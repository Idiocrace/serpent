# COVERAGE: ascii_lowercase, ascii_uppercase, ascii_letters, digits,
# hexdigits, octdigits, punctuation, printable, whitespace (checked
# character-for-character and in ORDER against a running CPython); capwords
# (default separator, extra whitespace, a custom separator); Template
# (substitute and safe_substitute against a dict and against keyword
# arguments, a dict AND keywords together with keywords winning, a missing
# key raising KeyError vs safe_substitute leaving it untouched, $$ escaping
# to a literal $, ${braced} identifiers, an invalid placeholder raising
# ValueError, is_valid, get_identifiers, and a subclass with its own
# delimiter); Formatter (positional, named, auto-numbered, {0.attr} and
# {0[item]} field access, !r/!s/!a conversions, format specs, a nested spec,
# parse()'s exact tuples including the {{ }} flush quirk, and a subclass
# overriding get_value to see that override actually taken).
import string

# ---- constants --------------------------------------------------------
print(string.ascii_lowercase)
print(string.ascii_uppercase)
print(string.ascii_letters)
print(string.digits)
print(string.hexdigits)
print(string.octdigits)
print(string.punctuation)
print(repr(string.whitespace))
print(repr(string.printable))
print(len(string.ascii_letters), len(string.printable))
print(string.ascii_letters == string.ascii_lowercase + string.ascii_uppercase)
print(string.printable == string.digits + string.ascii_letters
      + string.punctuation + string.whitespace)

# ---- capwords -----------------------------------------------------------
print(string.capwords("  aBc  dEf   ghI "))
print(string.capwords("hello world"))
print(string.capwords("one,two,three", sep=","))
print(string.capwords("a-b-c", "-"))
print(string.capwords(""))

# ---- Template -------------------------------------------------------------
t = string.Template("$who likes $what, and $$ is a dollar. ${who}!")
print(t.substitute(who="Alice", what="pie"))
print(t.substitute({"who": "Bob", "what": "cake"}))
# A DICT AND KEYWORDS TOGETHER -- keywords win on a shared name.
print(t.substitute({"who": "Carl", "what": "tea"}, what="soup"))
print(t.template)

try:
    t.substitute({"who": "Dee"})
except KeyError as e:
    print("substitute missing key:", type(e).__name__, str(e))

safe = string.Template("$known and $missing and ${also_missing}")
print(safe.safe_substitute(known="X"))

bad = string.Template("a $ b")
try:
    bad.substitute()
except ValueError as e:
    print("invalid placeholder:", "Invalid placeholder" in str(e))
print(bad.safe_substitute())
print(bad.is_valid())
print(string.Template("$ok").is_valid())

print(string.Template("$a $b ${c} $a $$").get_identifiers())
print(string.Template("no placeholders here").get_identifiers())


class Pct(string.Template):
    delimiter = "%"


p = Pct("%name scored %score%%")
print(p.substitute(name="Ann", score=90))

# ---- Formatter --------------------------------------------------------
f = string.Formatter()
print(f.format("{} and {} and {}", 1, 2, 3))
print(f.format("{0} {1} {0}", "x", "y"))
print(f.format("{a} loves {b}", a="Ann", b="Bo"))
print(f.format("{}  {} {name}", "auto", "posn", name="kw"))
print(f.format("[{!r}] [{!s}] [{!a}]", "x", "y", "café"))
print(f.format("{:>10}|{:<10}|{:^10}", "r", "l", "c"))
print(f.format("{:08.3f}", 3.14159))
print(f.format("{0.real} {0.imag}", 3 + 4j))
print(f.format("{0[1]} {1[key]}", [10, 20, 30], {"key": "value"}))
print(f.format("{0[key]}", {"key": "value"}))
print(f.format("{:{}}", 42, ">6"))

# `"{}  {} {name}".format(...)` DIRECTLY, to confirm Formatter matches the
# str.format the compiler already knows how to run.
print("{}  {} {name}".format("auto", "posn", name="kw")
      == f.format("{}  {} {name}", "auto", "posn", name="kw"))

try:
    f.format("{0} {1}", "only one")
except IndexError as e:
    print("out of range:", type(e).__name__)

try:
    f.format("{} {0}", 1, 2)
except ValueError as e:
    print("mixed auto/manual:", "automatic" in str(e) or "manual" in str(e))

# `.parse` -- the exact tuples, literal_text/field_name/format_spec/conv.
print(list(f.parse("plain text, no fields")))
print(list(f.parse("{0}")))
print(list(f.parse("a{0}b")))
print(list(f.parse("{} {1} {name}")))
print(list(f.parse("{0.attr}")))
print(list(f.parse("{0[key]}")))
print(list(f.parse("{name!r:>10}")))
print(list(f.parse("{0:{1}}")))
print(list(f.parse("{{literal}}")))
print(list(f.parse("")))

# `.get_field` / `.get_value` / `.convert_field` / `.format_field` directly.
print(f.get_field("0.real", (3 + 4j,), {}))
print(f.get_field("0[1]", ([10, 20, 30],), {}))
print(f.get_value(0, ("a", "b"), {}))
print(f.get_value("x", (), {"x": 9}))
print(f.convert_field("hi", "r"), f.convert_field(5, None))
print(f.format_field(3.5, ".1f"))


class CountingFormatter(string.Formatter):
    """A subclass overriding `get_value`, to prove the override actually
    fires rather than `.format()` running the string through the runtime's
    own `str.format` and skipping this class's own hooks."""

    def __init__(self):
        self.calls = []

    def get_value(self, key, args, kwargs):
        self.calls.append(key)
        return super().get_value(key, args, kwargs)


cf = CountingFormatter()
print(cf.format("{0}-{name}-{0}", "z", name="q"))
print(cf.calls)
