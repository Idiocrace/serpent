# COVERAGE: format_exception_only (both call forms, empty-message and
# multi-arg exceptions, __notes__ including a multi-line one), the real
# chaining attributes (__cause__, __context__, __suppress_context__) for
# `raise X from Y`, implicit context, and `from None` suppression, and
# format_exception / print_exception / format_tb / extract_tb / StackSummary
# / FrameSummary / TracebackException for a `raise` in the SAME FRAME as the
# `try` that catches it (module level here) -- the one shape this runtime's
# ONE-FRAME-DEEP traceback (`tb_next` always None) agrees with CPython about
# exactly. NOT COVERED, and not exercised below because a shared script
# cannot ask CPython to skip its own real behaviour: format_exc/print_exc
# (no `sys.exc_info()`, and a bare `raise` in a called function cannot see
# what its caller is handling -- see bundled/traceback.py), walk_tb/
# walk_stack/extract_stack/format_stack/print_stack (no call stack to walk),
# a quoted source line under a frame (co_filename is always `<compiled>`),
# and SyntaxError's / BaseExceptionGroup's own multi-line formats (refused
# BY NAME with NotImplementedError rather than approximated).
#
# THE FILE PATH IS NEVER COMPARED. CPython's frame line embeds this file's
# real, unpredictable absolute path; this runtime's embeds the fixed
# `<compiled>` (`objects_host._apy_code_of` says why). `_scrub` below pulls
# the line number and function name out of each frame line by regex and
# discards the rest of it, and drops the quoted-source line CPython adds
# and this module never can -- see its own docstring for both. What is left
# after that reduction embeds no path either way and is compared exactly.
import re
import traceback


def _scrub(lines):
    """`lines` is what `format_exception`/`TracebackException.format`
    returns: a list (or, under real CPython, a generator) of strings, one
    `Traceback (most recent call last):` header and one FRAME entry per
    stack entry, then the exception-only line(s), repeated once per link
    of a chain with a message string between.

    A frame entry is `list(...)`-list-checked here by its own first line
    only: real CPython's frame entry is TWO lines run together in one
    string -- the `File "...", line N, in NAME` line and, when the source
    is readable (this file always is, under CPython), a second line
    quoting it (`re.match` does not anchor the end, so that second line is
    simply never looked at). This runtime's is one line, the file never
    readable (`<compiled>` never names a real one -- see the module
    docstring), so there is no second line to begin with. Both reduce to
    the same thing: the file PATH -- unpredictable and real under CPython,
    fixed and fake here -- is the only part discarded."""
    out = []
    for item in lines:
        m = re.match(r'  File "[^"]*", line (\d+), in ([^\n]+)\n', item)
        if m:
            out.append("  FRAME line=%s in=%s\n" % (m.group(1), m.group(2)))
            continue
        out.append(item)
    return out


class Buf:
    """A file-like `print_exception`/`print_tb` can write to -- this
    runtime has no `io.StringIO` and no `sys.stdout` object, only the
    `file=` keyword `print` already accepts for any object with `.write`."""

    def __init__(self):
        self.parts = []

    def write(self, s):
        self.parts.append(s)


class MyError(Exception):
    pass


print("=== format_exception_only ===")
try:
    raise ValueError("bad thing")
except ValueError as e:
    print(traceback.format_exception_only(e))

try:
    raise RuntimeError()
except RuntimeError as e:
    print(traceback.format_exception_only(e))

try:
    raise ValueError("a", "b", 3)
except ValueError as e:
    print(traceback.format_exception_only(e))

try:
    raise KeyError("mykey")
except KeyError as e:
    print(traceback.format_exception_only(e))

try:
    raise MyError("oops")
except MyError as e:
    print(traceback.format_exception_only(e))

# The legacy two-argument form: the first argument is a CLASS, ignored in
# favour of the second's own type -- CPython's real implementation does
# this too, which is why passing a mismatched class here still reads
# "ValueError", not "TypeError".
print(traceback.format_exception_only(TypeError, ValueError("legacy")))

e = ValueError("noted")
e.add_note("extra info")
e.add_note("line one\nline two")
print(traceback.format_exception_only(e))

print("=== unraised exception has no traceback ===")
e = ValueError("never raised")
print(e.__traceback__)
print(traceback.format_exception_only(e))
print(_scrub(traceback.format_exception(e)))

print("=== explicit cause (raise X from Y) ===")
try:
    raise ValueError("first")
except ValueError as first:
    try:
        raise TypeError("second") from first
    except TypeError as e2:
        print(type(e2.__cause__).__name__, str(e2.__cause__))
        print(type(e2.__context__).__name__, str(e2.__context__))
        print(e2.__suppress_context__)

print("=== implicit context (bare raise inside except) ===")
try:
    raise ValueError("A")
except ValueError:
    try:
        raise TypeError("B")
    except TypeError as e3:
        print(e3.__cause__)
        print(type(e3.__context__).__name__, str(e3.__context__))
        print(e3.__suppress_context__)

print("=== suppressed context (raise X from None) ===")
try:
    raise ValueError("A2")
except ValueError:
    try:
        raise TypeError("B2") from None
    except TypeError as e4:
        print(e4.__cause__)
        print(e4.__context__)
        print(e4.__suppress_context__)

print("=== a later, unrelated raise carries no stale context ===")
try:
    raise RuntimeError("fresh")
except RuntimeError as e5:
    print(e5.__context__)
    print(e5.__cause__)

print("=== extract_tb / StackSummary / FrameSummary, one frame ===")
try:
    raise ValueError("single frame")
except ValueError as e6:
    tb = e6.__traceback__
    print(tb.tb_next)
    stack = traceback.extract_tb(tb)
    print(len(stack))
    print(stack[0].name)
    print(stack[0].lineno == tb.tb_lineno)
    # `.line` IS NOT COMPARED: CPython reads it from the real file on disk
    # (`linecache`, keyed by the real path), and this runtime's `co_filename`
    # is always `<compiled>`, which is never a file -- so `.line` is always
    # None here where CPython's is the actual source text. Documented in
    # bundled/traceback.py rather than approximated.
    same = traceback.format_tb(tb) == stack.format()
    print(same)

print("=== format_exception, one chain link ===")
try:
    raise ValueError("solo")
except ValueError as e7:
    lines = traceback.format_exception(e7)
    print(_scrub(lines))

print("=== format_exception, explicit cause chain ===")
try:
    raise ValueError("cause-first")
except ValueError as cause_first:
    try:
        raise TypeError("cause-second") from cause_first
    except TypeError as e8:
        print(_scrub(traceback.format_exception(e8)))
        print(_scrub(traceback.format_exception(e8, chain=False)))

print("=== format_exception, implicit context chain ===")
try:
    raise ValueError("ctx-A")
except ValueError:
    try:
        raise TypeError("ctx-B")
    except TypeError as e9:
        print(_scrub(traceback.format_exception(e9)))

print("=== format_exception, suppressed context: one block only ===")
try:
    raise ValueError("supp-A")
except ValueError:
    try:
        raise TypeError("supp-B") from None
    except TypeError as e10:
        print(_scrub(traceback.format_exception(e10)))

print("=== print_exception writes what format_exception computes ===")
try:
    raise KeyError("pk")
except KeyError as e11:
    buf = Buf()
    traceback.print_exception(e11, file=buf)
    printed = "".join(buf.parts)
    computed = "".join(traceback.format_exception(e11))
    print(printed == computed)
    print(_scrub(traceback.format_exception(e11)))

print("=== print_tb writes what format_tb computes ===")
try:
    raise ValueError("tbwrite")
except ValueError as e12:
    buf = Buf()
    traceback.print_tb(e12.__traceback__, file=buf)
    print("".join(buf.parts) == "".join(traceback.format_tb(e12.__traceback__)))

print("=== TracebackException ===")
try:
    raise ValueError("te")
except ValueError as e13:
    te = traceback.TracebackException.from_exception(e13)
    print(te.exc_type is ValueError)
    print(len(te.stack))
    print(list(te.format_exception_only()))
    print(_scrub(list(te.format())))
    print(te.__cause__)
    print(te.__context__)

print("=== TracebackException with a cause chain ===")
try:
    raise ValueError("te-cause-1")
except ValueError as tc1:
    try:
        raise TypeError("te-cause-2") from tc1
    except TypeError as e14:
        te2 = traceback.TracebackException.from_exception(e14)
        print(te2.__cause__ is not None)
        print(te2.__cause__.exc_type is ValueError)
        print(_scrub(list(te2.format())))

print("done")
