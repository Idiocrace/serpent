# COVERAGE: load, loads, TOMLDecodeError -- the whole public surface. A
# nontrivial TOML v1.0.0 document below exercises nested tables, an array of
# tables nested two deep, dotted keys (both top-level and inside an inline
# table), an inline table, all four string kinds, integers in all four
# bases, floats including inf/nan, booleans, and arrays laid out across
# several lines with a trailing comma. What is deliberately NOT here is any
# date/time literal: `bundled/tomllib.py` refuses those by name (its own
# docstring explains why), so a document that used one could only ever
# diverge from CPython here, not agree with it.
import tomllib

_BS = chr(92)
_TAB = chr(9)
_DQ = chr(34)

_doc_lines = [
    'title = "TOML Example"',
    "",
    "[owner]",
    'name = "Tom Preston-Werner"',
    'bio = """',
    "Multi-line basic string with a " + _DQ + "quote" + _DQ
    + " and a tab" + _TAB + "here.",
    '"""',
    "",
    "[database]",
    "enabled = true",
    "ports = [ 8000, 8001,",
    "          8002, ]",
    'data = [ ["delta", "phi"], [3.14] ]',
    "temp_targets = { cpu = 79.5, case = 72.0 }",
    "point = { x.a = 1, x.b = 2 }",  # a dotted key inside an inline table
    "",
    "[servers]",
    "",
    "[servers.alpha]",
    'ip = "10.0.0.1"',
    'role = "frontend"',
    "",
    "[servers.beta]",
    'ip = "10.0.0.2"',
    'role = "backend"',
    "",
    "[misc]",
    'physical.color = "orange"',
    'physical.shape = "round"',
    'site."google.com" = true',
    "",
    # A four-hex and an eight-hex unicode escape, plus an ordinary letter
    # escape (tab) right next to them in the same basic string.
    "unicode_short = " + _DQ + "e-acute:" + _BS + "u00e9,tab:" + _BS + "t."
    + _DQ,
    "unicode_long = " + _DQ + "grinning face:" + _BS + "U0001F600." + _DQ,
    "",
    "literal_single = 'C:" + _BS + "Users" + _BS + "nobody" + _BS + "templates'",
    "literal_multi = '''",
    "line one",
    'line "two"',
    "'''",
    "",
    "int_dec = 1_000",
    "int_hex = 0xDEAD_BEEF",
    "int_oct = 0o755",
    "int_bin = 0b1010_1010",
    "",
    "flt_normal = 6.62e-34",
    "flt_pos_inf = +inf",
    "flt_neg_inf = -inf",
    "flt_nan = nan",
    "",
    "[[fruit]]",
    'name = "apple"',
    "",
    "[fruit.physical]",
    'color = "red"',
    'shape = "round"',
    "",
    "[[fruit.variety]]",
    'name = "red delicious"',
    "",
    "[[fruit.variety]]",
    'name = "granny smith"',
    "",
    "[[fruit]]",
    'name = "banana"',
    "",
    "[[fruit.variety]]",
    'name = "plantain"',
    "",
]
DOC = "\n".join(_doc_lines)

data = tomllib.loads(DOC)

# THE WHOLE STRUCTURE, printed at once -- this is the broadest single check
# available: every table, array-of-tables, string kind, number base and
# float special value has to come out in the right place and the right
# Python type for this one line to match the oracle.
print(data)

# ---- individual values, so a divergence buried in the dict above has a
# narrower line to point at -------------------------------------------------
print(data["title"])
print(repr(data["owner"]["bio"]))
print(type(data["database"]["enabled"]).__name__, data["database"]["enabled"])
print(data["database"]["ports"])
print(data["database"]["data"])
print(data["database"]["temp_targets"])
print(data["database"]["point"])
print(data["servers"]["alpha"]["ip"], data["servers"]["beta"]["role"])

print(data["misc"]["physical"], data["misc"]["site"])
print(repr(data["misc"]["unicode_short"]))
print(repr(data["misc"]["unicode_long"]))
print(len(data["misc"]["unicode_long"]))  # a non-BMP escape is ONE character
print(repr(data["misc"]["literal_single"]))
print(repr(data["misc"]["literal_multi"]))

print(data["misc"]["int_dec"], data["misc"]["int_hex"],
      data["misc"]["int_oct"], data["misc"]["int_bin"])
print(type(data["misc"]["int_hex"]).__name__)

print(data["misc"]["flt_normal"])
print(data["misc"]["flt_pos_inf"], data["misc"]["flt_neg_inf"],
      data["misc"]["flt_nan"])
print(data["misc"]["flt_pos_inf"] == float("inf"))
print(data["misc"]["flt_neg_inf"] == float("-inf"))
print(data["misc"]["flt_nan"] != data["misc"]["flt_nan"])  # NaN, by definition

print(len(data["fruit"]))
print(data["fruit"][0]["name"], data["fruit"][0]["physical"])
print([v["name"] for v in data["fruit"][0]["variety"]])
print(data["fruit"][1]["name"], [v["name"] for v in data["fruit"][1]["variety"]])

# ---- parse_float ------------------------------------------------------------
# The default is `float`; a custom one receives the matched text VERBATIM,
# underscores included, and its result is what ends up in the tree -- this
# is the hook decimal.Decimal would use if `decimal` were bundled.
print(tomllib.loads("x = 3.14\n", parse_float=str))
print(tomllib.loads("x = 1_000.5\n", parse_float=str))

try:
    tomllib.loads("x = 1.5\n", parse_float=lambda text: {"boom": text})
    print("ACCEPTED a dict-returning parse_float")
except ValueError:
    print("rejected: parse_float returning a dict")

# ---- load(), a binary file object -------------------------------------------
# `io` is not bundled yet (`docs/STDLIB.md`), so this is the smallest thing
# with a `.read()` returning bytes -- exactly what `load` asks its argument
# for, and nothing io.BytesIO would add for this purpose.


class _FakeBinaryFile:
    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data


print(tomllib.load(_FakeBinaryFile(b"answer = 42\n")))

try:
    tomllib.load(_FakeBinaryFile("answer = 42\n"))  # str, not bytes
    print("ACCEPTED a text-mode file")
except TypeError:
    print("rejected: load() given a str instead of bytes")

# ---- malformed documents -----------------------------------------------------
# Each of these is valid-looking TOML that is not valid TOML -- the ordinary
# mistake CPython also refuses, which is what makes it a differential check
# rather than a check of this module's own opinion.
print("TOMLDecodeError is a ValueError:",
      issubclass(tomllib.TOMLDecodeError, ValueError))

_bad_docs = {
    "duplicate key": "dup = 1\ndup = 2\n",
    "unterminated basic string": 'bad = "unterminated\n',
    "duplicate table header": "[a]\n[a]\n",
    "dotted key redefines a table": "[a]\nb = 1\n[a.b]\nc = 2\n",
    "duplicate inline table key": "t = { x = 1, x = 2 }\n",
    "trailing comma in inline table": "t = { x = 1, }\n",
    "unclosed array": "a = [1, 2\n",
}
for label, bad in _bad_docs.items():
    try:
        tomllib.loads(bad)
        print("ACCEPTED", label)
    except tomllib.TOMLDecodeError:
        print("rejected:", label)

# The duplicate-key case above is small enough that its exact position is
# worth pinning down, not just its type -- `pos`/`lineno`/`colno` are
# documented attributes and this checks them rather than just their names.
try:
    tomllib.loads("dup = 1\ndup = 2\n")
except tomllib.TOMLDecodeError as exc:
    print(exc.pos, exc.lineno, exc.colno)

print("done")
