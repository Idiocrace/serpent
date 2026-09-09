"""`typing`'s runtime -- the part of the module that actually DOES something.

COVERAGE: `TypeVar` (construction, `__name__`, `__bound__`, `__constraints__`,
`__covariant__`/`__contravariant__`, `repr`); `Generic` with a real
`__class_getitem__` -- `class Box(Generic[T])` then `Box[int]` answers an
object with genuine `.__origin__`/`.__args__` attributes; `NewType` (a real
identity-wrapping callable, with `__name__` and `__supertype__`); `cast` (a
real no-op passthrough); `overload` (a real decorator -- see below for why it
needs almost no machinery); `Protocol` + `runtime_checkable`, structural
`isinstance` checking built the same way `bundled/abc.py` builds one;
`get_type_hints`, built on the now-bundled `annotationlib.get_annotations`;
`NamedTuple` and `TypedDict`, but ONLY THE FUNCTIONAL FORM -- see below for
why the class-based form is refused rather than silently wrong.

EVERYTHING ELSE `typing` NAMES -- `Any`, `Union`, `Optional`, `Callable`,
`Literal`, the container aliases, `Annotated`, `ParamSpec`, `Required` and
the rest of PEP 484's annotation-only vocabulary, plus `final`, `override`,
`no_type_check`, `get_origin` and `get_args` -- stays exactly where it was:
`frontends/python/modules.py`'s native `_TYPING` table. Those names are
markers a program writes in an annotation and, mostly, never inspects at
run time -- CPython gives most of them no runtime behaviour either, so
reimplementing them here would be inventing behaviour CPython itself does
not have. This module does not redefine any of them, and `import typing`
still reaches the native table for whichever half of the name this file
does not define -- see `bundled.py`'s own note that `typing` is "bundled IN
PART", written before this file existed, for exactly this arrangement.

## Precedence: a bundled member always wins over the native table entry

`bundled.py`'s `splice()` decides, name by name, whether `typing.X` points at
something this file defines or at the native `_TYPING` table: `_Rewrite`
checks `X in members["typing"]` -- the names THIS FILE defines -- before it
ever asks `modules.resolve("typing")` about the native table. So defining
`Generic`, `Protocol`, `NamedTuple`, `TypedDict`, `TypeVar`, `NewType`,
`cast`, `overload`, `runtime_checkable` or `get_type_hints` here makes every
reference to that name -- `typing.X`, `from typing import X` -- resolve HERE
instead, automatically, with no change needed to `modules.py`'s `_TYPING`
table at all: the entries there for these same names simply stop being
reached. Checked by reading `splice()`'s `_Rewrite.visit_Attribute` and the
`ImportFrom` handling in `splice()` itself, both of which test bundled
membership first and only fall back to `_resolve()` -- the native table --
for a name this file does NOT define. The `import typing` statement itself
also survives the splice (`_resolve("typing") is not None` keeps it), which
is what lets the untouched half of the name -- `typing.Optional` and the
rest -- keep resolving through the native path exactly as before.

## Why the class-based `NamedTuple`/`TypedDict` form is refused

CPython builds both from a class body: `class Point(NamedTuple): x: int`
works because `NamedTupleMeta.__new__` (or, in 3.14, a `__mro_entries__`
hook) reads `x`'s annotation out of the class namespace it is handed.
THAT NAMESPACE DOES NOT CARRY IT HERE. A bare annotation with no assigned
value (`x: int`, as opposed to `y: int = 0`) never enters the `ns` dict a
custom metaclass's `__new__` receives -- only names the class body actually
BINDS do. Confirmed by direct probe: a metaclass printing `sorted(ns.keys())`
for `class Point: x: int; y: int = 0` shows only `['y']`. Reading
`cls.__annotations__` immediately after `super().__new__()` inside that same
`__new__` still answers `{}` for BOTH fields -- the PEP 649 thunk that would
answer `{'x': int, 'y': int}` is wired onto the bound class object by the
compiler in a step AFTER the whole `class` statement finishes, keyed to the
name the statement binds; reading it from inside the metaclass call that
produces that very object is too early, every time. Reading the SAME class's
`__annotations__` from OUTSIDE the class statement afterwards answers
correctly -- so the data exists, it is simply invisible to exactly the
mechanism CPython's own `NamedTuple`/`TypedDict` depend on, and a fix would
mean changing how the compiler wires PEP 649 thunks into class construction,
not a change to this module.

A class-based form that happened to work whenever every field carried a
default -- silently dropping annotation-only ones -- is precisely the
"accepted and ignored" shape `docs/STDLIB.md` exists to prevent (see its
`islice`/`frozen=True` examples), so it is refused rather than half-shipped.
The FUNCTIONAL form needs none of this: `NamedTuple('P', [('x', int)])` and
`TypedDict('P', {'x': int})` receive their fields as an ordinary argument,
not by inspecting a class body, and both are fully covered.

## A native-callable `**kwargs`-forwarding gap, found and routed around

`dict(*args, **kwargs)` -- BOTH forwarded together, from inside a function
that collected them -- silently drops every keyword when `dict` resolves to
the builtin constructor value: `_apy_call_spread_kw` (`ir/objects_host.py`)
threads the caller's leftover keywords through as `kwrest` only for a `Func`
or `Class` callee; `_invoke_obj`'s `Native` branch calls `f.body(*given)`
and never reads `kwrest` at all. A plain user function forwarding the same
`*args, **kwargs` to ANOTHER USER FUNCTION is unaffected -- only a builtin
constructor reached this way loses them. `TypedDict`'s functional-form
constructor could have hit this (`dict(*args, **kwargs)`), so it is written
as `dict(**kwargs)` instead -- every real call is keyword-only already, and
the rewrite needs no compiler change. Not fixed here: nothing in this module
needs it once routed around, and the fix belongs in `_invoke_obj`'s `Native`
case for every bundled module, not this one.

## `get_origin`/`get_args` and a user `Generic[T]` subscript

The native `get_origin`/`get_args` (still reached through the untouched
half of `_TYPING`) recognise ONE run-time shape: the alias kind
`runtime/alias.py` builds for `list[int]`, `dict[str, int]` and a union --
unchanged by this file. A `Box[int]` built by THIS module's own
`Generic.__class_getitem__` is an ordinary instance of a plain Python class
(`_GenericAlias`, below), not that native kind, so `get_origin(Box[int])`
answers `None` rather than `Box` -- correct for CPython's own container
aliases, wrong for a user generic. `Box[int].__origin__` and `.__args__` are
real attributes on the object regardless and answer correctly by direct
access; only the two native FUNCTIONS fail to recognise it. Making them
recognise a Python-level object as well as the native kind would mean
rewriting them in this module too, changing already-correct behaviour for
the common case to add a narrower one -- so this is refused BY NAME instead:
`get_origin`/`get_args` on a user `Generic[T]` subscript is not covered.

## `Protocol` covers method-based structural protocols, not attribute ones

The SAME limitation above about annotation-only class members applies here:
a `Protocol` class collects its structural attributes from its own
`cls.__dict__`, which holds a `def area(self): ...` (an ordinary bound
name) correctly, but would never see a bare `x: int` protocol member. Every
protocol this module can check is method-based -- which is the common case
-- and an attribute-only protocol is out of scope for the reason given above
rather than silently checked against nothing.

## `overload`

CPython's own `@overload` at run time is almost inert: the decorated stub
is replaced entirely by the final, undecorated `def` of the same name, so
the decorator's only OBSERVABLE job is to make a body that is somehow still
called directly (a stub reached by accident, or the very last `@overload` in
a stub file with no real implementation following) fail loudly rather than
silently returning `None`. There is no dispatch-by-signature at run time in
CPython either -- that is entirely a static type checker's job -- so this
needs no registry.
"""
import annotationlib
from abc import ABCMeta
from collections import namedtuple


# ── TypeVar ──────────────────────────────────────────────────────────────

class TypeVar:
    """A placeholder for a type in a generic signature.

    NOTHING HERE CHECKS ANYTHING -- exactly as in CPython, a `TypeVar` is a
    marker a type checker reasons about; the constructor's whole run-time
    job is to remember what it was built with.
    """

    def __init__(self, name, *constraints, bound=None, covariant=False,
                 contravariant=False, infer_variance=False):
        self.__name__ = name
        self.__constraints__ = constraints
        self.__bound__ = bound
        self.__covariant__ = covariant
        self.__contravariant__ = contravariant
        self.__infer_variance__ = infer_variance

    def __repr__(self):
        if self.__covariant__:
            prefix = "+"
        elif self.__contravariant__:
            prefix = "-"
        else:
            prefix = "~"
        return prefix + self.__name__


# ── Generic ──────────────────────────────────────────────────────────────

class _GenericAlias:
    """`Box[int]` -- what subscripting a `Generic` subclass answers.

    A PLAIN OBJECT WITH TWO REAL ATTRIBUTES, not the native alias kind
    `list[int]` builds -- see the module docstring for what that costs.
    """

    def __init__(self, origin, args):
        self.__origin__ = origin
        self.__args__ = args

    def __repr__(self):
        names = [getattr(a, "__name__", repr(a)) for a in self.__args__]
        return getattr(self.__origin__, "__name__",
                       repr(self.__origin__)) + "[" + ", ".join(names) + "]"


class Generic:
    """The base a program subclasses to make its own class subscriptable.

    `Generic[T]` USED AS A BASE COLLAPSES TO PLAIN `Generic`: this compiler
    has no `__mro_entries__` (PEP 560), which is what CPython uses to
    substitute a parameterised base for a real one at class-creation time.
    Returning `cls` itself when `cls is Generic` reaches the same class
    statement outcome -- `class Box(Generic[T])` ends up an ordinary
    `class Box(Generic)` -- at the cost of not recording which TypeVar was
    bound; nothing here reads that back, so it is not missed by anything
    this module implements.
    """

    def __class_getitem__(cls, params):
        if cls is Generic:
            return cls
        if not isinstance(params, tuple):
            params = (params,)
        return _GenericAlias(cls, params)


# ── NewType, cast ────────────────────────────────────────────────────────

class NewType:
    """`UserId = NewType("UserId", int)` -- a real identity wrapper.

    CALLING IT ANSWERS THE ARGUMENT UNCHANGED, which is CPython's own
    run-time behaviour: `UserId(5)` is `5`, an `int`, not some wrapped
    value -- the "new type" is a fiction for a type checker only.
    """

    def __init__(self, name, tp):
        self.__name__ = name
        self.__supertype__ = tp

    def __call__(self, x):
        return x


def cast(typ, val):
    """A real no-op: the whole of CPython's own run-time `cast`."""
    return val


def overload(func):
    """Mark a stub as one a real implementation must follow.

    See the module docstring: CPython does no dispatch here either. The
    wrapper exists so that a stub somehow reached directly fails loudly
    instead of returning `None`, which is the one observable behaviour to
    preserve.
    """
    def _overload_dummy(*args, **kwargs):
        raise NotImplementedError(
            "You should not call an overloaded function. "
            "A series of @overload-decorated functions outside a stub "
            "module should always be followed by an implementation that "
            "is not @overload-ed.")
    return _overload_dummy


# ── Protocol ─────────────────────────────────────────────────────────────

#: Names never counted as part of a protocol's structural surface, whether
#: they come from `object`, from `type`'s own machinery, or from the
#: bookkeeping this module and `ABCMeta` add.
_PROTO_SKIP = frozenset((
    "__module__", "__qualname__", "__doc__", "__dict__", "__weakref__",
    "__init__", "__new__", "__class_getitem__", "__subclasshook__",
    "__abstractmethods__", "_is_protocol", "_is_runtime_protocol",
    "__protocol_attrs__", "__parameters__", "__annotations__",
))


def _protocol_attrs(cls):
    """Every method name a `Protocol` (or one it builds on) declares.

    WALKS THE MRO so one protocol extending another still checks the whole
    surface -- but only what a class BODY BINDS, which is `def` and a
    plain assignment; see the module docstring for why a bare-annotation
    attribute member cannot be seen here.
    """
    attrs = set()
    for base in cls.__mro__:
        if base is object or not getattr(base, "_is_protocol", False):
            continue
        for name in base.__dict__:
            if name.startswith("_abc_") or name in _PROTO_SKIP:
                continue
            attrs.add(name)
    return attrs


class _ProtocolMeta(ABCMeta):
    def __new__(mcls, name, bases, ns):
        cls = super().__new__(mcls, name, bases, ns)
        # A DIRECT SUBCLASS OF `Protocol` IS ONE TOO -- checked by NAME
        # rather than by identity, because `Protocol` itself is still being
        # built the one time this runs before that name exists at all.
        cls._is_protocol = any(
            getattr(b, "__name__", None) == "Protocol" for b in bases)
        if cls._is_protocol:
            cls.__protocol_attrs__ = _protocol_attrs(cls)
        return cls

    def __instancecheck__(cls, instance):
        if not getattr(cls, "_is_protocol", False):
            return super().__instancecheck__(instance)
        if not getattr(cls, "_is_runtime_protocol", False):
            raise TypeError(
                "Instance and class checks can only be used with "
                "@runtime_checkable protocols")
        for attr in cls.__protocol_attrs__:
            if not hasattr(instance, attr):
                return False
        return True


class Protocol(metaclass=_ProtocolMeta):
    """A structural interface -- see the module docstring for its scope."""
    _is_runtime_protocol = False


def runtime_checkable(cls):
    """Allow `isinstance`/`issubclass` against a `Protocol` subclass."""
    cls._is_runtime_protocol = True
    return cls


# ── get_type_hints ───────────────────────────────────────────────────────

def get_type_hints(obj, globalns=None, localns=None, include_extras=False):
    """The resolved annotations of a function or class, as real objects.

    BUILT ON `annotationlib.get_annotations`, which is what this runtime's
    PEP 649 thunks were ever able to give -- see `bundled/annotationlib.py`
    for exactly what that covers and refuses. `include_extras` is accepted
    and has nothing to do here: this module does not implement `Annotated`,
    which is the only thing that flag changes.

    A CLASS MERGES ITS WHOLE `__mro__`, reversed so a subclass's own
    annotation wins over a base's -- CPython does the same. Every class here
    is read the ordinary way, through `getattr`, never through a custom
    metaclass's namespace -- so this does NOT hit the limitation the module
    docstring describes for `NamedTuple`/`TypedDict`/`Protocol`: those need
    the data DURING class construction, and this needs it afterwards, which
    is exactly when it is available.
    """
    if isinstance(obj, type):
        hints = {}
        for base in reversed(obj.__mro__):
            ann = annotationlib.get_annotations(
                base, globals=globalns, locals=localns, eval_str=True)
            hints.update(ann)
        return hints
    return annotationlib.get_annotations(
        obj, globals=globalns, locals=localns, eval_str=True)


# ── NamedTuple, functional form only ─────────────────────────────────────

def NamedTuple(typename, fields):
    """`Point = NamedTuple("Point", [("x", int), ("y", int)])`.

    BUILT ON THE NOW-BUNDLED `collections.namedtuple`, exactly as CPython's
    own `typing.NamedTuple` is -- the type annotations decide the field
    ORDER and become `__annotations__`; nothing here checks that a field's
    value actually matches its declared type, which CPython does not either.

    THE CLASS-BASED FORM IS NOT HERE -- see the module docstring for why.
    """
    names = [pair[0] for pair in fields]
    types = {pair[0]: pair[1] for pair in fields}
    made = namedtuple(typename, names)
    made.__annotations__ = types
    return made


# ── TypedDict, functional form only ──────────────────────────────────────

class _TypedDictMeta(type):
    def __call__(cls, **kwargs):
        # `dict(**kwargs)`, DELIBERATELY NOT `dict(*args, **kwargs)` -- see
        # the module docstring for the native-callable kwargs-forwarding gap
        # this sidesteps. Every real TypedDict construction is keyword-only
        # already, so nothing is given up.
        return dict(**kwargs)


class _TypedDictBase(metaclass=_TypedDictMeta):
    pass


def TypedDict(typename, fields, total=True):
    """`Movie = TypedDict("Movie", {"title": str, "year": int})`.

    AT RUN TIME THIS IS A PLAIN `dict`: calling the object this returns
    builds and returns an ordinary `dict`, exactly as CPython's own
    `TypedDict` does -- there is no validation, and none is expected.

    `total` DECIDES ALL KEYS AT ONCE -- `Required`/`NotRequired` on an
    individual field are not consulted (those stay in the native, inert
    half of `typing`), so every key follows the class's own `total`.

    THE CLASS-BASED FORM IS NOT HERE -- see the module docstring for why.
    """
    required = frozenset(fields) if total else frozenset()
    optional = frozenset() if total else frozenset(fields)
    body = {
        "__annotations__": dict(fields),
        "__required_keys__": required,
        "__optional_keys__": optional,
        "__total__": total,
    }
    return _TypedDictMeta(typename, (_TypedDictBase,), body)
