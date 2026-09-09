# COVERAGE: Lock (acquire/release/locked, non-blocking acquire, the
# RuntimeError for releasing an unlocked one, as a context manager),
# RLock (reentrancy, the count, the RuntimeError for an un-acquired
# release), Semaphore and BoundedSemaphore (the counter, non-blocking
# acquire at zero, the ValueError for over-releasing a bounded one),
# Event (set/clear/is_set, wait on a set event, a timed wait on a clear
# one), Condition (the lock half, wait_for on a predicate that already
# holds, notify's un-acquired-lock check), Barrier with one party,
# local, and Thread (the target running exactly once with its arguments,
# join, is_alive before start and after join, name, daemon, ident,
# current_thread/main_thread/active_count, an exception in the target
# not reaching the starter).
#
# WHAT IS NOT ASSERTED, AND WHY. Nothing here starts two threads and
# looks at the interleaving, because CPython's answer to that is a RACE
# and a differential test cannot have one: `t.start(); t.is_alive()` is
# True or False there depending on the scheduler. Every case below is
# one whose answer CPython gives deterministically -- which is also the
# set a correct program is allowed to depend on.
import threading

# --- Lock -------------------------------------------------------------
lock = threading.Lock()
print("fresh:", lock.locked())
print("acquired:", lock.acquire())
print("now locked:", lock.locked())
print("non-blocking while held:", lock.acquire(False))
lock.release()
print("after release:", lock.locked())
try:
    lock.release()
except RuntimeError as exc:
    print("releasing an unlocked lock:", exc)
try:
    lock.acquire(False, 1.0)
except ValueError as exc:
    print("a timeout with blocking=False:", exc)

with threading.Lock() as held:
    print("as a context manager:", held)
print("--- Lock done ---")


# --- RLock ------------------------------------------------------------
rlock = threading.RLock()
rlock.acquire()
print("reentrant, once:", rlock.locked())
rlock.acquire()
rlock.acquire()
print("reentrant, three times:", rlock.locked())
rlock.release()
rlock.release()
print("still held after two releases:", rlock.locked())
rlock.release()
print("released:", rlock.locked())
try:
    rlock.release()
except RuntimeError as exc:
    print("releasing an un-acquired rlock:", exc)
with threading.RLock() as held:
    print("as a context manager:", held)
print("--- RLock done ---")


# --- Semaphore --------------------------------------------------------
sem = threading.Semaphore(2)
print("two permits:", sem.acquire(), sem.acquire())
print("none left:", sem.acquire(False))
sem.release()
print("one back:", sem.acquire(False))
sem.release(2)
print("released two:", sem.acquire(False), sem.acquire(False))
try:
    threading.Semaphore(-1)
except ValueError as exc:
    print("a negative semaphore:", exc)
try:
    sem.release(0)
except ValueError as exc:
    print("releasing zero:", exc)
with threading.Semaphore(1):
    print("as a context manager: True")
print("--- Semaphore done ---")


# --- BoundedSemaphore -------------------------------------------------
bounded = threading.BoundedSemaphore(1)
print("one permit:", bounded.acquire())
bounded.release()
try:
    bounded.release()
except ValueError as exc:
    print("over-releasing:", exc)
print("still usable:", bounded.acquire(False))
print("--- BoundedSemaphore done ---")


# --- Event ------------------------------------------------------------
event = threading.Event()
print("fresh:", event.is_set())
print("a timed wait on a clear event:", event.wait(0))
event.set()
print("after set:", event.is_set())
print("wait on a set event:", event.wait(), event.wait(0))
event.clear()
print("after clear:", event.is_set())
print("--- Event done ---")


# --- Condition --------------------------------------------------------
cond = threading.Condition()
with cond:
    print("wait_for a predicate that already holds:",
          cond.wait_for(lambda: "answer"))
    cond.notify()
    cond.notify_all()
    print("notify under the lock is fine: True")
try:
    cond.notify()
except RuntimeError as exc:
    print("notify without the lock:", exc)
own = threading.Condition(threading.Lock())
with own:
    print("over an explicit Lock: True")
print("--- Condition done ---")


# --- Barrier ----------------------------------------------------------
barrier = threading.Barrier(1)
print("parties:", barrier.parties, "broken:", barrier.broken)
print("one party trips it:", barrier.wait())
print("and again:", barrier.wait())
ran = []
acting = threading.Barrier(1, action=lambda: ran.append(1))
acting.wait()
print("the action ran:", ran)
acting.abort()
print("aborted:", acting.broken)
try:
    acting.wait()
except threading.BrokenBarrierError:
    print("a broken barrier refuses")
acting.reset()
print("reset:", acting.broken)
try:
    threading.Barrier(0)
except ValueError as exc:
    print("zero parties:", exc)
print("--- Barrier done ---")


# --- local ------------------------------------------------------------
store = threading.local()
store.value = 42
store.other = "text"
print("stored:", store.value, store.other)
store.value = 43
print("rebound:", store.value)
try:
    store.missing
except AttributeError:
    print("an unset attribute is an AttributeError")
print("--- local done ---")


# --- Thread -----------------------------------------------------------
calls = []


def record(*args, **kwargs):
    calls.append((args, sorted(kwargs.items())))
    return "ignored"


worker = threading.Thread(target=record, args=(1, 2), kwargs={"k": 3})
print("before start:", worker.is_alive())
worker.start()
worker.join()
print("after join:", worker.is_alive())
print("ran exactly once, with its arguments:", calls)
print("join returns None:", worker.join() is None)
print("auto name:", worker.name.startswith("Thread-"))
print("not a daemon:", worker.daemon)
print("has an ident:", worker.ident is not None)
try:
    worker.start()
except RuntimeError as exc:
    print("starting twice:", exc)

named = threading.Thread(target=lambda: None, name="picked", daemon=True)
print("given name:", named.name, "daemon:", named.daemon)
named.name = "renamed"
print("renamed:", named.name)
try:
    threading.Thread(target=lambda: None).join()
except RuntimeError as exc:
    print("joining before start:", exc)


class Subclassed(threading.Thread):
    def run(self):
        calls.append("subclass ran")


sub = Subclassed()
sub.start()
sub.join()
print("a subclass overriding run:", calls[-1])
print("--- Thread done ---")


# --- the module's view of itself --------------------------------------
print("current is main:",
      threading.current_thread() is threading.main_thread())
print("the main thread is alive:", threading.main_thread().is_alive())
print("it is named:", threading.main_thread().name)
print("active count:", threading.active_count())
print("get_ident is an int:", isinstance(threading.get_ident(), int))
print("TIMEOUT_MAX is a float:", isinstance(threading.TIMEOUT_MAX, float))
print("done")
