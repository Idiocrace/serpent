# COVERAGE: pack, unpack, pack_into, unpack_from, calcsize, iter_unpack,
# error, and the Struct class. Byte-order prefixes '<' '>' '!' '=' (all four
# STANDARD, unpadded -- '!' is '>' under another name, '=' is native which is
# little-endian on every real target this compiler produces). Type codes
# x c b B h H i I l L q Q f d s ?, with repeat counts (3i, 10x, 10s) and
# whitespace between fields.
#
# NOT covered, each refused BY NAME rather than a wrong answer: '@' (native
# size/alignment -- genuinely platform-specific) and a format with no prefix
# at all (CPython's own default IS '@'), 'e' (half float), 'p' (Pascal
# string), 'n'/'N'/'P' (native ssize_t/size_t/pointer, meaningful only under
# '@'). A differential test cannot exercise those refusals -- CPython has
# every one of them, so the two runtimes would only ever disagree -- so they
# are not attempted here; see the module docstring in bundled/struct.py.
import struct

# ---- integers, both byte orders, negative numbers, and the width boundaries
for code, lo, hi in [
    ("b", -128, 127),
    ("B", 0, 255),
    ("h", -32768, 32767),
    ("H", 0, 65535),
    ("i", -2147483648, 2147483647),
    ("I", 0, 4294967295),
    ("l", -2147483648, 2147483647),
    ("L", 0, 4294967295),
    ("q", -9223372036854775808, 9223372036854775807),
    ("Q", 0, 18446744073709551615),
]:
    for order in ("<", ">"):
        packed_lo = struct.pack(order + code, lo)
        packed_hi = struct.pack(order + code, hi)
        print(code, order, packed_lo, packed_hi,
              struct.unpack(order + code, packed_lo),
              struct.unpack(order + code, packed_hi))

# The same width in each order disagrees byte for byte, except for one byte.
print(struct.pack("<I", 0x01020304).hex())
print(struct.pack(">I", 0x01020304).hex())
print(struct.pack("!I", 0x01020304) == struct.pack(">I", 0x01020304))
print(struct.pack("=I", 0x01020304) == struct.pack("<I", 0x01020304))

# ---- x (pad byte), c, ? ------------------------------------------------
print(struct.pack("<2x"))
print(struct.pack("<b2xb", 1, 2))
print(struct.unpack("<b2xb", struct.pack("<b2xb", 1, 2)))
print(struct.pack("<c", b"A"), struct.unpack("<c", b"A"))
print(struct.pack("<3?", True, False, 1))
print(struct.unpack("<3?", struct.pack("<3?", True, False, 1)))
print(type(struct.unpack("<?", b"\x01")[0]))

# ---- s: a fixed-size bytes field, not repetition ------------------------
print(struct.pack("<10s", b"hello"))
print(struct.unpack("<10s", struct.pack("<10s", b"hello")))
print(struct.pack("<5s", b"hello world"))          # truncated to 5
print(struct.pack("<0s", b""))
print(struct.calcsize("<0s"))
# 's' accepts a bytearray where 'c' does not -- see the module docstring.
print(struct.pack("<5s", bytearray(b"ab")))

# ---- f and d: IEEE-754 pack/unpack, exact and rounded --------------------
for value in [0.0, -0.0, 1.5, -2.5, 3.14159265358979, 1e10, -1e10,
              1e300, -1e300, 1e-300, 5e-324, 1.7976931348623157e308,
              2.2250738585072014e-308]:
    d = struct.pack("<d", value)
    print(value, struct.unpack("<d", d))
print(struct.unpack("<f", struct.pack("<f", 1.5)))
print(struct.unpack("<f", struct.pack("<f", 3.14159265)))
print(struct.pack("<d", -0.0).hex())
print(struct.unpack("<d", struct.pack("<d", float("inf"))))
print(struct.unpack("<d", struct.pack("<d", float("-inf"))))
print(struct.unpack("<d", struct.pack("<d", float("nan"))))
try:
    struct.pack("<f", 1e300)
except OverflowError as e:
    print("f overflow:", str(e))

# ---- multi-value formats ---------------------------------------------
packed = struct.pack("<ihq", 7, -2, 300000000000)
print(packed, struct.unpack("<ihq", packed))
print(struct.pack("<3i 2h", 1, 2, 3, 4, 5) ==
      struct.pack("<3i2h", 1, 2, 3, 4, 5))

# ---- calcsize -----------------------------------------------------------
print(struct.calcsize("<i"), struct.calcsize(">3i"), struct.calcsize("<10s"))
print(struct.calcsize("<ihq"), struct.calcsize(""))

# ---- the Struct class --------------------------------------------------
s = struct.Struct("<3ihq")
print(s.format, s.size)
packed = s.pack(1, 2, 3, -4, 5)
print(packed)
print(s.unpack(packed))

# ---- pack_into / unpack_from with an offset into a LARGER buffer --------
buf = bytearray(16)
struct.pack_into("<i", buf, 4, 0x11223344)
struct.pack_into("<i", buf, 8, -99)
print(bytes(buf))
print(struct.unpack_from("<i", buf, 4))
print(struct.unpack_from("<i", buf, 8))
print(struct.unpack_from("<i", buf, -8))          # negative offset, from the end

# ---- iter_unpack over several fixed-size records ------------------------
records = struct.pack("<3i", 10, 20, 30)
print(list(struct.iter_unpack("<i", records)))
pairs = struct.pack("<2ih", 1, -1, 5) + struct.pack("<2ih", 2, -2, 6)
print(list(struct.iter_unpack("<2ih", pairs)))

# ---- errors: an out-of-range value raises struct.error -------------------
try:
    struct.pack("<B", 300)
except struct.error as e:
    print("B overflow:", str(e))
try:
    struct.pack("<b", -200)
except struct.error as e:
    print("b overflow:", str(e))
try:
    struct.pack("<h", 70000)
except struct.error as e:
    print("h overflow:", str(e))
try:
    struct.pack("<Q", -1)
except struct.error as e:
    print("Q negative:", str(e))
try:
    struct.pack("<i")
except struct.error as e:
    print("too few:", str(e))
try:
    struct.pack("<i", 1, 2)
except struct.error as e:
    print("too many:", str(e))
try:
    struct.pack("<c", b"AB")
except struct.error as e:
    print("bad char:", str(e))
try:
    struct.pack("<c", bytearray(b"A"))
except struct.error as e:
    print("bytearray for c refused:", str(e))
try:
    struct.pack("<5s", "hi")
except struct.error as e:
    print("bad s:", str(e))
try:
    struct.unpack("<i", b"ab")
except struct.error as e:
    print("unpack size:", str(e))
try:
    struct.unpack_from("<i", b"ab")
except struct.error as e:
    print("unpack_from size:", str(e))
try:
    struct.pack_into("<i", bytearray(2), 0, 5)
except struct.error as e:
    print("pack_into size:", str(e))
try:
    struct.iter_unpack("<i", b"abcde")
except struct.error as e:
    print("iter_unpack size:", str(e))
try:
    struct.iter_unpack("", b"abc")
except struct.error as e:
    print("iter_unpack zero:", str(e))
try:
    struct.calcsize("<3")
except struct.error as e:
    print("dangling count:", str(e))
try:
    struct.calcsize("<z")
except struct.error as e:
    print("bad code:", str(e))

# `@` and the codes it alone offers ('e', 'n', 'N', 'p', 'P', and no prefix
# at all) are refused BY NAME -- see the module docstring. CPython supports
# every one of them, so a differential test structurally cannot exercise
# that refusal without the two runtimes only ever disagreeing; it is not
# attempted here.
