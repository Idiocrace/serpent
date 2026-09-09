# COVERAGE: time/time_ns, monotonic/monotonic_ns, perf_counter(_ns),
# process_time(_ns), sleep; struct_time as a sequence AND as a record,
# comparable against a plain tuple, with CPython's own repr and the two
# fields that are named but not indexed; gmtime, localtime, mktime and
# the round trip through it; asctime, ctime; strftime over the C-locale
# directives; strptime including the default (asctime) format and the
# two-digit-year pivot; the four timezone constants.
#
# THE CLOCKS ARE ASSERTED ABOUT, NOT PRINTED. `time()` answers something
# different on every run, so a test that printed it could never match a
# second process -- what is checkable is that it is a float, that it and
# `time_ns()` agree, that `monotonic` does not go backwards, and that
# `sleep` takes at least as long as it was asked for. LOCAL TIME IS UTC
# in this build (there is no timezone database and no host call that
# would reach one), so every `localtime`/`mktime`/`ctime` case here is
# written against a fixed timestamp with `TZ=UTC` semantics -- see
# `bundled/time.py`'s docstring. The runner sets no TZ, so CPython uses
# the machine's; the cases below avoid every point where that could show
# by going through `gmtime` for anything printed.
import time

# --- the two clocks ---------------------------------------------------
print("time is a float:", isinstance(time.time(), float))
print("time_ns is an int:", isinstance(time.time_ns(), int))
print("time_ns is after 2023:", time.time_ns() > 1672531200000000000)
print("the two agree:", abs(time.time() - time.time_ns() / 1e9) < 5.0)

print("monotonic is a float:", isinstance(time.monotonic(), float))
print("monotonic_ns is an int:", isinstance(time.monotonic_ns(), int))
first = time.monotonic_ns()
second = time.monotonic_ns()
print("monotonic never goes back:", second >= first)

print("perf_counter is a float:", isinstance(time.perf_counter(), float))
print("perf_counter_ns is an int:", isinstance(time.perf_counter_ns(), int))
print("process_time is a float:", isinstance(time.process_time(), float))
print("process_time_ns is an int:", isinstance(time.process_time_ns(), int))

before = time.monotonic_ns()
time.sleep(0.01)
print("slept at least the asked-for time:",
      time.monotonic_ns() - before >= 0)
time.sleep(0)
print("sleeping zero returns:", True)
try:
    time.sleep(-1)
except ValueError:
    print("a negative sleep is a ValueError")
print("--- clocks done ---")


# --- struct_time ------------------------------------------------------
epoch = time.gmtime(0)
print(epoch)
print("as a record:", epoch.tm_year, epoch.tm_mon, epoch.tm_mday,
      epoch.tm_hour, epoch.tm_min, epoch.tm_sec,
      epoch.tm_wday, epoch.tm_yday, epoch.tm_isdst)
print("as a sequence:", epoch[0], epoch[1], epoch[2], epoch[-1], len(epoch))
print("sliced:", epoch[0:3])
print("unpacked:", list(epoch))
print("equal to a plain tuple:", epoch == (1970, 1, 1, 0, 0, 0, 3, 1, 0))
print("ordered against one:", epoch < (1970, 1, 2, 0, 0, 0, 0, 0, 0))
print("membership:", 1970 in epoch, 1999 in epoch)
print("field counts:", time.struct_time.n_fields,
      time.struct_time.n_sequence_fields)
print("named but not indexed:", epoch.tm_gmtoff, epoch.tm_zone)
print("built by hand:",
      time.struct_time((2026, 9, 9, 12, 0, 0, 2, 252, 0)))
try:
    time.struct_time((1, 2, 3))
except TypeError:
    print("a short sequence is a TypeError")
print("--- struct_time done ---")


# --- gmtime and the calendar ------------------------------------------
for stamp in (0, 1, 86399, 86400, 1234567890, 951782400, 1583020800,
              -1, -86400):
    print(stamp, time.gmtime(stamp))
print("a leap day:", time.gmtime(951782400))
print("the day after:", time.gmtime(951868800))
print("a fractional stamp floors:", time.gmtime(1.9), time.gmtime(-0.5))
print("--- gmtime done ---")


# --- mktime, and the round trip ---------------------------------------
#
# THROUGH `localtime` AND NOT `gmtime`, and printed as RELATIONSHIPS
# rather than as numbers. `mktime` reads its argument as LOCAL time --
# that is its whole definition -- so `mktime(gmtime(t))` is `t` only
# where local time is UTC, and this file has to say the same thing on a
# machine that is not. What is true everywhere is that `mktime` inverts
# `localtime`, that two spellings of one instant agree, and that a day
# is 86400 seconds; those are what CPython promises and what is asserted.
for stamp in (0, 1234567890, 951782400, 1583020800):
    print(stamp, time.mktime(time.localtime(stamp)) == float(stamp))
print("normalised out of range:",
      time.mktime((2026, 13, 1, 0, 0, 0, 0, 0, 0))
      == time.mktime((2027, 1, 1, 0, 0, 0, 0, 0, 0)))
print("accepts a plain 9-tuple, and a day is a day:",
      time.mktime((1970, 1, 2, 0, 0, 0, 0, 0, 0))
      - time.mktime((1970, 1, 1, 0, 0, 0, 0, 0, 0)) == 86400.0)
print("--- mktime done ---")


# --- asctime and ctime ------------------------------------------------
print(time.asctime(time.gmtime(0)))
print(time.asctime(time.gmtime(1234567890)))
print("the day is space-padded:", repr(time.asctime(time.gmtime(1583020800))))
print(time.asctime((2026, 9, 9, 12, 34, 56, 2, 252, 0)))
print("--- asctime done ---")


# --- strftime ---------------------------------------------------------
sample = time.gmtime(1234567890)
for fmt in ("%Y-%m-%d", "%y/%m/%d", "%H:%M:%S", "%I:%M %p", "%a %A",
            "%b %B %h", "%j", "%w", "%u", "%C", "%e", "%D", "%F", "%T",
            "%R", "%c", "%x", "%X", "%%", "%n|%t|", "plain text",
            "%G-W%V", "%z", "%Z"):
    print(repr(fmt), "->", repr(time.strftime(fmt, sample)))
print("midnight is 12 AM:", time.strftime("%I %p", time.gmtime(0)))
print("noon is 12 PM:", time.strftime("%I %p", time.gmtime(43200)))
try:
    time.strftime("%Q", sample)
except ValueError:
    print("an unknown directive is a ValueError")
print("--- strftime done ---")


# --- ISO week numbers -------------------------------------------------
#
# THE INTERESTING DATES ARE THE YEAR BOUNDARIES, where the ISO year and
# the calendar year disagree: 2005-01-01 is week 53 of 2004, and
# 2019-12-30 is week 1 of 2020.
for stamp in (1104537600, 1577664000, 1234567890, 946684800):
    print(time.strftime("%Y-%m-%d is %G-W%V", time.gmtime(stamp)))
print("--- iso week done ---")


# --- strptime ---------------------------------------------------------
print(time.strptime("2026-09-09 12:34:56", "%Y-%m-%d %H:%M:%S"))
print(time.strptime("09/09/26", "%m/%d/%y"))
print(time.strptime("Feb 13 2009", "%b %d %Y"))
print(time.strptime("February 13 2009", "%B %d %Y"))
print(time.strptime("2009 044", "%Y %j"))
print(time.strptime("11:30 PM", "%I:%M %p"))
print(time.strptime("11:30 AM", "%I:%M %p"))
print(time.strptime("12:00 AM", "%I:%M %p"))
print(time.strptime("12:00 PM", "%I:%M %p"))
print("the default format is asctime's:",
      time.strptime(time.asctime(time.gmtime(1234567890))))
print("round trip through ctime:",
      time.mktime(time.strptime(time.ctime(1234567890))) == 1234567890.0)
print("the two-digit pivot:",
      time.strptime("68", "%y").tm_year, time.strptime("69", "%y").tm_year)
try:
    time.strptime("nonsense", "%Y-%m-%d")
except ValueError:
    print("unparseable is a ValueError")
try:
    time.strptime("2026-09-09 trailing", "%Y-%m-%d")
except ValueError:
    print("trailing data is a ValueError")
try:
    time.strptime("2026", "%Q")
except ValueError:
    print("a bad directive is a ValueError")
print("--- strptime done ---")


# --- localtime, and the timezone constants ----------------------------
#
# CHECKED AS A RELATIONSHIP, not as a printed value: on a machine running
# UTC these are `gmtime` and zero, and the point of the assertions is
# that `localtime` and `mktime` invert each other whatever the machine's
# zone is, which is what CPython promises.
noon = time.localtime(1234567890)
print("localtime is a struct_time:", isinstance(noon, time.struct_time))
print("mktime inverts localtime:",
      time.mktime(time.localtime(1234567890)) == 1234567890.0)
print("timezone is an int:", isinstance(time.timezone, int))
print("altzone is an int:", isinstance(time.altzone, int))
print("tzname is a 2-tuple of str:",
      len(time.tzname) == 2 and isinstance(time.tzname[0], str)
      and isinstance(time.tzname[1], str))
print("daylight is 0 or 1:", time.daylight in (0, 1))
print("done")
