# COVERAGE: sys.getrefcount -- one binding, a second binding, a binding
# dropped, membership in a list, a dict value, a set member, an instance
# attribute, and each of those going away again. A function asking about
# its OWN PARAMETER reads one higher here than in CPython 3.14 and is
# left out on purpose -- see `objects_host._apy_sys_getrefcount` for
# why (that binding is a counted reference here and a borrowed one
# there).
import sys


class Foo:
    def __init__(self):
        self.child = None


def bindings():
    x = Foo()
    print("one name:", sys.getrefcount(x))
    y = x
    print("two names:", sys.getrefcount(x))
    z = x
    print("three names:", sys.getrefcount(x))
    del z
    print("back to two:", sys.getrefcount(x))
    del y
    print("back to one:", sys.getrefcount(x))


bindings()
print("--- bindings done ---")


def containers():
    x = Foo()
    print("start:", sys.getrefcount(x))
    xs = [x, x]
    print("twice in a list:", sys.getrefcount(x))
    d = {"k": x}
    print("plus a dict value:", sys.getrefcount(x))
    s = {x}
    print("plus a set member:", sys.getrefcount(x))
    holder = Foo()
    holder.child = x
    print("plus an attribute:", sys.getrefcount(x))
    holder.child = None
    print("attribute gone:", sys.getrefcount(x))
    s.discard(x)
    print("set member gone:", sys.getrefcount(x))
    del d["k"]
    print("dict entry gone:", sys.getrefcount(x))
    xs.clear()
    print("list cleared:", sys.getrefcount(x))


containers()
print("--- containers done ---")


def overwritten():
    x = Foo()
    xs = [x]
    print("in the list:", sys.getrefcount(x))
    xs[0] = None
    print("overwritten:", sys.getrefcount(x))


overwritten()
print("--- overwritten done ---")


# --- a reference a CALL made, and gave back --------------------------
#
# Passing an object into a function does not leave a reference behind:
# the callee's binding is gone the moment it returns. Written out because
# the reverse -- an argument the interpreter went on counting -- is
# invisible to every test that does not ask this question, and shows up
# instead as a `__del__` that never runs and a `weakref` that never dies.
def looked_at(o):
    return 0


def calls_leave_nothing():
    x = Foo()
    print("before any call: ", sys.getrefcount(x))
    looked_at(x)
    print("after a plain call:", sys.getrefcount(x))
    looked_at(x)
    looked_at(x)
    print("after three:      ", sys.getrefcount(x))
    x.method_like = None
    repr(x)
    print("after a builtin:  ", sys.getrefcount(x))


calls_leave_nothing()
print("done")


# --- the bundled half: streams, breakpoint, audit, monitoring ---------
print("stdout writable:", sys.stdout.writable(), sys.stdout.readable(),
      sys.stdout.seekable())
print("descriptors:", sys.stdout.fileno(), sys.stderr.fileno())
print("closed/isatty:", sys.stdout.closed, sys.stdout.isatty(),
      sys.stdout.flush())
try:
    sys.stdout.write(7)
except TypeError as exc:
    print("write type:", exc)

calls = []
sys.breakpointhook = lambda *a, **kw: calls.append((a, sorted(kw)))
breakpoint()
breakpoint(1, k=2)
print("breakpoint:", calls, callable(breakpoint))

seen = []
sys.addaudithook(lambda event, args: seen.append((event, args)))
sys.audit("stdlib.test", 1, "two")
sys.audit("stdlib.other")
print("audit:", seen, callable(sys.audit), callable(sys.addaudithook))

mon = sys.monitoring
print("ids:", mon.DEBUGGER_ID, mon.COVERAGE_ID, mon.PROFILER_ID,
      mon.OPTIMIZER_ID)
print("events:", mon.events.NO_EVENTS, mon.events.PY_START, mon.events.CALL,
      mon.events.LINE, mon.events.BRANCH)
print("unclaimed:", mon.get_tool(mon.DEBUGGER_ID))
mon.use_tool_id(mon.DEBUGGER_ID, "stdlib")
print("claimed:", mon.get_tool(mon.DEBUGGER_ID))
try:
    mon.use_tool_id(mon.DEBUGGER_ID, "again")
except ValueError as exc:
    print("reuse:", exc)
print("events before:", mon.get_events(mon.DEBUGGER_ID))
mon.set_events(mon.DEBUGGER_ID, mon.events.CALL | mon.events.LINE)
print("events after:", mon.get_events(mon.DEBUGGER_ID))
print("callback:", mon.register_callback(mon.DEBUGGER_ID, mon.events.CALL,
                                         lambda *a: None))
mon.free_tool_id(mon.DEBUGGER_ID)
print("freed:", mon.get_tool(mon.DEBUGGER_ID))
for bad in (9, -1):
    try:
        mon.get_tool(bad)
    except ValueError as exc:
        print("bad id:", exc)
