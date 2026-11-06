# Connecting to the Heltec never holds the Stump (1.0.0-beta.56): a Heltec
# that's off or not set up yet froze a WROVER 4 to 20 s per try (TCP's own
# give-up; the ESP32's MicroPython ignores settimeout() on connect), so no
# page and no captive portal answered meanwhile. Now the connect starts
# without blocking and the poll loop finishes it.
import sys, time, socket
exec(open(sys.argv[1] + '/harness.py').read())
from urns.interfaces.wifi_serial import WiFiSerialInterface
FAIL = []


def check(n, c, i=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else '  ' + repr(i)[:300]))
    if not c:
        FAIL.append(n)


def ms(t0):
    return time.ticks_diff(time.ticks_ms(), t0)


# A Heltec that's there (a listening socket stands for its TCP port)
srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(socket.getaddrinfo("127.0.0.1", 47633)[0][-1])
srv.listen(2)
t0 = time.ticks_ms()
i = WiFiSerialInterface({"name": "Heltec", "target_host": "127.0.0.1", "target_port": 47633})
check("there: starting the connect doesn't wait", ms(t0) < 300, ms(t0))
longest = 0
for _ in range(40):
    if i.online:
        break
    t1 = time.ticks_ms()
    i._reconnect()
    longest = max(longest, ms(t1))
    time.sleep_ms(50)
check("there: connected by the poll loop's steps", i.online, i.hw)
check("... no step held the Stump", longest < 300, longest)
i._close_socket()

# Nobody on that port: refused, said, no wait
t0 = time.ticks_ms()
j = WiFiSerialInterface({"name": "Heltec", "target_host": "127.0.0.1", "target_port": 47634})
for _ in range(40):
    if j._pending is None:
        break
    j._reconnect()
    time.sleep_ms(50)
check("not there (refused): not online, the error kept for /admin", not j.online and j.hw["error"], j.hw)
check("... found out quickly", ms(t0) < 2500, ms(t0))

# Nothing answers at all (an address nobody has): each step is quick, and
# it gives up after CONNECT_WAIT_S -- not TCP's 20 s
k = WiFiSerialInterface({"name": "Heltec", "target_host": "10.255.255.1", "target_port": 7633})
k.CONNECT_WAIT_S = 1
t0 = time.ticks_ms()
longest = 0
while k._pending is not None and ms(t0) < 6000:
    t1 = time.ticks_ms()
    k._reconnect()
    longest = max(longest, ms(t1))
    time.sleep_ms(50)
check("nobody answers: given up on its own time", k._pending is None and not k.online and ms(t0) < 3000, (ms(t0), k.hw))
check("... and no step held the Stump", longest < 300, longest)
srv.close()
print('FAILURES:', FAIL)
