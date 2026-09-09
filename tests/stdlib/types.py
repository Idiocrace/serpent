# COVERAGE: ModuleType, SimpleNamespace, new_class. NOT covered: FunctionType,
# MethodType, GeneratorType, MappingProxyType, prepare_class -- see the module.
import types

ns = types.SimpleNamespace(a=1, b="two")
print(ns.a, ns.b)
print(ns)
ns.c = 3.5
print(ns.c, ns == types.SimpleNamespace(a=1, b="two", c=3.5))
print(types.SimpleNamespace() == types.SimpleNamespace())
print(types.SimpleNamespace(x=1) == types.SimpleNamespace(x=2))

m = types.ModuleType("made_up")
print(m.__name__)
m.value = 7
print(m.value)

C = types.new_class("C", (), {}, lambda ns: ns.update({"n": 1}))
print(C.__name__, C().n)


class Base:
    def who(self):
        return "base"


D = types.new_class("D", (Base,), {}, lambda ns: ns.update({"who": lambda s: "derived"}))
print(D.__name__, D().who(), issubclass(D, Base))

# `types.GenericAlias` -- `list[int]` as a value. EQUALITY AND HASH, which is
# what makes one usable as a dict key or a set element: two spellings of one
# annotation are one type.
print(list[int] == list[int], hash(list[int]) == hash(list[int]))
print(list[int] == list[str], list[int] == tuple[int], list[int] == list)
print(dict[str, list[int]] == dict[str, list[int]])
print(tuple[int, str] == tuple[str, int])
print(len({list[int], list[int], list[str]}))
print({list[int]: "a"}[list[int]])
print(type(list[int]).__name__, list[int].__origin__, list[int].__args__)

# A UNION'S ARMS ARE ORDER-FREE AND DUPLICATE-FREE, unlike every other
# parameterised form's.
print(int | str)
print(int | str | int)
print((int | str) == (str | int), hash(int | str) == hash(str | int))
print((int | str | int) == (int | str))
print((int | None) == (None | int))
print((int | str) == (int | float))

try:
    hash(list[[]])
except TypeError as exc:
    print("unhashable:", exc)

# THE NAME AND THE REPR ARE THE TWO HALVES OF ONE DOTTED SPELLING: CPython
# keeps the module in `__module__`, prints it in `<class '...'>` and in a
# TypeError, and leaves `__name__` bare.
print(type(list[int]).__name__, type(list[int]))
print(type(int | str).__name__, type(int | str))
for it in (list[int], int | str):
    try:
        it + 1
    except TypeError as exc:
        print(exc)
    try:
        len(it)
    except TypeError as exc:
        print(exc)
