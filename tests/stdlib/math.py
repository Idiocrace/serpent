# COVERAGE: the integer-preserving rounders (floor/ceil/trunc) over ints,
# floats, bools and objects with PEP 3141's dunders -- including the two
# bundled real-number types, Fraction and Decimal; gcd and lcm over
# machine-word AND big integers, both signs and both zeroes; isqrt,
# factorial, comb, perm; the float predicates (isfinite/isinf/isnan),
# isclose, fsum, prod, dist, hypot; the transcendentals to the precision
# both sides print; the constants; and the TypeErrors.
#
# THE BIG-INTEGER CASES ARE THE POINT OF HALF OF THIS FILE. `gcd` and
# `lcm` read a machine word off their arguments, which is a POINTER when
# the argument outgrew one -- `gcd(2**100, 2**60)` answered 8 in a
# compiled build and the right answer under the interpreter, so the two
# arrangements disagreed and nothing said so. Same for the rounders and a
# class with `__floor__`: the interpreter and both compiled runtimes each
# had their own copy of "what is a real number", and all three had to
# learn the same answer.
import math

# --- the integer-preserving rounders ----------------------------------
print("floor:", math.floor(2.7), math.floor(-2.7), math.floor(2.0))
print("ceil: ", math.ceil(2.1), math.ceil(-2.1), math.ceil(2.0))
print("trunc:", math.trunc(2.7), math.trunc(-2.7), math.trunc(0.5))
print("ints pass through:", math.floor(5), math.ceil(5), math.trunc(5))
print("bools become ints:", math.floor(True), math.ceil(True),
      math.trunc(False))
print("they answer int, not float:",
      isinstance(math.floor(2.7), int), isinstance(math.floor(2.7), float))
big = 10 ** 30
print("a big passes through:", math.floor(big) == big,
      math.ceil(-big) == -big)
print("--- rounders done ---")


# --- PEP 3141's hooks -------------------------------------------------
class Rounded:
    def __floor__(self):
        return -7

    def __ceil__(self):
        return 7

    def __trunc__(self):
        return 0


hooked = Rounded()
print("a class's own hooks:", math.floor(hooked), math.ceil(hooked),
      math.trunc(hooked))


class OnlyFloor:
    def __floor__(self):
        return 1


print("one hook alone:", math.floor(OnlyFloor()))
try:
    math.ceil(OnlyFloor())
except TypeError:
    print("and the others still refuse")


class NoHooks:
    pass


try:
    math.floor(NoHooks())
except TypeError:
    print("a plain object is a TypeError")
try:
    math.floor("2.5")
except TypeError:
    print("a str is a TypeError")
print("--- hooks done ---")


# --- the two bundled real numbers -------------------------------------
from fractions import Fraction
from decimal import Decimal

for f in (Fraction(7, 2), Fraction(-7, 2), Fraction(4, 2), Fraction(0, 5)):
    print("Fraction", f, "->", math.floor(f), math.ceil(f), math.trunc(f))
for d in (Decimal("3.5"), Decimal("-3.5"), Decimal("4"), Decimal("0")):
    print("Decimal", d, "->", math.floor(d), math.ceil(d), math.trunc(d))
print("--- real numbers done ---")


# --- gcd and lcm, in machine words ------------------------------------
print("gcd:", math.gcd(12, 18), math.gcd(18, 12), math.gcd(17, 5))
print("with zero:", math.gcd(0, 5), math.gcd(5, 0), math.gcd(0, 0))
print("negatives:", math.gcd(-12, 18), math.gcd(12, -18),
      math.gcd(-12, -18))
print("equal:", math.gcd(9, 9), "one:", math.gcd(1, 999))
print("lcm:", math.lcm(4, 6), math.lcm(21, 6), math.lcm(0, 5),
      math.lcm(0, 0))
print("lcm negatives:", math.lcm(-4, 6), math.lcm(4, -6))
print("--- gcd small done ---")


# --- gcd and lcm, in big integers -------------------------------------
print("powers of two:", math.gcd(2 ** 100, 2 ** 60) == 2 ** 60)
print("a big and a word:", math.gcd(10 ** 30, 30), math.gcd(30, 10 ** 30))
print("two bigs:",
      math.gcd(123456789012345678901234567890,
               987654321098765432109876543210))
print("coprime bigs:", math.gcd(2 ** 89 - 1, 2 ** 107 - 1))
print("a big with itself:", math.gcd(10 ** 40, 10 ** 40) == 10 ** 40)
print("a big and zero:", math.gcd(10 ** 40, 0) == 10 ** 40,
      math.gcd(0, 10 ** 40) == 10 ** 40)
print("negative bigs:", math.gcd(-(10 ** 30), 10 ** 20) == 10 ** 20)
print("lcm of bigs:", math.lcm(10 ** 30, 30) == 10 ** 30)
print("lcm growing past a word:", math.lcm(2 ** 40, 3 ** 30)
      == 2 ** 40 * 3 ** 30)
print("lcm of two bigs:",
      math.lcm(2 ** 70, 3 ** 50) == 2 ** 70 * 3 ** 50)
try:
    math.gcd(1.5, 2)
except TypeError:
    print("a float is a TypeError")
print("--- gcd big done ---")


# --- the other integer functions --------------------------------------
print("isqrt:", math.isqrt(0), math.isqrt(1), math.isqrt(99),
      math.isqrt(100))
print("isqrt big:", math.isqrt(10 ** 40) == 10 ** 20)
print("factorial:", math.factorial(0), math.factorial(1), math.factorial(5))
print("factorial big:", math.factorial(25) == 15511210043330985984000000)
print("comb:", math.comb(5, 2), math.comb(5, 0), math.comb(5, 5))
print("perm:", math.perm(5, 2), math.perm(5, 0))
print("--- integers done ---")


# --- floats -----------------------------------------------------------
print("predicates:", math.isfinite(1.0), math.isinf(float("inf")),
      math.isnan(float("nan")))
print("isclose:", math.isclose(1.0, 1.0 + 1e-12),
      math.isclose(1.0, 1.1), math.isclose(1.0, 1.1, rel_tol=0.2))
print("fsum:", math.fsum([0.1] * 10))
print("prod:", math.prod([1, 2, 3, 4]), math.prod([], start=5))
print("hypot:", math.hypot(3.0, 4.0))
print("dist:", math.dist([0.0, 0.0], [3.0, 4.0]))
print("sqrt:", math.sqrt(16.0), "pow:", math.pow(2.0, 10.0))
print("exp/log:", round(math.exp(1.0), 10), round(math.log(math.e), 10))
print("log base:", round(math.log(8, 2), 10), round(math.log10(1000), 10))
print("trig:", round(math.sin(0.0), 10), round(math.cos(0.0), 10))
print("degrees/radians:", math.degrees(math.pi), round(math.radians(180), 10))
print("fabs/fmod:", math.fabs(-2.5), math.fmod(7.0, 3.0))
print("copysign:", math.copysign(3.0, -1.0))
print("--- floats done ---")


# --- the constants ----------------------------------------------------
print("pi:", round(math.pi, 12))
print("e:", round(math.e, 12))
print("tau:", round(math.tau, 12))
print("inf/nan:", math.isinf(math.inf), math.isnan(math.nan))
print("done")


# --- the last two -----------------------------------------------------
print("fma:", math.fma(2.0, 3.0, 4.0))
print("fma rounds once:", math.fma(1e308, 10.0, -1e309) == float("inf"))
print("sumprod:", math.sumprod([1, 2, 3], [4, 5, 6]))
print("sumprod stays an int:", isinstance(math.sumprod([2], [3]), int))
print("sumprod with floats:", math.sumprod([1.5, 2.5], [2, 2]))
print("sumprod empty:", math.sumprod([], []))
try:
    math.sumprod([1], [1, 2])
except ValueError as exc:
    print("a length mismatch:", exc)
print("all done")
