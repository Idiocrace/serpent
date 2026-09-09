# COVERAGE: collect() -- a two-object cycle, a self-cycle, a three-way
# cycle, an object hanging off a cycle, a cycle that is still referenced
# from outside (and so must NOT be collected), the count it answers, and
# that a second call finds nothing; isenabled(). enable/disable,
# thresholds, get_objects/get_referrers/get_referents/get_stats, debug
# flags, freeze/unfreeze, is_tracked and garbage are refused BY NAME --
# see the module docstring. Plus the two ORDERS a collection has that a
# program can observe, through `weakref`.
import gc
import weakref


class Node:
    def __init__(self, name):
        self.name = name
        self.other = None
        self.extra = None

    def __del__(self):
        print("del", self.name)


# --- refcounting alone cannot collect a cycle -------------------------
def two_way():
    a = Node("a")
    b = Node("b")
    a.other = b
    b.other = a
    print("built two-way")


two_way()
print("survived the scope that made it")
print("collected:", gc.collect())
print("a second pass finds nothing:", gc.collect())
print("--- two_way done ---")


# --- an object referring only to itself -------------------------------
def self_referring():
    s = Node("s")
    s.other = s
    print("built self-cycle")


self_referring()
print("collected:", gc.collect())
print("--- self_referring done ---")


# --- three in a ring, plus something hanging off one of them ----------
def ring_with_hanger():
    x = Node("x")
    y = Node("y")
    z = Node("z")
    x.other = y
    y.other = z
    z.other = x
    x.extra = Node("hanger")
    print("built ring")


ring_with_hanger()
print("collected:", gc.collect())
print("--- ring_with_hanger done ---")


# --- a cycle something OUTSIDE still points at is not garbage ---------
def kept_alive():
    k1 = Node("k1")
    k2 = Node("k2")
    k1.other = k2
    k2.other = k1
    print("built kept cycle")
    print("collected while held:", gc.collect())
    print("both still answer:", k1.name, k1.other.name)
    # Broken by hand so the cycle does not outlive this test, exactly as
    # a program that knows its own shape would do rather than leaving it
    # for the collector.
    k1.other = None
    k2.other = None


kept_alive()
print("--- kept_alive done ---")

print("enabled:", gc.isenabled())
print("done")


# --- a weakref callback for a collected cycle -------------------------
#
# TWO ORDERS CPYTHON DOCUMENTS, and both are things a program can count.
# `gc` clears the weak references to an unreachable set and runs their
# callbacks as ONE PASS, before finalizing and clearing the members -- so
# the callback fires, and `r()` inside it already answers None.
def cycle_with_callback():
    fired = []

    def on_die(w):
        fired.append(w)

    a = Node("wa")
    b = Node("wb")
    a.other = b
    b.other = a
    return weakref.ref(a, on_die), fired


ref_to_cycle, fired_for_cycle = cycle_with_callback()
print("alive before collect:", ref_to_cycle() is not None)
print("collected a watched cycle:", gc.collect() > 0)
print("callback fired:", len(fired_for_cycle))
print("dead after collect:", ref_to_cycle() is None)
print("--- cycle_with_callback done ---")


# And the other way: a `ref` reachable ONLY from the garbage is garbage
# too, and CPython does not invoke a callback it is about to destroy.
inside = []


def ref_inside_the_cycle():
    def on_die(w):
        inside.append(w)

    a = Node("ia")
    b = Node("ib")
    a.other = b
    b.other = a
    a.extra = weakref.ref(b, on_die)


ref_inside_the_cycle()
print("collected:", gc.collect() > 0)
print("callback for a doomed ref fired:", len(inside))
print("--- ref_inside_the_cycle done ---")


# --- an ATTRIBUTE holds a counted reference, so clearing one finalizes ------
#
# `apy_setattr` is on `interpreter._NON_RETAINING` now, which is what retires
# the temporary the store was handed. Without it every attribute-held value
# waited for frame teardown -- late, and visible in exactly this shape.
class Held:
    def __init__(self, tag):
        self.tag = tag

    def __del__(self):
        print("held gone:", self.tag)


class Owner:
    def __init__(self):
        self.child = None


class Guarded:
    def __init__(self):
        self._v = None

    @property
    def v(self):
        return self._v

    @v.setter
    def v(self, value):
        self._v = value


def cleared():
    o = Owner()
    o.child = Held("cleared")
    print("stored")
    o.child = None
    print("after clearing")


cleared()
print("--- cleared ---")


def replaced():
    o = Owner()
    o.child = Held("first")
    o.child = Held("second")
    print("after replacing")


replaced()
print("--- replaced ---")


def owner_dies():
    o = Owner()
    o.child = Held("cascade")
    print("dropping the owner")
    del o
    print("owner dropped")


owner_dies()
print("--- cascade ---")


def through_a_property():
    g = Guarded()
    g.v = Held("property")
    print("stored through the setter")
    g.v = None
    print("cleared through the setter")


through_a_property()
print("--- property ---")
