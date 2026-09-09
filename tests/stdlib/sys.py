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
