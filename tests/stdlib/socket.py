# COVERAGE: a real TCP round trip over loopback -- create_server, an
# ephemeral port through getsockname, create_connection, accept, sendall,
# send, recv, recv_into, end of stream when the peer closes, close and
# double close, fileno before and after, the context-manager protocol; the
# constants; inet_aton/inet_ntoa and the byte-order helpers; and the errors
# CPython raises too (a name that does not resolve, a port out of range, a
# malformed address, accept on a closed listener). What this build refuses
# BY NAME and CPython supports -- SOCK_DGRAM, AF_INET6, settimeout,
# setblocking(False) -- is a documented divergence rather than a case here;
# see the last section and the module docstring.
#
# BOTH ENDS IN ONE PROCESS, ON ONE THREAD, and that is not a workaround:
# connecting to a listening socket completes as soon as the kernel queues
# it -- that is what the backlog IS -- so listen, connect, accept runs to
# completion without a second thread. It also makes the test hermetic:
# nothing outside this process is contacted and no port is hard-coded.
import socket

# --- a round trip -----------------------------------------------------
server = socket.create_server(("127.0.0.1", 0))
host, port = server.getsockname()
print("bound:", host, "to a real port:", port > 0)
print("the listener has a descriptor:", server.fileno() >= 0)

client = socket.create_connection(("127.0.0.1", port))
conn, peer = server.accept()
print("accepted from:", peer[0])

print("sendall returns None:", client.sendall(b"hello over tcp") is None)
print("received:", conn.recv(64))
print("send returns a count:", conn.send(b"and back"))
print("round trip:", client.recv(64))

# recv_into fills a caller's buffer and answers how much
conn.sendall(b"0123456789")
buf = bytearray(10)
got = client.recv_into(buf)
print("recv_into:", got, bytes(buf[:got]))

# a short read leaves the rest for the next one
conn.sendall(b"abcdef")
print("first three:", client.recv(3))
print("the rest:", client.recv(3))
print("--- round trip done ---")


# --- end of stream ----------------------------------------------------
conn.close()
print("the peer closed, so recv is empty:", client.recv(16))
print("and stays empty:", client.recv(16))
client.close()
print("closed fileno:", client.fileno())
print("closing twice is fine:", client.close())
try:
    client.recv(1)
except OSError:
    print("a closed socket refuses recv")
try:
    client.send(b"x")
except OSError:
    print("a closed socket refuses send")
server.close()
print("--- end of stream done ---")


# --- the context manager ----------------------------------------------
with socket.create_server(("127.0.0.1", 0)) as listener:
    inner_port = listener.getsockname()[1]
    with socket.create_connection(("127.0.0.1", inner_port)) as talker:
        held, _ = listener.accept()
        talker.sendall(b"in a with")
        print("inside the with:", held.recv(32))
        held.close()
    print("the client closed on exit:", talker.fileno() == -1)
print("the listener closed on exit:", listener.fileno() == -1)
print("--- context manager done ---")


# --- constructing one by hand -----------------------------------------
manual = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# NOT `manual.fileno()` BEFORE `listen()`. CPython makes the descriptor in
# the constructor and this build makes it in `bind`/`listen` -- the `net`
# group has no "create a socket" operation, because a socket that is
# neither connected nor listening is a thing the operating system has and
# this contract does not. A documented divergence, so not asserted here.
manual.bind(("", 0))
manual.listen(1)
manual_port = manual.getsockname()[1]
print("bind then listen:", manual_port > 0)
peer = socket.socket()
print("connect_ex on success:", peer.connect_ex(("127.0.0.1", manual_port)))
accepted, _ = manual.accept()
peer.sendall(b"by hand")
print("by hand:", accepted.recv(16))
print("family/type/proto:", accepted.family, accepted.type, accepted.proto)
accepted.close()
peer.close()
manual.close()
print("--- manual done ---")


# --- the constants ----------------------------------------------------
print("AF_INET:", socket.AF_INET, "SOCK_STREAM:", socket.SOCK_STREAM)
print("SOL_SOCKET:", socket.SOL_SOCKET, "SO_REUSEADDR:", socket.SO_REUSEADDR)
print("SHUT_RD/WR/RDWR:", socket.SHUT_RD, socket.SHUT_WR, socket.SHUT_RDWR)
print("error is OSError:", socket.error is OSError)
print("timeout is an OSError:", issubclass(socket.timeout, OSError))
print("gaierror is an OSError:", issubclass(socket.gaierror, OSError))
print("--- constants done ---")


# --- addresses and byte order -----------------------------------------
print("inet_aton:", socket.inet_aton("127.0.0.1"))
print("inet_ntoa:", socket.inet_ntoa(b"\x7f\x00\x00\x01"))
print("round trip:", socket.inet_ntoa(socket.inet_aton("10.20.30.40")))
print("htons:", socket.htons(0x1234), "ntohs:", socket.ntohs(0x3412))
print("htonl:", socket.htonl(0x12345678),
      "ntohl:", socket.ntohl(0x78563412))
print("gethostbyname of a quad:", socket.gethostbyname("127.0.0.1"))
info = socket.getaddrinfo("127.0.0.1", 80)
print("getaddrinfo:", info[0][0], info[0][1], info[0][4])
print("--- addresses done ---")


# --- errors, and only the ones CPython raises too ---------------------
#
# THIS SECTION CANNOT TEST THIS BUILD'S REFUSALS, and that is the point of
# saying so here. `SOCK_DGRAM`, `AF_INET6`, `settimeout` and
# `setblocking(False)` are all things CPython SUPPORTS and this build
# refuses BY NAME -- so a case for one of them would print a refusal on one
# side and nothing on the other, which is a divergence to document (the
# module docstring does) rather than a difference to assert away. What
# belongs here is the errors BOTH raise, which is what a portable program's
# error path is actually made of.
refuser = socket.socket()
try:
    socket.create_connection(("no-such-host.invalid", 80))
except OSError:
    print("a name that does not resolve is an OSError")
try:
    refuser.connect(("127.0.0.1", 70000))
except OverflowError:
    print("a port out of range is an OverflowError")
try:
    refuser.connect("127.0.0.1")
except TypeError:
    print("a bare string address is a TypeError")
try:
    refuser.connect(("127.0.0.1", "80"))
except TypeError:
    print("a string port is a TypeError")
closed = socket.create_server(("127.0.0.1", 0))
closed.close()
try:
    closed.accept()
except OSError:
    print("accept on a closed listener is an OSError")
print("done")
