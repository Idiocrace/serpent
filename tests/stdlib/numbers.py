# COVERAGE: `Number`, `Complex`, `Real`, `Rational`, `Integral`, the real
# hierarchy between them, `int` and `float` registered up through the whole
# tower, abstract-method enforcement on a subclass, the mixin methods
# (`Rational.__float__`, `Integral.numerator`/`.denominator`/`__index__`),
# and a user-defined class registered structurally via `.register`.
#
# `complex` DOES NOT APPEAR as a value checked against `numbers.Complex`.
# `numbers.py` registers it, matching CPython, but `complex` cannot be named
# as a genuine class value in this frontend -- it compiles to a callable
# thunk rather than the type object `type(3+4j)` answers with, so
# `isinstance(3+4j, numbers.Complex)` answers False here where CPython
# answers True. Measured, not assumed: `type(3+4j) is complex` alone already
# answers False. See the module's docstring. `range`, `bytearray` and
# `memoryview` were the same shape of gap in `collections.abc`.
import numbers

# ---- isinstance against the builtins, up the whole tower -------------------
print(isinstance(3, numbers.Integral), isinstance(3, numbers.Rational),
      isinstance(3, numbers.Real), isinstance(3, numbers.Complex),
      isinstance(3, numbers.Number))
print(isinstance(3.0, numbers.Integral), isinstance(3.0, numbers.Rational),
      isinstance(3.0, numbers.Real), isinstance(3.0, numbers.Complex),
      isinstance(3.0, numbers.Number))

# ---- issubclass against the builtins ----------------------------------------
print(issubclass(int, numbers.Integral), issubclass(int, numbers.Rational),
      issubclass(int, numbers.Real), issubclass(int, numbers.Number))
# `float` IS NOT Rational or Integral -- CPython registers it with `Real`
# only, deliberately: floats do not interoperate as exact ratios.
print(issubclass(float, numbers.Rational), issubclass(float, numbers.Integral))
print(issubclass(float, numbers.Real), issubclass(float, numbers.Number))

# ---- the class hierarchy itself ---------------------------------------------
print(issubclass(numbers.Integral, numbers.Rational),
      issubclass(numbers.Rational, numbers.Real),
      issubclass(numbers.Real, numbers.Complex),
      issubclass(numbers.Complex, numbers.Number))
# THE WRONG DIRECTION, checked explicitly: a Real is not a Rational and a
# Number is not a Complex -- the tower only narrows one way.
print(issubclass(numbers.Real, numbers.Rational),
      issubclass(numbers.Number, numbers.Complex))

# ---- the module surface -----------------------------------------------------
print(sorted([numbers.Number.__name__, numbers.Complex.__name__,
             numbers.Real.__name__, numbers.Rational.__name__,
             numbers.Integral.__name__]))

# ---- abstract-method enforcement --------------------------------------------
class Incomplete(numbers.Integral):
    pass


try:
    Incomplete()
except TypeError as e:
    print("incomplete refused:", "abstract" in str(e))

# ---- a concrete Integral, exercising the mixins -----------------------------
class MyInt(numbers.Integral):
    def __init__(self, value):
        self.value = value

    def __int__(self):
        return self.value

    def __eq__(self, other):
        return int(self) == int(other)

    def __add__(self, other):
        return MyInt(int(self) + int(other))

    def __radd__(self, other):
        return MyInt(int(other) + int(self))

    def __neg__(self):
        return MyInt(-int(self))

    def __pos__(self):
        return MyInt(+int(self))

    def __mul__(self, other):
        return MyInt(int(self) * int(other))

    def __rmul__(self, other):
        return MyInt(int(other) * int(self))

    def __truediv__(self, other):
        return int(self) / int(other)

    def __rtruediv__(self, other):
        return int(other) / int(self)

    def __floordiv__(self, other):
        return MyInt(int(self) // int(other))

    def __rfloordiv__(self, other):
        return MyInt(int(other) // int(self))

    def __mod__(self, other):
        return MyInt(int(self) % int(other))

    def __rmod__(self, other):
        return MyInt(int(other) % int(self))

    def __lt__(self, other):
        return int(self) < int(other)

    def __le__(self, other):
        return int(self) <= int(other)

    def __abs__(self):
        return MyInt(abs(int(self)))

    def conjugate(self):
        return self

    def __pow__(self, exponent, modulus=None):
        if modulus is None:
            return MyInt(int(self) ** int(exponent))
        return MyInt(pow(int(self), int(exponent), int(modulus)))

    def __rpow__(self, base):
        return MyInt(int(base) ** int(self))

    def __lshift__(self, other):
        return MyInt(int(self) << int(other))

    def __rlshift__(self, other):
        return MyInt(int(other) << int(self))

    def __rshift__(self, other):
        return MyInt(int(self) >> int(other))

    def __rrshift__(self, other):
        return MyInt(int(other) >> int(self))

    def __and__(self, other):
        return MyInt(int(self) & int(other))

    def __rand__(self, other):
        return MyInt(int(other) & int(self))

    def __xor__(self, other):
        return MyInt(int(self) ^ int(other))

    def __rxor__(self, other):
        return MyInt(int(other) ^ int(self))

    def __or__(self, other):
        return MyInt(int(self) | int(other))

    def __ror__(self, other):
        return MyInt(int(other) | int(self))

    def __invert__(self):
        return MyInt(~int(self))

    def __trunc__(self):
        return self

    def __floor__(self):
        return self

    def __ceil__(self):
        return self

    def __round__(self, ndigits=None):
        return self


m = MyInt(7)
print(isinstance(m, numbers.Integral), isinstance(m, numbers.Rational))
print(isinstance(m, numbers.Real), isinstance(m, numbers.Complex))
print(int(m.numerator), m.denominator, m.__index__())
print(int(m + 3), int(3 + m), int(m * 2), int(-m))
print(float(m))

# ---- a user class NEVER TOLD ABOUT `numbers`, registered from outside ------
class ThirdPartyInt:
    def __init__(self, value):
        self.value = value

    def __int__(self):
        return self.value


print(isinstance(ThirdPartyInt(5), numbers.Integral))
numbers.Integral.register(ThirdPartyInt)
print(isinstance(ThirdPartyInt(5), numbers.Integral))
print(issubclass(ThirdPartyInt, numbers.Integral))
# REGISTRATION IS NOT INHERITANCE: nothing about ThirdPartyInt changed, so it
# still has none of the mixin methods.
print(hasattr(ThirdPartyInt, "numerator"))

# A `bool` IS AN `int`, and the tower has to say so at every level.
print(isinstance(True, numbers.Integral), isinstance(False, numbers.Rational))
print(isinstance(True, numbers.Real), isinstance(True, numbers.Complex))
print(isinstance(True, numbers.Number), isinstance("x", numbers.Number))
print(issubclass(bool, numbers.Integral), issubclass(str, numbers.Number))
