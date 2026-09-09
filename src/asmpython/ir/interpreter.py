"""A reference interpreter for the IR.

Two jobs, and the second is the important one.

First, it is the executable specification. When the meaning of an opcode is
ambiguous, this file is the answer -- prose in `ops.py` describes intent, this
decides. `SHR` on `u32` is a logical shift because `_shr` says so.

Second, it makes a backend testable the moment it exists. Run a module here,
run the same module through a backend, compare the output: any difference is
the backend's bug, localised to one program. Without this, testing a new
backend means trusting that a Python program, a frontend, a runtime and a code
generator are all simultaneously correct, and a mismatch tells you nothing
about which one is wrong.

It is deliberately slow and obvious. Nothing here is optimised, because the one
property it must have is being right, and the second is being readable enough
that a disagreement with it can be adjudicated by reading it.

MEMORY is one flat bytearray. Address 0 is never handed out, so a null pointer
faults instead of aliasing a real object. Globals are laid out first, then
frames grow upward via `alloca`. There is no free: a program that allocas in a
loop will exhaust the arena, which is a correct diagnosis of the program.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from . import types as T
from .module import Function, Instruction, Module
from .opcodes import Op


class Trap(Exception):
    """The program did something undefined: divide by zero, bad address, ..."""


class _Exited(Exception):
    """`plat_exit` was called. Carries the status; caught only by `run`.

    An exception rather than a return, because the floor's contract is that
    `plat_exit` DOES NOT RETURN -- and the honest way to not return from a
    tree-walking interpreter is to unwind every frame at once. Returning a
    sentinel and checking for it at each call site is the version that works
    until one call site forgets.
    """

    def __init__(self, status: int) -> None:
        super().__init__(status)
        self.status = status


@dataclass
class Frame:
    func: Function
    registers: dict[int, int | float] = field(default_factory=dict)
    frame_base: int = 0
    #: Countdown of remaining STATIC reads for each `T.PTR` register in
    #: this function, or `None` when the optimisation below is not in
    #: effect for it (no object runtime, or the function contains a
    #: loop -- see `Interpreter._analyze`). A fresh copy per call, since
    #: it counts down over the course of ONE invocation.
    remaining: dict[int, int] | None = None
    #: Registers `_consume` must never retire early -- every parameter and
    #: every register ever assigned by `Op.COPY`, which is how a NAMED
    #: Python variable is told from a compiler temporary. Shared across
    #: calls (purely static, from `_analyze`), unlike `remaining`.
    named: frozenset[int] = frozenset()


class Memory:
    """A flat address space. Address 0 is reserved so null always faults."""

    def __init__(self, size: int = 1 << 22) -> None:
        self.buf = bytearray(size)
        self.brk = 8            # never hand out 0

    def alloc(self, nbytes: int, align: int = 8) -> int:
        addr = (self.brk + align - 1) & ~(align - 1)
        end = addr + max(1, nbytes)
        if end >= len(self.buf):
            raise Trap(f"out of memory: {nbytes} bytes at {addr:#x}")
        self.brk = end
        return addr

    def _check(self, addr: int, n: int) -> None:
        if addr <= 0 or addr + n > len(self.buf):
            raise Trap(f"invalid address {addr:#x} (+{n} bytes)")

    def read(self, addr: int, ty: T.Type) -> int | float:
        n = ty.size
        self._check(addr, n)
        raw = bytes(self.buf[addr:addr + n])
        if ty.is_float:
            return struct.unpack("<f" if n == 4 else "<d", raw)[0]
        return int.from_bytes(raw, "little", signed=ty.is_signed and ty is not T.I1)

    def write(self, addr: int, ty: T.Type, value: int | float) -> None:
        n = ty.size
        self._check(addr, n)
        if ty.is_float:
            raw = struct.pack("<f" if n == 4 else "<d", float(value))
        else:
            raw = (_wrap(int(value), ty)).to_bytes(
                n, "little", signed=ty.is_signed and ty is not T.I1)
        self.buf[addr:addr + n] = raw


def _wrap(v: int, ty: T.Type) -> int:
    """Truncate to the type's width, honouring signedness. Integers wrap."""
    if ty.is_ptr:
        return v & 0xFFFFFFFFFFFFFFFF
    bits = ty.bits
    v &= (1 << bits) - 1
    if ty.is_signed and bits > 1 and v >= (1 << (bits - 1)):
        v -= 1 << bits
    return v


class Interpreter:
    """Executes a verified module. `run(entry)` returns the entry's result."""

    def __init__(self, module: Module, *, out=None) -> None:
        self.module = module
        self.mem = Memory()
        self.out = out
        self.globals: dict[str, int] = {}
        self.steps = 0
        self.max_steps = 50_000_000
        #: The dynamic object runtime's state -- the handle table and the
        #: error flag -- created on the first `apy_*` call. Lazy because a
        #: statically typed program never makes one, and because the module
        #: imports this one back for `Trap`.
        self.objects = None
        #: Bytes `plat_write` received that do not yet form whole characters,
        #: per descriptor. See `_plat_write`.
        self._plat_pending: dict[int, bytes] = {}
        #: The status `plat_exit` was called with, or None if it never was.
        #: A host uses this to end the way a compiled program would.
        self.exit_status: int | None = None
        #: `id(Function)` -> `(has_loop, read_count)`, memoised by
        #: `_analyze`. A function is analysed at most once per run.
        self._fn_analysis: dict[int, tuple[bool, dict[int, int]]] = {}
        for g in module.globals:
            addr = self.mem.alloc(max(1, g.size))
            if g.data:
                self.mem.buf[addr:addr + len(g.data)] = g.data
            self.globals[g.name] = addr

    # ── host functions ──────────────────────────────────────────────────────
    # The IR has no I/O opcodes -- printing is not a machine operation. A
    # frontend calls a named function and the host provides it, exactly as a
    # real target would resolve it in a runtime library.
    def _host(self, name: str, args: list) -> int | float | None:
        # The dynamic object runtime first, because it is now most of what a
        # compiled program calls. It lives in its own module -- it is as big
        # as this file and it is one subject, the meaning of a Python VALUE,
        # rather than the meaning of an opcode. `NOT_MINE` keeps the fallthrough
        # explicit: a name it does not claim reaches the bindings below and,
        # failing those, the trap at the end.
        if name.startswith("apy_"):
            from .objects_host import NOT_MINE, ObjectHost
            if self.objects is None:
                self.objects = ObjectHost(self)
            result = self.objects.call(name, args)
            if result is not NOT_MINE:
                return result
        # THE PLATFORM FLOOR (`objects/floor.py`). The three functions a
        # backend must supply that are not IR, implemented here so the IR
        # interpreter runs the same runtime a backend runs -- which is the
        # whole point of docs/INERT-RUNTIME.md and what the corpus checks by
        # comparing this path against the C one.
        if name == "plat_write":
            return self._plat_write(int(args[0]), int(args[1]), int(args[2]))
        if name == "plat_exit":
            raise _Exited(int(args[0]) & 0xFF)
        if name == "plat_heap":
            n = int(args[0])
            if n <= 0:
                return 0
            try:
                return self.mem.alloc(n)
            except Trap:
                return 0            # null, by contract -- not a crash
        if name == "putchar":
            self._emit(chr(int(args[0]) & 0xFF))
            return 0
        if name == "put_int":
            self._emit(str(int(args[0])))
            return None
        if name == "put_float":
            self._emit(repr(float(args[0])))
            return None
        if name == "put_bool":
            self._emit("True" if int(args[0]) else "False")
            return None
        if name == "put_none":
            self._emit("None")
            return None
        if name == "print_int":
            self._emit(f"{int(args[0])}\n")
            return None
        if name == "py_pow_int":
            # Python's own `**`, which is the oracle every path is measured
            # against. The compiled runtime reaches the same answer the hard
            # way (double-double squaring, because the platform's libm `pow` is
            # a ulp off here); this is the same answer, cheaply.
            return float(args[0]) ** int(args[1])
        if name in ("pow", "powf"):
            # libm's, matching what a compiled binary links against and what
            # CPython's `**` calls. Python's float ** is this function; a
            # reimplementation here would disagree in the last bit.
            import math
            return math.pow(float(args[0]), float(args[1]))
        if name in ("fmod", "fmodf"):
            # The same arrangement as `pow`, for the same reason. Every
            # backend lowers a float REM to a call here rather than to an
            # instruction -- there is no float remainder in the ISA and
            # computing it from a division loses precision once the quotient
            # is large -- so a module that came back FROM one of them calls
            # `fmod` where the IR it was built from used the opcode.
            #
            # `_arith` already answers REM with `math.fmod`, so binding the
            # symbol to the same function is what keeps those two paths
            # agreeing. Without it, IR that round-trips through a backend
            # traps here on a program the original ran.
            import math
            return math.fmod(float(args[0]), float(args[1]))
        if name == "print_float":
            # Python's repr, which is what the runtime the compiled paths link
            # against now prints too (`objects/support.py`'s `py_repr_double`).
            # This used to be C's `%f` -- `32.000000` for `32.0` -- and the
            # comment here recorded that divergence as deliberate. It was, and
            # it also meant every float a compiled program printed disagreed
            # with CPython, which is precisely what the conformance suite
            # measures. What must never differ is THIS and a compiled binary,
            # so the two moved together.
            self._emit(repr(float(args[0])) + "\n")
            return None
        if name == "print_str":
            addr = int(args[0])
            end = self.mem.buf.index(0, addr)
            self._emit(bytes(self.mem.buf[addr:end]).decode("utf-8", "replace"))
            return None
        # THE HOST SERVICES (`objects/hostsvc.py`), which are the contract every
        # backend implements -- so the interpreter implements them too, and
        # is a backend like any other in that respect. Before the ctypes
        # bindings below, because these are the arrangement those exist to
        # replace and a name should mean the portable one where both exist.
        from .hostsvc_host import NOT_MINE as _HS_NOT_MINE, call as _hs_call
        result = _hs_call(self, name, args)
        if result is not _HS_NOT_MINE:
            return result
        # THE NATIVE SYMBOLS A `ctypes` DECLARATION REACHES, last, because a
        # bundled module's declaration is the only thing that puts one in an
        # IR module and the name could otherwise shadow a runtime function.
        # Without these the interpreter cannot run a program that opens a file
        # -- the declaration is resolved by the LINKER, and this path has no
        # linker -- so the oracle would have nothing to say about the compiled
        # behaviour of `pathlib`. See `natives_host.py`.
        from .natives_host import NOT_MINE, call as native_call
        result = native_call(self, name, args)
        if result is not NOT_MINE:
            return result
        raise Trap(f"call to undefined function {name!r} (no host binding)")

    def _emit(self, s: str) -> None:
        if self.out is None:
            print(s, end="")
        else:
            self.out.write(s)

    def _objects_own(self, name: str) -> bool:
        """Whether the host object runtime implements `name`. See `_call`."""
        from .objects_host import _TABLE
        return name in _TABLE

    def _plat_write(self, fd: int, addr: int, n: int) -> int:
        """`plat_write(fd, buf, n)`. Returns bytes written, or -1.

        THE OUTPUT HERE IS TEXT AND THE CONTRACT IS BYTES, so a multi-byte
        character split across two calls has to survive the split. It will
        happen: a runtime that formats into a fixed buffer and flushes when it
        is full has no idea where the character boundaries are. So incomplete
        trailing bytes are HELD until the next call rather than replaced, and
        only a sequence that is still invalid once it is complete becomes U+FFFD.
        """
        if n < 0:
            return -1
        if n == 0:
            return 0
        try:
            self.mem._check(addr, n)
        except Trap:
            return -1               # a bad address is a failed write, not a crash
        pending = self._plat_pending.get(fd, b"") + bytes(
            self.mem.buf[addr:addr + n])
        # Split off any incomplete sequence at the end. A UTF-8 lead byte says
        # how many continuations follow, so at most three bytes are ever held.
        cut = len(pending)
        for back in range(1, min(4, len(pending)) + 1):
            b = pending[-back]
            if b < 0x80:
                break
            if b >= 0xC0:           # a lead byte
                need = (2 if b < 0xE0 else 3 if b < 0xF0 else 4)
                if back < need:
                    cut = len(pending) - back
                break
        self._plat_pending[fd] = pending[cut:]
        text = pending[:cut].decode("utf-8", errors="replace")
        if fd == 2:
            import sys
            sys.stderr.write(text)
        else:
            self._emit(text)
        return n

    # ── execution ───────────────────────────────────────────────────────────
    def run(self, entry: str = "main", args: list | None = None):
        fn = self.module.function(entry)
        if fn is None:
            raise Trap(f"no function named {entry!r}")
        try:
            return self._call(fn, args or [])
        except _Exited as done:
            # `plat_exit` unwound every frame. The status is RECORDED as well
            # as returned, because a caller cannot otherwise tell it apart
            # from an ordinary `return 7` -- and the two mean different things
            # to whoever is hosting the interpreter. `driver/cli.py` reads it.
            self.exit_status = done.status
            return done.status

    def _call(self, fn: Function, args: list):
        if fn.external:
            return self._host(fn.name, args)
        if fn.name.startswith("apy_") and self._objects_own(fn.name):
            # THE HOST OBJECT RUNTIME OWNS EVERY `apy_*` NAME IT CLAIMS, even
            # when the module also DEFINES one -- which it now can, because
            # part of the runtime is compiled from `runtime/*.py` and spliced
            # in (`objects/ir.py`).
            #
            # The two cannot be mixed, and this is the reason rather than a
            # preference: `objects_host.py` represents an `apy_value` as a
            # HANDLE into a Python-side table, and the ported code represents
            # it as an ADDRESS in this interpreter's flat memory. A ported
            # `apy_from_int` therefore hands back something every unported
            # function rejects -- observed as `apy_is: 2248 is not a runtime
            # value handle`, which names neither runtime.
            #
            # So the port is NOT incremental on this path. The interpreter
            # keeps the host runtime until enough is ported to switch all at
            # once, and until then it is the ORACLE the compiled paths are
            # measured against, which is what the corpus is for.
            return self._host(fn.name, args)
        fr = Frame(fn, frame_base=self.mem.brk)
        # NOT GATED ON `self.objects` -- purely static, and cheap, so it
        # runs even for the OUTERMOST call, before the object runtime
        # necessarily exists yet (`self.objects` is lazy: the first
        # `apy_*` call creates it). Gating this on `self.objects is not
        # None` here left the very first frame -- a script's whole
        # top-level body, for the common case -- permanently without a
        # `remaining` table, since that check ran before this frame's
        # first `apy_*` call had a chance to create one. `_consume`
        # guards the actual decref on `self.objects` itself, which by
        # the time anything reaches it, is set.
        has_loop, read_count, named = self._analyze(fn)
        fr.named = named
        if not has_loop:
            fr.remaining = dict(read_count)
        for reg, val in zip(fn.params, args):
            fr.registers[reg] = val
            # A PARAMETER IS A NEW BINDING, same as `put()` treats any other
            # register write -- the caller's own reference to `val`
            # (whatever slot it came from) is untouched; this is the
            # callee's OWN, additional one.
            if self.objects is not None and fn.registers.get(reg) is T.PTR and val:
                self.objects.incref(val)
        blk = fn.blocks[0]
        prev_brk = self.mem.brk
        returned = None
        try:
            while True:
                nxt = None
                for ins in blk.instructions:
                    self.steps += 1
                    if self.steps > self.max_steps:
                        raise Trap("step limit exceeded (infinite loop?)")
                    res = self._exec(fr, ins)
                    if isinstance(res, _Jump):
                        nxt = res
                        break
                    if isinstance(res, _Return):
                        returned = res.value
                        return res.value
                if nxt is None:
                    raise Trap(f"{fn.name}/{blk.label}: fell off the end")
                target = fn.block(nxt.label)
                if target is None:
                    raise Trap(f"{fn.name}: no block {nxt.label!r}")
                blk = target
        finally:
            self.mem.brk = prev_brk     # frame allocas die with the frame
            if self.objects is not None:
                # EVERY REGISTER IN THIS FRAME IS GOING OUT OF SCOPE. Decref
                # each one that held a handle -- EXCEPT ONE occurrence of
                # whatever is being returned (`returned` stays `None`, and
                # so matches nothing, on a trap/exception rather than a real
                # return): that reference is being HANDED TO THE CALLER, not
                # dropped, and the caller's own `put()` -- in whichever
                # `_exec` called this -- will count its new ownership on
                # receipt. Skipping the decref here rather than fixing this
                # frame's copy up first and asking the caller not to
                # re-count leaves a handle passed through several nested
                # returns slightly OVER-counted -- finalized a step too
                # LATE, never a step too EARLY -- which is the direction
                # `ObjectHost.decref`'s own docstring says is safe to be
                # wrong in.
                skipped = False
                for reg, ty in fr.func.registers.items():
                    if ty is not T.PTR:
                        continue
                    val = fr.registers.get(reg)
                    if not val:
                        continue
                    if not skipped and val == returned:
                        skipped = True
                        continue
                    self.objects.decref(val)

    def _analyze(self, fn: Function) -> tuple[bool, dict[int, int], frozenset[int]]:
        """Whether `fn` has a loop, how many times each `T.PTR` register is
        READ (an operand of some instruction, anywhere in the function) in
        total, and which registers are NAMED -- see below. Memoised per
        function -- purely static, so it never changes across calls.

        WHAT THIS BUYS: `Op.COPY` and `Op.STORE` -- `x = <expr>` and a
        global/attribute assignment -- read a source register whose value
        they hand to a longer-lived home, but that source register itself
        keeps counting as an owner (`put()`'s own incref when it was
        FIRST written) until something decrefs it. Nothing does, ordinarily,
        until the register's whole FRAME tears down -- which for a
        function is that call's return, and for a module's top-level code
        is the end of the program. `_consume` uses `read_count` to tell
        the LAST static read of a register from an earlier one, so that
        last read can retire the register's own reference right there
        instead of waiting for the frame to end.

        LOOPS ARE EXCLUDED ENTIRELY, for one function-wide reason: a
        register's STATIC read count is not its DYNAMIC one when a read
        sits inside a loop body -- the same instruction fires every
        iteration, and retiring the register's reference after the first
        pass would finalize something a later pass still needs to read.
        Detecting per-register whether a given read is actually inside a
        loop (rather than merely "this function has one somewhere") would
        recover the optimisation for the rest of a loopy function, but
        that is real control-flow analysis; ruling out the whole function
        is the cheap, safe version -- registers in it simply keep waiting
        for frame teardown, exactly as they did before this existed.

        NAMED REGISTERS ARE NEVER RETIRED AT THEIR LAST READ, and this is
        not an optimisation left on the table -- it is the difference
        between a compiler TEMPORARY and a Python VARIABLE, and `_consume`
        finalizing the wrong one is a real bug this analysis exists to
        prevent, not a missed case. `dynamic.py` gives every named local,
        parameter and closure slot ONE PERSISTENT register, written via
        `Op.COPY` for each assignment (`_dyn_store`) -- so `y = x` reads
        `x`'s register as `Op.COPY`'s SOURCE. If `x` happens not to be
        read again after that line, its read count reaches zero right
        there, and retiring it would drop `x`'s OWN reference the moment
        `y = x` runs -- even though `x` is still a live, bound name that
        CPython would not release until reassignment, `del`, or the
        function's return. `print(x.name)` is the same hazard through a
        CALL argument instead of a COPY source. Measured: both finalized
        an object at its last syntactic mention, one and sometimes two
        statements before CPython would have. So a register is NAMED --
        excluded from `_consume` entirely -- if it is ever a PARAMETER, or
        ever the `dst` of an `Op.COPY` anywhere in the function; a true
        temporary (a CALL's raw result, handed to exactly one COPY/STORE/
        CALL argument and never itself assigned INTO) is never `Op.COPY`'s
        destination and keeps the optimisation.
        """
        cached = self._fn_analysis.get(id(fn))
        if cached is not None:
            return cached
        has_loop = self._has_cycle(fn)
        read_count: dict[int, int] = {}
        named: set[int] = set(fn.params)
        for blk in fn.blocks:
            for ins in blk.instructions:
                for reg in ins.args:
                    if fn.registers.get(reg) is T.PTR:
                        read_count[reg] = read_count.get(reg, 0) + 1
                if ins.op is Op.COPY and ins.dst is not None:
                    named.add(ins.dst)
        result = (has_loop, read_count, frozenset(named))
        self._fn_analysis[id(fn)] = result
        return result

    def _has_cycle(self, fn: Function) -> bool:
        """Does `fn`'s control-flow graph have an actual cycle -- some
        block reachable from itself along a real path -- reachable from
        `fn`'s entry block?

        NOT "does some edge point to an earlier block": this compiler's
        own bound/unbound-variable check (every read of a name that
        might be unassigned) emits an `UNBOUND` block that raises, calls
        `apy_fatal_if_error` (which never returns once an error is
        pending), and only THEN has an unconditional `jump` back to the
        `BOUND` block it belongs to -- a well-formed IR needs a
        terminator there even though control never reaches it. That jump
        points backward in block order on virtually every function that
        reads a possibly-unbound name, which is nearly all of them, and
        a plain "target index <= source index" check flagged it as a
        loop every time, disabling `_analyze`'s optimisation almost
        everywhere it mattered, including a plain top-level script.
        `BOUND` never leads back to that specific `UNBOUND` block, so it
        is not actually part of a cycle -- there is no path from `BOUND`
        back to it -- which is exactly what a real cycle test answers
        and a same-or-earlier-index test does not.

        Standard DFS back-edge test: a GRAY node is one on the current
        path (an ancestor, not yet fully explored); an edge to a GRAY
        node is a genuine back edge, and a graph has a cycle reachable
        from the start iff DFS from it finds one. Iterative, to not
        depend on Python's recursion limit for a function with an
        unusually large block count.
        """
        blocks = {b.label: b for b in fn.blocks}
        if not fn.blocks:
            return False
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {label: WHITE for label in blocks}
        start = fn.blocks[0].label
        # Each stack entry is (label, index of the next successor to try)
        # -- the standard "explicit stack" shape for an iterative DFS
        # that needs to resume a node after each child returns, the
        # same thing the call stack would do for a recursive version.
        succs_of: dict[str, list[str]] = {}
        stack: list[tuple[str, int]] = [(start, 0)]
        color[start] = GRAY
        while stack:
            label, idx = stack[-1]
            succs = succs_of.get(label)
            if succs is None:
                blk = blocks.get(label)
                succs = succs_of[label] = blk.successors if blk is not None else []
            advanced = False
            while idx < len(succs):
                nxt = succs[idx]
                idx += 1
                c = color.get(nxt, BLACK)   # an unknown label: nothing to visit
                if c == GRAY:
                    return True
                if c == WHITE:
                    color[nxt] = GRAY
                    stack[-1] = (label, idx)
                    stack.append((nxt, 0))
                    advanced = True
                    break
            if advanced:
                continue
            stack[-1] = (label, idx)
            color[label] = BLACK
            stack.pop()
        return False

    def _consume(self, fr: Frame, reg: int) -> None:
        """One static read of `reg` -- from `_analyze`'s count -- has just
        been spent. At the last one, this invocation's value for `reg`
        will never be read again (true only because `_analyze` found no
        loop in this function, so the static count IS the dynamic one),
        so the register's own reference is dropped here.

        CALLED AFTER the consuming instruction's OWN `put()`/incref of
        the same handle has already run: `x = t` and `t` are the SAME
        handle at that point, and dropping `t`'s reference FIRST would
        read as zero and finalize an object one line away from gaining
        the new owner `put()` just gave it.
        """
        if fr.remaining is None or self.objects is None:
            # NO OBJECT RUNTIME: a `T.PTR` register in a program that
            # never touches `apy_*` at all is a raw address (see `put()`'s
            # own "one pointer type for both" comment) -- `_analyze` does
            # not know that when it builds `read_count`, since it has no
            # way to tell a handle-shaped program from an address-shaped
            # one ahead of time. Nothing to consume in that case.
            return
        if reg in fr.named:
            # A PYTHON VARIABLE, not a temporary -- see `_analyze`'s own
            # comment on why this register's LAST static read is not
            # when CPython would drop it, and never retired here.
            return
        left = fr.remaining.get(reg)
        if left is None:
            return
        left -= 1
        fr.remaining[reg] = left
        if left <= 0:
            v = fr.registers.get(reg)
            if v:
                self.objects.decref(v)
                # CLEARED, not merely counted down: `_call`'s frame
                # teardown decrefs every `T.PTR` register still holding a
                # value, with no idea a register's reference was already
                # retired here -- left as `v`, it would be decref'd a
                # SECOND time at teardown, one too many, finalizing an
                # object that is (from this frame's point of view) still
                # alive through whatever `reg` was copied/stored into.
                fr.registers[reg] = 0

    def _exec(self, fr: Frame, ins: Instruction):
        op, ty = ins.op, ins.ty
        R = fr.registers

        def a(i: int):
            try:
                return R[ins.args[i]]
            except KeyError:
                raise Trap(
                    f"{fr.func.name}: read of uninitialised register "
                    f"%{ins.args[i]}"
                ) from None

        def put(v):
            if ins.dst is not None:
                # SHADOW REFCOUNTING'S ONE CHOKE POINT for every register in
                # the interpreter: every instruction with a `dst` writes it
                # through here, so hooking this one function -- rather than
                # each of the several dozen opcode handlers above and below
                # -- covers every local/temporary's lifecycle uniformly. See
                # `ObjectHost.incref`/`decref` for what happens at each end.
                #
                # `fr.func.registers[dst]`, NOT `ty`: `ty` is documented
                # (module.py) to be the OPERAND type for a comparison, not
                # the result's -- `apy_x == apy_y` has `ty is T.PTR` but
                # writes an `i1`, and treating that `0`/`1` as a handle
                # would decref whatever handle happened to equal 0 or 1.
                # The register's OWN declared type has no such ambiguity:
                # it is fixed for the register's whole life (module.py).
                #
                # KNOWN, ACCEPTED IMPRECISION: a `ptr` register can ALSO
                # hold a raw memory address (an `alloca`, a global's
                # address) rather than an object-runtime handle -- the IR
                # has one pointer type for both, and nothing here tells them
                # apart. `ObjectHost.incref`/`decref` are no-ops for a
                # number that is not a handle THIS RUN has minted, so this
                # is silent almost always; the one way it can go wrong is a
                # raw address numerically coinciding with a handle that
                # genuinely exists right now, which only a program mixing
                # heavy `alloca` use with the object runtime in the same
                # function risks. Every bundled stdlib module -- the
                # differential suite this exists to serve -- is ordinary
                # dynamic Python and never allocas, so this does not reach
                # them.
                if self.objects is not None and fr.func.registers.get(ins.dst) is T.PTR:
                    old = R.get(ins.dst)
                    # NEW BEFORE OLD. `x = x` -- or anything that hands
                    # this register back its own current value, a tuple
                    # swap's `a[i], a[j] = a[j], a[i]` included -- has
                    # `v == old`: decrefing first would pass through a
                    # transient zero and finalize an object that is, by
                    # the end of this one assignment, exactly as alive as
                    # it was at the start.
                    if v:
                        self.objects.incref(v)
                        # LIFTS ANY `_instantiate`-STYLE PIN now that the
                        # register itself is a real reference -- see
                        # `ObjectHost.settle`. A freshly constructed
                        # object's handle rides pinned, not decref'd,
                        # all the way from `_instantiate` up through
                        # every host frame in between (none of which
                        # this interpreter's refcounting hooks touch)
                        # to exactly this store; settling anywhere else
                        # would either release too early (a nested call
                        # still in flight) or never (nothing else calls
                        # it).
                        self.objects.settle(v)
                    if old:
                        self.objects.decref(old)
                R[ins.dst] = v
            return None

        if op is Op.CONST:
            return put(float(ins.imm) if ty.is_float else _wrap(int(ins.imm), ty))
        if op is Op.COPY:
            src = ins.args[0]
            res = put(a(0))
            # See `_consume`: retires the SOURCE register's own reference
            # once this was its last static read, now that `put()` above
            # has already given the destination its own.
            self._consume(fr, src)
            return res
        if op is Op.GLOBAL_ADDR:
            return put(self.globals[ins.sym])
        if op is Op.FUNC_ADDR:
            return put(_FUNC_TAG | self.module.functions.index(self.module.function(ins.sym)))

        if op in _ARITH:
            return put(_arith(op, ty, a(0), a(1)))
        if op is Op.NEG:
            return put(-a(0) if ty.is_float else _wrap(-a(0), ty))
        if op is Op.NOT:
            return put(_wrap(~int(a(0)), ty))
        if op in (Op.SHL, Op.SHR):
            return put(_shift(op, ty, int(a(0)), int(a(1))))
        if op in _CMP:
            return put(1 if _compare(op, ty, a(0), a(1)) else 0)

        if op is Op.TRUNC:
            return put(_wrap(int(a(0)), ty))
        if op is Op.EXTEND:
            return put(_wrap(int(a(0)), ty))
        if op is Op.FTOI:
            return put(_wrap(int(a(0)), ty))
        if op is Op.ITOF:
            return put(float(a(0)))
        if op is Op.FTOF:
            v = float(a(0))
            return put(struct.unpack("<f", struct.pack("<f", v))[0]
                       if ty is T.F32 else v)
        if op is Op.BITCAST:
            return put(_bitcast(a(0), fr.func.register_type(ins.args[0]), ty))

        if op is Op.ALLOCA:
            return put(self.mem.alloc(int(ins.imm)))
        if op is Op.LOAD:
            return put(self.mem.read(int(a(0)), ty))
        if op is Op.STORE:
            addr = int(a(1))
            # THE SAME CHOKE POINT AS `put()`, for a `ptr`-typed value
            # landing in MEMORY rather than a register -- a global (`b =
            # Foo(...)` at module scope lowers to `global_addr`+`store`,
            # never through a register `dst`) or an address-taken local.
            # Without this a global holding the only reference to an
            # object never triggers `decref` on reassignment or `del`,
            # so nothing here ever finalizes at the moment a Python
            # program would observe it -- only ever (if at all) whenever
            # something else happens to touch the same handle.
            #
            # `ty`, NOT A DECLARED SLOT TYPE: unlike a register, a raw
            # memory address has no type of its own in this IR (`Global`
            # carries only a byte size -- see `module.py`) -- but unlike
            # `put()`'s `ins.dst` case, `Op.STORE`'s `ty` IS unambiguously
            # the type of the value being stored (`self.mem.write` above
            # already trusts it for that), so there is no equivalent of
            # the comparison-operand ambiguity `put()` has to route
            # around. The same accepted imprecision applies as there: a
            # `ptr` store can be a raw address rather than a handle, and
            # nothing here tells them apart -- see `put()`'s own comment.
            if self.objects is not None and ty is T.PTR:
                old = self.mem.read(addr, ty)
                v = a(0)
                self.mem.write(addr, ty, v)
                # NEW BEFORE OLD -- see `put()`'s own comment: `old == v`
                # (storing a global's own current value back into it) must
                # not decref through a transient zero before the matching
                # incref lands.
                if v:
                    self.objects.incref(int(v))
                    self.objects.settle(int(v))
                if old:
                    self.objects.decref(int(old))
                # See `_consume`: the SOURCE register (`ins.args[0]`) held
                # its own reference from whenever it was written; now that
                # the address just got its own (above), retire the
                # register's if this was its last static read.
                self._consume(fr, ins.args[0])
                return None
            self.mem.write(addr, ty, a(0))
            return None
        if op is Op.OFFSET:
            return put(int(a(0)) + int(a(1)))

        if op is Op.CALL:
            callee = self.module.function(ins.sym)
            if callee is None:
                raise Trap(f"call to unknown function {ins.sym!r}")
            # NOT ROUTED THROUGH `_consume`, deliberately, even though a
            # CALL argument that is never read again afterward has the
            # same "phantom reference until frame teardown" story
            # `Op.COPY`/`Op.STORE` do -- and once did retire it here.
            # Reverted: `_consume`'s safety needs the CALLEE to incref
            # anything it keeps, the way `_attr_store`/`_dict_set`/
            # `_apy_seq_push` were fixed to. `apy_cell_set` (closures)
            # was not one of the audited ones -- `def inner(): return
            # captured` finalized `captured` the moment the closure
            # captured it, before `inner` was ever called, because
            # nothing in the cell-store path claimed a reference the way
            # a list append now does. Two hundred more `apy_*` functions
            # exist unaudited; retiring an argument here is only safe
            # for the ones actually checked, and checking all of them
            # was not -- so nothing here is retired early, and it goes
            # back to waiting for frame teardown, the same as before
            # this optimisation existed.
            return put(self._call(callee, [R[x] for x in ins.args]))
        if op is Op.CALL_PTR:
            idx = int(a(0)) & ~_FUNC_TAG
            # See `Op.CALL`'s own comment -- not routed through `_consume`.
            return put(self._call(self.module.functions[idx],
                                  [R[x] for x in ins.args[1:]]))

        if op is Op.JUMP:
            return _Jump(ins.labels[0])
        if op is Op.BRANCH:
            return _Jump(ins.labels[0] if a(0) else ins.labels[1])
        if op is Op.SWITCH:
            v = int(a(0))
            for cv, lbl in ins.cases:
                if cv == v:
                    return _Jump(lbl)
            return _Jump(ins.labels[0])
        if op is Op.RET:
            return _Return(a(0) if ins.args else None)
        if op is Op.UNREACHABLE:
            raise Trap(f"{fr.func.name}: reached `unreachable`")

        raise Trap(f"interpreter has no rule for {op.value!r}")


_FUNC_TAG = 1 << 40


@dataclass(slots=True)
class _Jump:
    label: str


@dataclass(slots=True)
class _Return:
    value: object


_ARITH = (Op.ADD, Op.SUB, Op.MUL, Op.DIV, Op.REM, Op.AND, Op.OR, Op.XOR)
_CMP = (Op.EQ, Op.NE, Op.LT, Op.LE, Op.GT, Op.GE)


def _arith(op: Op, ty: T.Type, x, y):
    if ty.is_float:
        if op is Op.ADD: return x + y
        if op is Op.SUB: return x - y
        if op is Op.MUL: return x * y
        if op is Op.DIV:
            if y == 0:
                raise Trap("float division by zero")
            return x / y
        if op is Op.REM:
            if y == 0:
                raise Trap("float remainder by zero")
            import math
            return math.fmod(x, y)
        raise Trap(f"{op.value} is not defined on {ty}")
    x, y = int(x), int(y)
    if op is Op.ADD: return _wrap(x + y, ty)
    if op is Op.SUB: return _wrap(x - y, ty)
    if op is Op.MUL: return _wrap(x * y, ty)
    if op is Op.AND: return _wrap(x & y, ty)
    if op is Op.OR:  return _wrap(x | y, ty)
    if op is Op.XOR: return _wrap(x ^ y, ty)
    if y == 0:
        raise Trap("integer division by zero")
    # Truncating division, like C and every machine -- NOT Python's floor
    # division. A frontend whose language floors must lower it to more than
    # one opcode; see ops.py on REM.
    q = abs(x) // abs(y)
    if (x < 0) != (y < 0):
        q = -q
    if op is Op.DIV:
        return _wrap(q, ty)
    return _wrap(x - q * y, ty)


def _shift(op: Op, ty: T.Type, x: int, n: int):
    if n < 0 or n >= ty.bits:
        raise Trap(f"shift by {n} is undefined for {ty}")
    if op is Op.SHL:
        return _wrap(x << n, ty)
    if ty.is_signed:
        return _wrap(x >> n, ty)                      # arithmetic
    return _wrap((x & ((1 << ty.bits) - 1)) >> n, ty)  # logical


def _compare(op: Op, ty: T.Type, x, y) -> bool:
    if op is Op.EQ: return x == y
    if op is Op.NE: return x != y
    if op is Op.LT: return x < y
    if op is Op.LE: return x <= y
    if op is Op.GT: return x > y
    return x >= y


def _bitcast(v, src: T.Type, dst: T.Type):
    if src.is_float and not dst.is_float:
        raw = struct.pack("<f" if src.size == 4 else "<d", float(v))
        return int.from_bytes(raw, "little", signed=dst.is_signed)
    if dst.is_float and not src.is_float:
        raw = _wrap(int(v), src).to_bytes(src.size, "little",
                                          signed=src.is_signed)
        return struct.unpack("<f" if dst.size == 4 else "<d", raw)[0]
    return _wrap(int(v), dst)


def run(module: Module, entry: str = "main", args: list | None = None, *, out=None):
    """Convenience: execute `module` and return the entry function's result."""
    return Interpreter(module, out=out).run(entry, args)
