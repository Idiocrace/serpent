"""Each object format gets the directives it actually accepts.

WHY THIS FILE EXISTS. `x86_64-macos` and `aarch64-macos` had been registered
targets since the beginning, and both emitted ELF. The x86-64 backend chose
its dialect with `coff if ... else elf` and the arm64 backend had no notion of
a dialect at all, so `--target x86_64-macos` produced output BYTE-IDENTICAL to
the Linux one: `.type`, `.size` and `.note.GNU-stack`, none of which a Mach-O
assembler will take, and no leading underscore, so nothing would have resolved
even if it had assembled.

Nothing caught it because nothing compared the formats. Every test asked
whether ONE target produced good assembly, and the answer was yes for the two
that were exercised. So the assertions here are DIFFERENTIAL -- what one
format has and another must not -- because that is the shape of the bug.

The text checks need no toolchain and are the regression guard. The assembly
check needs clang, which can target all three formats from any host, and is
the one that would notice a directive this file has not thought to name.
"""
from __future__ import annotations

import shutil
import subprocess

from tests import harness

from asmpython import target as target_registry
from asmpython.diagnostics import DiagnosticSink
from asmpython.driver import Options, compile_source

HAS_CLANG = bool(shutil.which("clang"))


#: A program with a call and a definition, so both a symbol's DEFINITION and
#: its USE are in the output -- the prefix has to reach both, and applying it
#: to only one is the failure mode that links to nothing.
SOURCE = """\
def add(a: int, b: int) -> int:
    return a + b


def main() -> int:
    return add(3, 4)
"""

#: backend, target, and the triple clang assembles that target's output with.
MATRIX = [
    ("x86-64", "x86_64-linux", "x86_64-linux-gnu"),
    ("x86-64", "x86_64-windows", "x86_64-windows-gnu"),
    ("x86-64", "x86_64-macos", "x86_64-apple-darwin"),
    ("arm64", "aarch64-linux", "aarch64-linux-gnu"),
    ("arm64", "aarch64-macos", "arm64-apple-darwin"),
    ("arm64", "aarch64-none", "aarch64-linux-gnu"),
]


def _artifact(tmp_path, backend: str, target: str) -> tuple[str, bytes]:
    """What this backend writes for this target, named and unread."""
    path = tmp_path / "prog.py"
    path.write_text(SOURCE, encoding="utf-8")
    result = compile_source(Options(
        source=path, backend=backend,
        target=target_registry.get(target)), DiagnosticSink())
    assert result.ok, f"{backend}/{target} did not compile"
    (name, body), = result.artifacts.items()
    return name, body


def _asm(tmp_path, backend: str, target: str) -> str:
    """The assembly this backend writes for this target.

    ONLY FOR A TARGET THAT STILL GOES THROUGH TEXT. Once a backend writes the
    object itself there is no assembly to read and the dialect's job has moved
    into the symbol table -- see `TestTheElfObjectSaysWhatTheDirectivesDid`.
    """
    name, body = _artifact(tmp_path, backend, target)
    assert name.endswith(".s"), (
        f"{backend}/{target} emits {name}, not assembly; this claim belongs "
        f"in the object-file tests")
    return body.decode("utf-8")


#: Pairs still assembled from text. THIS SHRINKS as backends grow encoders,
#: and the claims about each pair move rather than disappear.
TEXT_MATRIX = [row for row in MATRIX
               if (row[0], row[1]) != ("x86-64", "x86_64-linux")]


class TestTheDialectsDiffer:
    @harness.cases("backend,target", [(b, t) for b, t, _ in MATRIX
                                      if t.endswith("macos")])
    def test_macho_symbols_wear_an_underscore(self, backend, target, tmp_path):
        """Mach-O's C ABI prefixes every symbol, at the definition AND the call."""
        text = _asm(tmp_path, backend, target)
        assert "_asmpython_main:" in text, "the entry point is not prefixed"
        assert "_add:" in text, "a defined symbol is not prefixed"
        # THE CALL SITE TOO, or the call resolves to nothing. Read off the
        # branch instruction rather than by position: the definition of `add`
        # precedes the call to it, so "before the label" finds the wrong half.
        call = [l for l in text.splitlines()
                if l.lstrip().startswith(("call", "bl "))]
        assert call, "no call instruction in the output"
        assert all("_add" in l for l in call), f"call site not prefixed: {call}"

    @harness.cases("backend,target", [(b, t) for b, t, _ in MATRIX
                                      if t.endswith("macos")])
    def test_macho_has_no_elf_directives(self, backend, target, tmp_path):
        """`.type`, `.size` and `.note.GNU-stack` are each a hard error there."""
        text = _asm(tmp_path, backend, target)
        for directive in (".type", ".size", ".note.GNU-stack"):
            assert directive not in text, f"{directive} survives into Mach-O"

    @harness.cases("backend,target", [("arm64", "aarch64-linux")])
    def test_elf_still_declares_its_symbols(self, backend, target, tmp_path):
        """The other half of the fix: ELF must not have LOST anything."""
        text = _asm(tmp_path, backend, target)
        assert ".type" in text and ".size" in text
        assert "asmpython_main:" in text and "_asmpython_main:" not in text

    def test_coff_uses_its_own_definition_directive(self, tmp_path):
        """`.def/.scl/.endef`, and NOT the ELF pair.

        COFF's `.def` line carries a `.type 32;` of its own, so the test is
        that `.type x, @function` is absent -- not that the four characters
        `.type` are.
        """
        text = _asm(tmp_path, "x86-64", "x86_64-windows")
        assert ".def" in text and ".endef" in text
        assert "@function" not in text and ".size" not in text

    @harness.cases("backend,a,b", [
        ("x86-64", "x86_64-linux", "x86_64-macos"),
        ("x86-64", "x86_64-linux", "x86_64-windows"),
        ("arm64", "aarch64-linux", "aarch64-macos"),
    ])
    def test_two_formats_are_not_the_same_text(self, backend, a, b, tmp_path):
        """THE ASSERTION THAT WOULD HAVE CAUGHT IT.

        Byte-identical output for two object formats is the whole bug, and it
        is checkable without knowing which directive is wrong.
        """
        # COMPARED AS BYTES, because one side of a pair may be an object and
        # the other assembly: decoding would fail on the object rather than
        # answer the question, and the question is only whether they differ.
        assert _artifact(tmp_path, backend, a)[1] \
            != _artifact(tmp_path, backend, b)[1]


class TestTheElfObjectSaysWhatTheDirectivesDid:
    """Where `.type` and `.size` go once nothing writes assembly.

    THE CLAIM IS THE SAME ONE, moved. `.type add, @function` and `.size add,
    .-add` exist to put a kind and a length in the symbol table; a backend
    writing the table itself sets those fields directly, so the test reads the
    fields rather than the directives that used to produce them. Dropping the
    check with the text would have retired the only assertion that the ELF
    path describes its symbols at all.
    """

    def _object(self, tmp_path):
        name, body = _artifact(tmp_path, "x86-64", "x86_64-linux")
        assert name.endswith(".o"), name
        path = tmp_path / name
        path.write_bytes(body)
        return path

    @harness.needs("readelf")
    def test_the_symbols_carry_their_kind_and_size(self, tmp_path):
        out = subprocess.run(["readelf", "-sW", str(self._object(tmp_path))],
                             capture_output=True, text=True, check=True).stdout
        # `Num: Value Size Type Bind Vis Ndx Name`. The header row starts
        # with `Num:` and would otherwise parse as a symbol called `Name`.
        rows = {}
        for line in out.splitlines():
            fields = line.split()
            if len(fields) >= 8 and fields[0][:-1].isdigit():
                rows[fields[7]] = (fields[3], int(fields[2], 0))
        for wanted in ("add", "asmpython_main"):
            assert wanted in rows, f"{wanted} is not in the symbol table"
            kind, size = rows[wanted]
            assert kind == "FUNC", f"{wanted} is {kind}, not FUNC"
            assert size > 0, f"{wanted} has no size"
        # NO LEADING UNDERSCORE, which is the Mach-O convention and would
        # resolve to nothing here. The text test asserted this too.
        assert "_asmpython_main" not in rows

    @harness.needs("readelf")
    def test_the_stack_is_marked_non_executable(self, tmp_path):
        """`.note.GNU-stack` as a section rather than a directive.

        Without it a linker assumes the worst and marks the whole program's
        stack executable -- a real difference in the binary produced, and one
        no other test would notice.
        """
        out = subprocess.run(["readelf", "-SW", str(self._object(tmp_path))],
                             capture_output=True, text=True, check=True).stdout
        assert ".note.GNU-stack" in out


@harness.skip_if(not HAS_CLANG, reason="no clang to assemble with")
class TestItActuallyAssembles:
    """clang cross-assembles all three formats from any host, so this runs
    everywhere rather than only on the platform it describes."""

    @harness.cases("backend,target,triple", TEXT_MATRIX)
    def test_the_output_assembles(self, backend, target, triple, tmp_path):
        source = tmp_path / "out.s"
        source.write_text(_asm(tmp_path, backend, target), encoding="utf-8")
        done = subprocess.run(
            ["clang", "-target", triple, "-c", str(source),
             "-o", str(tmp_path / "out.o")],
            capture_output=True, text=True)
        assert done.returncode == 0, (
            f"{backend}/{target} did not assemble as {triple}:\n{done.stderr}")
