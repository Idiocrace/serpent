# COVERAGE: bisect_left, bisect_right, bisect (alias), insort_left,
# insort_right, insort (alias), each with lo, hi and key= -- the whole
# module.
import bisect

# --- bisect_left / bisect_right on duplicates -------------------------
a = [1, 3, 3, 3, 5, 7, 9]
for x in [0, 1, 2, 3, 4, 9, 10]:
    print(x, bisect.bisect_left(a, x), bisect.bisect_right(a, x))

# Inserting a value already present, at the very start, and past the end.
b = [2, 2, 2]
print(bisect.bisect_left(b, 2), bisect.bisect_right(b, 2))
print(bisect.bisect_left(b, 1), bisect.bisect_right(b, 1))
print(bisect.bisect_left(b, 3), bisect.bisect_right(b, 3))

empty = []
print(bisect.bisect_left(empty, 5), bisect.bisect_right(empty, 5))

# --- explicit lo/hi slicing the search range ---------------------------
c = [1, 2, 2, 2, 3, 4, 4, 5, 6]
print(bisect.bisect_left(c, 2, 2, 6))
print(bisect.bisect_right(c, 2, 2, 6))
print(bisect.bisect_left(c, 4, 0, 5))
print(bisect.bisect_right(c, 4, 0, 5))
# hi omitted, lo given.
print(bisect.bisect_left(c, 4, 5))
print(bisect.bisect_right(c, 4, 5))
# lo == hi: an empty slice, always the same index back.
print(bisect.bisect_left(c, 100, 3, 3))

# --- bisect is an alias for bisect_right, exactly ----------------------
print(bisect.bisect is bisect.bisect_right)
for x in [0, 1, 2, 3, 4, 9, 10]:
    print(bisect.bisect(a, x) == bisect.bisect_right(a, x))

# --- key=, sorting/searching by absolute value --------------------------
d = [-9, -7, -3, 1, 4, 6, 8]  # sorted by abs(): 1, -3, 4, -7, 6, 8, -9
print([abs(v) for v in d])
print(bisect.bisect_left(d, 5, key=abs))
print(bisect.bisect_right(d, 5, key=abs))
print(bisect.bisect_left(d, 7, key=abs))
print(bisect.bisect_right(d, 7, key=abs))
print(bisect.bisect_left(d, 0, key=abs))

# --- key=, searching a list of tuples by the second element -------------
pairs = [("a", 1), ("b", 1), ("c", 2), ("d", 2), ("e", 4)]
by_second = lambda t: t[1]
print(bisect.bisect_left(pairs, 2, key=by_second))
print(bisect.bisect_right(pairs, 2, key=by_second))
print(bisect.bisect_left(pairs, 3, key=by_second))
print(bisect.bisect_right(pairs, 3, key=by_second))

# key= together with lo/hi.
print(bisect.bisect_left(pairs, 1, 1, 5, key=by_second))
print(bisect.bisect_right(pairs, 1, 1, 5, key=by_second))

# --- insort_left / insort_right actually mutate, preserving order -------
xs = [1, 3, 3, 5]
bisect.insort_left(xs, 3)
print(xs)
bisect.insort_right(xs, 3)
print(xs)
bisect.insort_left(xs, 0)
print(xs)
bisect.insort_right(xs, 9)
print(xs)

# insort_left vs insort_right land on opposite sides of a run of equals.
left_xs = [2, 2, 2]
bisect.insort_left(left_xs, 2)
print(left_xs)
right_xs = [2, 2, 2]
bisect.insort_right(right_xs, 2)
print(right_xs)

# insort with lo/hi restricting where the insertion may land.
ys = [0, 5, 5, 5, 9]
bisect.insort_left(ys, 5, 2, 3)
print(ys)

# --- insort is an alias for insort_right, exactly ------------------------
print(bisect.insort is bisect.insort_right)
zs1 = [1, 2, 2, 4]
zs2 = [1, 2, 2, 4]
bisect.insort(zs1, 2)
bisect.insort_right(zs2, 2)
print(zs1 == zs2, zs1)

# --- insort with key=, keeping the list sorted by the key ----------------
words = ["fig", "date", "kiwi", "banana"]  # sorted by len: fig(3) date(4) kiwi(4) banana(6)
words.sort(key=len)
print(words)
bisect.insort_left(words, "pear", key=len)  # len 4, ties with date/kiwi
print(words)
bisect.insort_right(words, "ox", key=len)  # len 2, goes first
print(words)

# --- errors: a negative lo is refused ------------------------------------
try:
    bisect.bisect_left([1, 2, 3], 2, -1)
except ValueError as e:
    print("ValueError:", e)

try:
    bisect.insort_right([1, 2, 3], 2, -1)
except ValueError as e:
    print("ValueError:", e)
