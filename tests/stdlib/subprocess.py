# COVERAGE: run() with capture_output, stdout=PIPE, stderr=PIPE,
# stderr=STDOUT, text=, encoding=, check=, and a list or a shell string;
# CompletedProcess (.args/.returncode/.stdout/.stderr/.check_returncode);
# check_output, check_call, call, getoutput, getstatusoutput;
# CalledProcessError with its returncode/cmd/output/stdout/stderr and its
# message; a child that could not be started; the constants.
#
# EVERY COMMAND IS A POSIX SHELL BUILTIN OR COREUTIL used the same way on
# both sides -- `echo`, `true`, `false`, `sh -c`, `cat`. Nothing here
# depends on this repository, this directory or anything the test could
# have left behind, so the two runs see the same world.
#
# WHAT IS NOT TESTED, AND WHY. `Popen` and everything that needs a live
# child is refused BY NAME here and supported by CPython, so a case for it
# would print a refusal on one side and nothing on the other; the module
# docstring records it instead. Nothing writes more than the capture
# buffer, because that limit is this build's and CPython has none.
import subprocess

# --- run, and what it answers -----------------------------------------
done = subprocess.run(["echo", "hi"], capture_output=True, text=True)
print("stdout:", repr(done.stdout))
print("stderr:", repr(done.stderr))
print("returncode:", done.returncode)
print("args:", done.args)
print("check_returncode on success:", done.check_returncode())

as_bytes = subprocess.run(["echo", "raw"], capture_output=True)
print("without text=:", repr(as_bytes.stdout))
print("bytes stderr:", repr(as_bytes.stderr))

with_encoding = subprocess.run(["echo", "enc"], capture_output=True,
                               encoding="utf-8")
print("with encoding=:", repr(with_encoding.stdout))
print("--- run done ---")


# --- the streams ------------------------------------------------------
# A CHILD THAT WRITES NOTHING TO stderr, deliberately: with only stdout
# captured, the other stream goes to this program's own, and WHERE that
# lands relative to this program's buffered output is not something the
# two runs agree on -- CPython's child writes to the inherited descriptor
# as it runs and this build re-emits what it collected after the child is
# done. The captured half is what is asserted; the pass-through is
# exercised by `call()` further down.
out_only = subprocess.run(["sh", "-c", "echo to-out"],
                          stdout=subprocess.PIPE, text=True)
print("stdout only:", repr(out_only.stdout), "stderr:", out_only.stderr)

both = subprocess.run(["sh", "-c", "echo to-out; echo to-err >&2"],
                      capture_output=True, text=True)
print("captured out:", repr(both.stdout))
print("captured err:", repr(both.stderr))

merged = subprocess.run(["sh", "-c", "echo first; echo second >&2"],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True)
print("merged has both:",
      "first" in merged.stdout and "second" in merged.stdout)
print("merged stderr is None:", merged.stderr is None)
print("--- streams done ---")


# --- exit status ------------------------------------------------------
print("true:", subprocess.run(["true"]).returncode)
print("false:", subprocess.run(["false"]).returncode)
print("a chosen status:", subprocess.run(["sh", "-c", "exit 7"]).returncode)
try:
    subprocess.run(["false"], check=True)
except subprocess.CalledProcessError as exc:
    print("check=True raises:", exc.returncode, exc.cmd)
    print("its message:", str(exc))
    print("it is a SubprocessError:",
          isinstance(exc, subprocess.SubprocessError))
failed = subprocess.run(["sh", "-c", "echo said; exit 2"],
                        capture_output=True, text=True)
try:
    failed.check_returncode()
except subprocess.CalledProcessError as exc:
    print("check_returncode carries the output:", repr(exc.output),
          repr(exc.stdout))
print("--- status done ---")


# --- the convenience functions ----------------------------------------
print("check_output:", repr(subprocess.check_output(["echo", "co"],
                                                    text=True)))
print("check_output bytes:", repr(subprocess.check_output(["echo", "cb"])))
try:
    subprocess.check_output(["sh", "-c", "echo out; exit 4"], text=True)
except subprocess.CalledProcessError as exc:
    print("check_output on failure:", exc.returncode, repr(exc.output))
print("check_call:", subprocess.check_call(["true"]))
try:
    subprocess.check_call(["false"])
except subprocess.CalledProcessError as exc:
    print("check_call on failure:", exc.returncode)
print("call:", subprocess.call(["true"]), subprocess.call(["false"]))
print("--- convenience done ---")


# --- the shell --------------------------------------------------------
print("getoutput:", repr(subprocess.getoutput("echo shelled")))
print("getstatusoutput:", subprocess.getstatusoutput("echo ok"))
print("a failing shell command:", subprocess.getstatusoutput("exit 5"))
print("stderr is merged in:",
      subprocess.getoutput("echo to-err >&2"))
shelled = subprocess.run("echo via-shell", shell=True,
                         capture_output=True, text=True)
print("shell=True:", repr(shelled.stdout))
print("--- shell done ---")


# --- a child that will not start --------------------------------------
try:
    subprocess.run(["no-such-program-anywhere"], capture_output=True)
except FileNotFoundError:
    print("a missing program is a FileNotFoundError")
print("--- missing done ---")


# --- the constants ----------------------------------------------------
print("PIPE/STDOUT/DEVNULL are distinct ints:",
      len({subprocess.PIPE, subprocess.STDOUT, subprocess.DEVNULL}) == 3)
print("CalledProcessError is a SubprocessError:",
      issubclass(subprocess.CalledProcessError, subprocess.SubprocessError))
print("done")
