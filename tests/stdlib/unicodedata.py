# COVERAGE: normalize (NFC/NFD/NFKC/NFKD), is_normalized, category, combining,
# decomposition, decimal, digit, numeric. NOT name/lookup (the name table is
# not carried -- see the module's own docstring) or unidata_version/ucd_3_2_0.
import unicodedata

# CATEGORY, over a spread of scripts and kinds: letter, digit, mark, symbol,
# punctuation, separator, control.
for cp in (0x61, 0x41, 0x31, 0x20, 0x2E, 0x21, 0x0301, 0x00E9, 0x4E2D, 0x0000):
    ch = chr(cp)
    print(hex(cp), unicodedata.category(ch))

# COMBINING CLASS -- 0 for a base character, non-zero for a combining mark.
for cp in (0x61, 0x0301, 0x0592):
    print(hex(cp), unicodedata.combining(chr(cp)))

# DECOMPOSITION -- the raw field, empty string when there is none.
for cp in (0x61, 0x00E9, 0x00BD, 0xFB01):
    print(hex(cp), repr(unicodedata.decomposition(chr(cp))))

# NORMALIZE, all four forms, over composed/decomposed/compatibility pairs.
cases = [
    "é",              # e-acute, precomposed
    "é",             # e + combining acute
    "ﬁ",              # ligature fi, compatibility-decomposes to "fi"
    "½",              # vulgar fraction one half
    "가",              # Hangul syllable (algorithmic decomposition)
    "가",        # the same syllable's jamo, pre-composition
    "",
    "plain ascii",
]
for form in ("NFC", "NFD", "NFKC", "NFKD"):
    for text in cases:
        n = unicodedata.normalize(form, text)
        print(form, repr(text), "->", repr(n), len(n))

# IS_NORMALIZED agrees with normalize -- that IS the specification
# (is_normalized(form, s) == (normalize(form, s) == s)) -- checked for every
# case and every form rather than trusted as a separate implementation.
for form in ("NFC", "NFD", "NFKC", "NFKD"):
    for text in cases:
        want = unicodedata.normalize(form, text) == text
        print(form, repr(text), "normalized:",
             unicodedata.is_normalized(form, text) == want)

# ROUND TRIP: NFD then NFC recomposes to the same string for ordinary text.
for text in ("café", "élève", "straße"):
    d = unicodedata.normalize("NFD", text)
    c = unicodedata.normalize("NFC", d)
    print(repr(text), "round-trips:", c == text)

# NUMERIC PROPERTIES.
for cp in (0x30, 0x39, 0x00BD, 0x2155, 0x3007, 0x61):
    ch = chr(cp)
    print(hex(cp), unicodedata.decimal(ch, None),
         unicodedata.digit(ch, None), unicodedata.numeric(ch, None))

# DEFAULTS, and the exception when none is given.
print(unicodedata.decimal("a", "none"))
try:
    unicodedata.decimal("a")
    print("ACCEPTED")
except ValueError:
    print("ValueError raised")
