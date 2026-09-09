# COVERAGE: select() over sockets -- a listener that becomes readable when
# something connects, a connection that becomes readable when data
# arrives and stops when it is drained, writability, a poll with timeout
# 0, an empty call, the objects (not descriptors) coming back, and the
# TypeError/ValueError for a bad argument; poll() objects with register,
# modify, unregister and poll(0), the POLL* constants; error as an alias
# of OSError; PIPE_BUF.
#
# TIMEOUT 0 THROUGHOUT, and that is deliberate rather than a shortcut.
# `select` with a positive timeout is a RACE against whatever it is
# waiting for, so a differential test cannot use one -- both sides would
# be answering "what happened within N milliseconds", which is not a
# question with one answer. Everything below is a POLL: what is ready at
# this instant, which both sides answer identically because both are
# looking at the same kernel state on the same loopback connection.
#
# EVERY DESCRIPTOR IS A SOCKET. This build's `select` is built on the
# `net` host-service group, which knows about the sockets it opened and
# nothing else -- a file is always ready in CPython and this cannot say
# so. That is in the module docstring; here it just means the test uses
# sockets, which is what `select` is for anyway.
import select
import socket

# --- a listener becoming readable -------------------------------------
server = socket.create_server(("127.0.0.1", 0))
port = server.getsockname()[1]
print("nothing pending:", select.select([server], [], [], 0))

client = socket.create_connection(("127.0.0.1", port))
readable, writable, exceptional = select.select([server], [], [], 0)
print("the listener is readable:", readable == [server])
print("and the other two are empty:", writable, exceptional)
conn, _ = server.accept()
print("--- listener done ---")


# --- a connection becoming readable -----------------------------------
print("no data yet:", select.select([conn], [], [], 0)[0])
client.sendall(b"ping")
print("data waiting:", select.select([conn], [], [], 0)[0] == [conn])
print("still waiting on a second look:",
      select.select([conn], [], [], 0)[0] == [conn])
print("read it:", conn.recv(8))
print("drained:", select.select([conn], [], [], 0)[0])
print("--- readable done ---")


# --- writability ------------------------------------------------------
print("a fresh connection is writable:",
      select.select([], [conn], [], 0)[1] == [conn])
print("both directions at once:",
      select.select([conn], [conn], [], 0) == ([], [conn], []))
client.sendall(b"x")
print("readable and writable:",
      select.select([conn], [conn], [], 0) == ([conn], [conn], []))
conn.recv(1)
print("--- writability done ---")


# --- several at once --------------------------------------------------
other_server = socket.create_server(("127.0.0.1", 0))
other_client = socket.create_connection(
    ("127.0.0.1", other_server.getsockname()[1]))
other_conn, _ = other_server.accept()
client.sendall(b"a")
watching = [conn, other_conn]
ready = select.select(watching, [], [], 0)[0]
print("one of two is ready:", ready == [conn])
other_client.sendall(b"b")
ready = select.select(watching, [], [], 0)[0]
print("now both are:", ready == watching)
conn.recv(1)
other_conn.recv(1)
print("and neither is:", select.select(watching, [], [], 0)[0])
print("--- several done ---")


# --- the empty and the malformed --------------------------------------
print("nothing to watch:", select.select([], [], [], 0))
print("error is OSError:", select.error is OSError)
print("PIPE_BUF is an int:", isinstance(select.PIPE_BUF, int))
try:
    select.select([object()], [], [], 0)
except TypeError:
    print("an object with no fileno is a TypeError")
try:
    select.select([-1], [], [], 0)
except ValueError:
    print("a negative descriptor is a ValueError")
try:
    select.select([conn], [], [], -1)
except ValueError:
    print("a negative timeout is a ValueError")
print("--- errors done ---")


# --- poll -------------------------------------------------------------
print("constants:", select.POLLIN, select.POLLOUT, select.POLLERR,
      select.POLLHUP, select.POLLNVAL)
poller = select.poll()
poller.register(conn, select.POLLIN)
print("nothing to report:", poller.poll(0))
client.sendall(b"pong")
print("POLLIN:", poller.poll(0) == [(conn.fileno(), select.POLLIN)])
conn.recv(8)
print("drained:", poller.poll(0))

poller.modify(conn, select.POLLOUT)
print("POLLOUT after modify:",
      poller.poll(0) == [(conn.fileno(), select.POLLOUT)])
poller.unregister(conn)
print("unregistered:", poller.poll(0))
try:
    poller.unregister(conn)
except KeyError:
    print("unregistering twice is a KeyError")
try:
    poller.modify(conn, select.POLLIN)
except OSError:
    print("modifying an unregistered descriptor is an OSError")

both = select.poll()
both.register(conn, select.POLLIN | select.POLLOUT)
client.sendall(b"z")
print("both flags at once:",
      both.poll(0) == [(conn.fileno(), select.POLLIN | select.POLLOUT)])
conn.recv(1)
print("--- poll done ---")

for one in (other_client, other_conn, other_server, conn, client, server):
    one.close()
print("done")
