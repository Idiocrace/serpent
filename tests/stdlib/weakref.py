# COVERAGE: ref(obj), ref(obj, callback), calling a ref, the interning of
# callback-free refs, __eq__/__hash__, the callback receiving the ref
# itself, and getweakrefcount -- the whole module (proxy, finalize,
# WeakValueDictionary, WeakKeyDictionary and WeakSet are refused BY NAME,
# see the module docstring).
import weakref


class Foo:
    def __init__(self, name):
        self.name = name

    def __del__(self):
        print("del", self.name)


# --- a live ref, then the referent goes away --------------------------
def alive_then_dead():
    a = Foo("a")
    r = weakref.ref(a)
    print(r() is a)
    print(r() is None)
    del a
    print("after del a:", r() is None)


alive_then_dead()
print("--- alive_then_dead done ---")


def deref_gives_the_object_back():
    a = Foo("a2")
    r = weakref.ref(a)
    got = r()
    print("deref answers the object:", got.name, got is a)


deref_gives_the_object_back()
print("--- deref_gives_the_object_back done ---")


# --- the callback fires, with the ref itself as its argument ----------
def callback_fires():
    seen = []

    def on_die(weak):
        seen.append(weak() is None)
        print("callback ran, ref now dead:", weak() is None)

    b = Foo("b")
    rb = weakref.ref(b, on_die)
    print("callback saw the ref itself:", rb is not None)
    del b
    print("after del b, seen:", seen)


callback_fires()
print("--- callback_fires done ---")


# --- callback-free refs are interned, refs with callbacks are not -----
def interning():
    c = Foo("c")
    r1 = weakref.ref(c)
    r2 = weakref.ref(c)
    print("interned:", r1 is r2)
    print("count:", weakref.getweakrefcount(c))
    r3 = weakref.ref(c, lambda w: None)
    print("with callback is separate:", r3 is r1)
    print("count now:", weakref.getweakrefcount(c))
    del c


interning()
print("--- interning done ---")


# --- equality and hash -------------------------------------------------
def equality_and_hash():
    d = Foo("d")
    e = Foo("e")
    rd = weakref.ref(d)
    rd_again = weakref.ref(d)
    re_ = weakref.ref(e)
    print(rd == rd_again, rd == re_)
    print(hash(rd) == hash(d))
    print(hash(rd) == hash(rd_again))
    del d
    del e


equality_and_hash()
print("--- equality_and_hash done ---")


# --- a ref to something that cannot have one ---------------------------
try:
    weakref.ref(5)
except TypeError as exc:
    print("TypeError:", "cannot create weak reference" in str(exc))

def count_of_unreferenced():
    z = Foo("z")
    print("count of a never-referenced object:", weakref.getweakrefcount(z))


count_of_unreferenced()
print("--- count_of_unreferenced done ---")


# --- a referent that was passed into a call ----------------------------
#
# THE SHAPE A WEAKREF IS ACTUALLY WRITTEN IN. `weakref.ref(obj)` is
# itself a call, and so is every method call and every constructor, so a
# referent that goes dead only after the LAST NAME for it is dropped is
# the whole test: an argument still counted by whoever was called would
# keep the referent answering long after `del`.
def looked_at(o):
    return o.name


def passed_around():
    p = Foo("p")
    r = weakref.ref(p)
    print("read through a call:", looked_at(p))
    print("alive while named:", r() is not None)
    del p
    print("dead once the name is gone:", r() is None)


passed_around()
print("--- passed_around done ---")


def through_a_container():
    q = Foo("q")
    r = weakref.ref(q)
    held = [q]
    del q
    print("still held by the list:", r() is not None)
    held.clear()
    print("dead once the list lets go:", r() is None)


through_a_container()
print("done")
