# COVERAGE: os.path.join/basename/dirname/splitext/normpath/isabs, and
# os.path.abspath for an ALREADY-ABSOLUTE path only (a relative one raises
# NotImplementedError -- see bundled/os.py, which has no os.getcwd to
# resolve one against); os.path.exists/isfile/isdir against a real file and
# a real directory this program creates and removes; os.remove/os.unlink/
# os.mkdir/os.rmdir/os.makedirs actually mutating the real filesystem, and
# the errors each raises; os.getenv and os.environ (`[]`, `.get`, `in` --
# READ-ONLY: no iteration, no assignment); os.linesep, os.sep, os.pathsep.
# NOT covered: os.getcwd, os.listdir, os.walk, os.stat, os.chdir,
# os.rename, os.replace -- each refused by name in bundled/os.py rather
# than answered wrongly (docs/STDLIB.md's pathlib section states the same
# limits for the equivalent pathlib.Path methods), and so cannot appear in
# a program whose output must equal CPython's.
import os
import pathlib

# A RUN THAT DIED HALFWAY LEFT ITS FILES BEHIND, and the next run then
# differs from CPython at whichever line first trips over one -- a failure
# that reads as a miscompile and is not one. See tests/stdlib/pathlib.py for
# the same note; it cannot be a loop over the directory here either, since
# this module refuses os.listdir just as that one refuses iterdir.
for _stale in ("apy-os-case.txt", "apy-os-case-dir/x/y", "apy-os-case-dir/x",
               "apy-os-case-dir"):
    if pathlib.Path(_stale).is_dir():
        os.rmdir(_stale)
    else:
        pathlib.Path(_stale).unlink(missing_ok=True)

# ---- os.path.join -----------------------------------------------------
print(os.path.join("a", "b", "c"))
print(os.path.join("a/", "b"))
print(os.path.join("/a", "b", "/c"))
print(os.path.join("a", ""))
print(os.path.join("", "a"))
print(os.path.join("/a"))
print(os.path.join("a", "b/"))
print(os.path.join("a", "", "b"))

# ---- os.path.basename / os.path.dirname --------------------------------
for _p in ("/a/b/c.txt", "/a/b/", "a", "/", "", "a/b//c", "./a", "//a"):
    print(repr(_p), repr(os.path.basename(_p)), repr(os.path.dirname(_p)))

# ---- os.path.splitext ---------------------------------------------------
for _p in ("a.txt", "a.tar.gz", ".bashrc", "...bashrc", "a.", "/a/b.c/d",
          "noext", "a..b", "/a/.bashrc"):
    print(repr(_p), os.path.splitext(_p))

# ---- os.path.normpath ----------------------------------------------------
for _p in ("a//b", "a/./b", "a/../b", "../a", "/../a", "//a", "///a", "",
          ".", "a/..", "a/b/../..", "..", "/", "//", "///",
          "/./a/../b/./c"):
    print(repr(_p), repr(os.path.normpath(_p)))

# ---- os.path.isabs / os.path.abspath -------------------------------------
print(os.path.isabs("/a/b"), os.path.isabs("a/b"), os.path.isabs(""))
print(os.path.abspath("/a/b/../c"))
print(os.path.abspath("/a//b/./c"))
# `abspath` ON A RELATIVE PATH IS NOT TESTED HERE, deliberately: CPython
# answers it (by resolving against `os.getcwd()`) rather than raising, so a
# differential assertion that it raises could only ever fail -- the same
# reason tests/stdlib/pathlib.py never calls `resolve` or `absolute`. See
# the module docstring in bundled/os.py for why this module cannot answer
# it either.

# ---- os.path.exists / isfile / isdir, against real files ----------------
_f = "apy-os-case.txt"
_d = "apy-os-case-dir"
print(os.path.exists(_f), os.path.isfile(_f), os.path.isdir(_f))
pathlib.Path(_f).write_bytes(b"hello")
print(os.path.exists(_f), os.path.isfile(_f), os.path.isdir(_f))

print(os.path.exists(_d), os.path.isdir(_d))
os.mkdir(_d)
print(os.path.exists(_d), os.path.isdir(_d), os.path.isfile(_d))

# ---- os.remove / os.unlink / os.rmdir / os.mkdir, mutating real files ---
os.remove(_f)
print(os.path.exists(_f))
try:
    os.remove(_f)
except FileNotFoundError:
    print("remove: FileNotFoundError")

pathlib.Path(_f).write_bytes(b"z")
os.unlink(_f)
print(os.path.exists(_f))

try:
    os.mkdir(_d)
except FileExistsError:
    print("mkdir: FileExistsError")

os.rmdir(_d)
print(os.path.exists(_d))
try:
    os.rmdir(_d)
except FileNotFoundError:
    print("rmdir: FileNotFoundError")

# ---- os.makedirs ----------------------------------------------------------
_nested = os.path.join(_d, "x", "y")
os.makedirs(_nested)
print(os.path.isdir(_nested), os.path.isdir(os.path.join(_d, "x")))
os.makedirs(_nested, exist_ok=True)
print(os.path.isdir(_nested))
try:
    os.makedirs(_nested)
except FileExistsError:
    print("makedirs: FileExistsError")
os.rmdir(_nested)
os.rmdir(os.path.join(_d, "x"))
os.rmdir(_d)
print(os.path.exists(_d))

# ---- os.getenv / os.environ ------------------------------------------------
_missing = "ASMPY_OS_TEST_DOES_NOT_EXIST_9182"
print(os.getenv(_missing))
print(os.getenv(_missing, "fallback"))
print(_missing in os.environ)
try:
    os.environ[_missing]
except KeyError:
    print("environ[]: KeyError")
print(os.environ.get(_missing, "fallback"))

print(os.getenv("HOME") is not None)
print(os.getenv("PATH") is not None)
print("HOME" in os.environ)
print("PATH" in os.environ)

# ---- constants --------------------------------------------------------------
print(repr(os.linesep), repr(os.sep), repr(os.pathsep))

# `os.getcwd`, `os.listdir`, `os.walk`, `os.stat`, `os.chdir`, `os.rename`
# and `os.replace` ARE NOT EXERCISED HERE, deliberately: CPython answers
# every one of them (this program runs in a real directory with real
# files), so a differential assertion that any of them raises could only
# ever fail -- the same structural reason `tests/stdlib/re.py` cannot test
# what it refuses either (docs/STDLIB.md). Each is refused BY NAME in
# bundled/os.py; see its module docstring for exactly what each is blocked
# on.

print("done")
