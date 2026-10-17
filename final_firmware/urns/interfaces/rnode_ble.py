# µReticulum RNode over Bluetooth (BLE) -- a Heltec paired with the
# computer running Stump, no cable (docs/PC.md).
#
# The same RNode protocol as on USB (RNodeSerialInterface: the handshake,
# the radio set-up, the "still there?" checks), carried over the RNode
# firmware's Bluetooth serial service (Nordic UART: write to RX, notified on
# TX), as reference RNS does (RNS.Interfaces.RNodeInterface.BLEConnection).
#
# Bluetooth runs in its own thread with its own asyncio loop (bleak): it
# looks for the Heltec, connects, and stays connected, reconnecting by
# itself; the interface only ever sees a socket-like port (_BLEPort) that
# is either connected or not, so nothing here blocks the node for long.
#
# Needs bleak, so it runs on a computer (CPython), not on the ESP32. The
# Heltec needs Bluetooth on and to be paired with the computer once:
#   rnodeconf <port> --bluetooth-on     (then --bluetooth-pair shows a PIN;
#   pair from the computer's Bluetooth settings, or when it asks)
#
# config.py:
#   {"type": "RNodeBLEInterface", "name": "Heltec (Bluetooth)", "enabled": True,
#    "target": "auto",            # or its name ("RNode 3B87") or address
#    "frequency": 915000000, "bandwidth": 125000, "txpower": 7,
#    "spreadingfactor": 8, "codingrate": 5}

import threading
import time
from . import rnode_serial
from .rnode_serial import RNodeSerialInterface
from .wifi_serial import WiFiSerialInterface, CMD_RADIO_STATE, RADIO_STATE_OFF, CMD_LEAVE
from ..log import log, LOG_NOTICE, LOG_VERBOSE

UART_SERVICE = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
UART_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"     # we write here
UART_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"     # it notifies here

SCAN_S = 5.0
CONNECT_S = 15.0
RETRY_S = 3.0
# After connecting, a moment before the handshake (reference RNS waits
# 2 s), and a longer handshake than on USB (it waits 5 s over BLE).
SETTLE_S = 1.5
HANDSHAKE_BLE_S = 6.0
# While a Bluetooth connection here goes nowhere (not paired yet, the
# wrong device), the Heltec counts itself "connected": it ignores pairing
# mode and hides from other devices. So attempts that fail back off.
MAX_RETRY_S = 30.0
# A fresh start, what switching USB -> Bluetooth in /admin did by hand:
# this computer's Bluetooth side thrown away and started again (its own
# thread, a new connection), and -- when the Heltec is also on USB
# (charging) -- the Heltec restarted through the cable (the RNode's reset
# command), clearing whatever Bluetooth state it kept. The Heltec restart
# at start-up; the whole fresh start after KICK_AFTER handshakes in a row
# that got no answer, and (cable plugged) after MISS_KICK scans in a row
# that didn't see it -- at most every FRESH_EVERY s. KICK_BOOT_S for it to
# boot and advertise again.
KICK_AFTER = 2
KICK_BOOT_S = 4.0
MISS_KICK = 3
FRESH_EVERY = 120.0
# Before subscribing to what it says: one write that makes the computer
# encrypt the link with the saved pairing (or pair, the first time).
# Subscribed before that, macOS may drop the subscription when the link
# gets encrypted, and the RNode's answers never arrive (silent handshake).
ENCRYPT_WAIT_S = 40.0
_CMD_RESET = bytes([0xC0, 0x55, 0xF8, 0xC0])
_DETECT = bytes([0xC0, 0x08, 0x73, 0xC0])
_DETECT_RESP = bytes([0xC0, 0x08, 0x46])


def _matches(target, device, adv):
    name = getattr(device, "name", None) or getattr(adv, "local_name", None) or ""
    if target in (None, "", "auto"):
        uuids = [u.lower() for u in (getattr(adv, "service_uuids", None) or [])]
        return name.startswith("RNode ") or UART_SERVICE in uuids
    t = target.lower()
    return t == (device.address or "").lower() or t == name.lower()


class _BLEPort:
    """The Bluetooth link to the Heltec, kept up in a thread, with the
    socket calls the RNode interface makes (sendall, readinto, close)."""

    def __init__(self, target):
        self.target = target or "auto"
        self.connected = False
        self.error = None
        self.name = None
        self.address = None
        self._rx = bytearray()
        self._tx = bytearray()
        self._lock = threading.Lock()
        self._run = True
        self._drop = False
        self.connected_at = 0
        self.fails = 0               # Bluetooth attempts in a row that went nowhere
        self.probe = False           # pairing check: ask "are you an RNode?" itself
        self.paired = False          # it answered over Bluetooth: the link is encrypted
        self.misses = 0              # scans in a row that didn't see it
        self._thread = threading.Thread(target=self._main, daemon=True, name="stump-ble")
        self._thread.start()

    # -- the socket side (the node's thread) --------------------------------

    def settimeout(self, t):
        pass

    def sendall(self, data):
        if not self.connected:
            raise OSError(5, "Bluetooth link down")
        with self._lock:
            self._tx += data

    def readinto(self, buf):
        with self._lock:
            if not self._rx:
                if not self.connected:
                    raise OSError(5, "Bluetooth link down")
                raise OSError(11, "no data")
            n = min(len(buf), len(self._rx))
            buf[:n] = self._rx[:n]
            del self._rx[:n]
        return n

    def pending(self):
        with self._lock:
            return len(self._tx)

    def reset(self):
        with self._lock:
            self._rx = bytearray()
            self._tx = bytearray()

    def close(self):
        """Ends the session (the thread stays, to connect again when asked)."""
        self.reset()

    def stop(self, wait=0):
        """Ends the thread; with wait, gives it that long to disconnect
        properly, so the Heltec sees this computer leave (and advertises
        again) instead of waiting on a link that's gone."""
        self._run = False
        if wait and self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(wait)

    def drop(self):
        """Disconnect and connect again from scratch: after a first pairing,
        macOS may have dropped the subscription made before the bond, so
        the link is up but carries nothing (reference RNS reconnects too)."""
        self._drop = True

    # -- the Bluetooth side (its own thread and asyncio loop) ---------------

    def _main(self):
        try:
            import asyncio
            import bleak  # noqa: F401
        except ImportError:
            self.error = "bleak isn't installed (python3 provisioner.py --pc installs it)"
            return
        try:
            asyncio.run(self._loop())
        except Exception as e:
            self.error = "Bluetooth stopped: %s" % e
            self.connected = False

    async def _loop(self):
        import asyncio
        from bleak import BleakClient, BleakScanner
        while self._run:
            try:
                dev = await BleakScanner.find_device_by_filter(
                    lambda d, a: _matches(self.target, d, a), timeout=SCAN_S)
                if dev is None:
                    self.misses += 1
                    self.error = ("no RNode found over Bluetooth%s: is the Heltec on, with Bluetooth on "
                                  "(rnodeconf <port> --bluetooth-on) and paired with this computer?"
                                  % ("" if self.target == "auto" else " named " + self.target))
                    await asyncio.sleep(RETRY_S)
                    continue
                self.misses = 0
                self.name, self.address = dev.name, dev.address
                gone = asyncio.Event()

                def on_disconnect(_client):
                    self.connected = False
                    gone.set()

                def on_rx(_char, data):
                    with self._lock:
                        self._rx += data
                        if _DETECT_RESP in bytes(self._rx[-64:]):
                            self.paired = True     # it answers: encrypted, paired
                            self.fails = 0

                async with BleakClient(dev, disconnected_callback=on_disconnect, timeout=CONNECT_S) as c:
                    rx = c.services.get_service(UART_SERVICE).get_characteristic(UART_RX)
                    size = max(20, getattr(rx, "max_write_without_response_size", 20) or 20)
                    # The RNode's RX takes writes WITH a reply (and needs an
                    # encrypted link): writing so makes the computer encrypt
                    # with the saved pairing, or pair (ask the code) the first
                    # time. A write without reply there was never answered.
                    props = [p.lower() for p in (getattr(rx, "properties", None) or [])]
                    reply = "write-without-response" not in props
                    if reply:
                        # Encrypted first (a lone frame end: nothing to the
                        # RNode), subscribed after.
                        try:
                            await asyncio.wait_for(c.write_gatt_char(rx, b"\xc0", response=True), ENCRYPT_WAIT_S)
                        except Exception:
                            pass
                    await c.start_notify(UART_TX, on_rx)
                    last_ask = 0
                    self.reset()
                    self.error = None
                    self._drop = False
                    self.connected_at = time.time()
                    self.connected = True
                    while self._run and not gone.is_set() and not self._drop:
                        with self._lock:
                            chunk = bytes(self._tx[:size])
                            del self._tx[:size]
                        if chunk:
                            await c.write_gatt_char(rx, chunk, response=reply)
                        elif self.probe and not self.paired and time.time() - last_ask > 2:
                            last_ask = time.time()
                            await c.write_gatt_char(rx, _DETECT, response=reply)
                        else:
                            await asyncio.sleep(0.02)
                self.connected = False
                if self._drop:
                    self._drop = False
                elif self._run:
                    self.error = "the Bluetooth link to %s dropped (it reconnects by itself)" % (self.name or "the Heltec")
            except Exception as e:
                self.connected = False
                self.error = ("Bluetooth: %s -- paired? (/admin -> Radio -> Bluetooth -> Pair this computer)"
                              % (str(e) or e.__class__.__name__))
            if self._run:
                if not self.paired:
                    self.fails += 1
                await asyncio.sleep(min(MAX_RETRY_S, RETRY_S * (2 ** min(self.fails, 4))) if self.fails else RETRY_S)


class RNodeBLEInterface(RNodeSerialInterface):
    KIND = "ble"
    HANDSHAKE_WAIT = HANDSHAKE_BLE_S
    # Bluetooth is slower to say it's gone than a USB port: the link's own
    # disconnect, or the probe, whichever comes first.
    PROBE_WAIT = 6.0
    LOOK_EVERY = 1.0

    def __init__(self, config):
        config = dict(config)
        config.setdefault("name", "Heltec (Bluetooth)")
        self.target = config.get("target") or "auto"
        self._ble = None
        self._kicked = False
        self._silent = 0
        self._fresh_at = 0
        config["port"] = "ble://" + self.target      # for RNodeSerialInterface's bookkeeping
        RNodeSerialInterface.__init__(self, config)

    def _link(self):
        if self._ble is None:
            self._ble = _BLEPort(self.target)
        return self._ble

    def _find(self):
        return "ble" if self._link().connected else None

    def _present(self):
        return self._link().connected

    def _open(self):
        b = self._link()
        if not b.connected:
            raise OSError(19, b.error or "looking for the Heltec over Bluetooth...")
        wait = SETTLE_S - (time.time() - b.connected_at)
        if wait > 0:
            time.sleep(wait)
        self.hw["device"] = b.name
        b.reset()
        return b

    def _usb_kick(self):
        """Restarts the Heltec through its USB cable, if it's plugged in:
        the port opened (that alone restarts many ESP32 boards), the RNode's
        reset command, closed. True if done. Never while a Bluetooth
        session is up."""
        if self._ble is not None and self._ble.connected and self.online:
            return False
        try:
            port = rnode_serial.find_port()
            if not port:
                return False
            s = rnode_serial._SerialPort(port)
            try:
                time.sleep(rnode_serial.BOOT_WAIT_S)     # if opening restarted it: booted by now
                s.sendall(_CMD_RESET)
                time.sleep(0.3)
            finally:
                s.close()
            self.hw["kicks"] = self.hw.get("kicks", 0) + 1
            log("Heltec restarted through its USB cable (%s), for a clean Bluetooth start" % port, LOG_NOTICE)
            return True
        except Exception as e:
            log("Couldn't restart the Heltec through USB: %s" % e, LOG_VERBOSE)
            return False

    def _fresh(self, why):
        """The USB -> Bluetooth switch, on its own: this computer's
        Bluetooth link closed properly and started over from nothing, the
        Heltec restarted in between when the cable's there."""
        if self.online:
            return False
        self._fresh_at = time.time()
        old, self._ble = self._ble, None
        self._socket = None
        if old is not None:
            old.stop(3)
        if self._usb_kick():
            time.sleep(KICK_BOOT_S)
        log("Bluetooth started over (%s)" % why, LOG_NOTICE)
        self._link()
        self._reconnect_count = 1               # and try again soon, not after the backoff
        self._last_reconnect = 0
        self._last_look = 0
        return True

    def _connect(self):
        if not self._kicked:
            # At start-up: the Heltec restarted through the cable, if it's
            # there, before this computer's Bluetooth looks for it.
            self._kicked = True
            if self._ble is None and self._usb_kick():
                time.sleep(KICK_BOOT_S)
        try:
            RNodeSerialInterface._connect(self)
            self._silent = 0
        except OSError as e:
            if self._ble is not None and self._ble.connected and "handshake" in str(e):
                # Connected but nothing came back: the Bluetooth link started
                # over; every KICK_AFTER such times, a whole fresh start.
                self._ble.fails += 1
                self._silent += 1
                if self._silent % KICK_AFTER == 0 and self._fresh("it answered nothing"):
                    raise OSError(5, "the Heltec answered nothing over Bluetooth: started the Bluetooth link "
                                     "over from scratch, connecting again")
                self._ble.drop()
                raise OSError(5, "the Heltec answered nothing over Bluetooth yet (reconnecting it); "
                                 "if it keeps on: forget it in this computer's Bluetooth settings and pair again")
            raise

    def _open_failed_text(self):
        b = self._link()
        if (b.misses >= MISS_KICK and time.time() - self._fresh_at > FRESH_EVERY
                and rnode_serial.find_port()):
            # Not seen for a while, and on the cable: it may be holding on to
            # a link that's gone (and not advertising). A fresh start.
            self._fresh("not seen over Bluetooth")
            b = self._link()
        self.hw["error"] = b.error or "looking for the Heltec over Bluetooth..."

    def _close_socket(self):
        # The Bluetooth link stays up (the thread keeps it): only this
        # session's buffers go.
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def _lost_text(self):
        return (self._link().error or "the Bluetooth link to the Heltec dropped") + ""

    def close(self):
        """Radio off and "the host left" (as on USB), given time to go out
        over Bluetooth before the link closes."""
        b = self._ble
        if self.online and self._socket and b is not None:
            try:
                self._send_command(CMD_RADIO_STATE, bytes([RADIO_STATE_OFF]))
                self._send_command(CMD_LEAVE, b"\xff")
            except Exception:
                pass
            t0 = time.time()
            while b.pending() and b.connected and time.time() - t0 < 2:
                time.sleep(0.05)
            time.sleep(0.1)
        WiFiSerialInterface.close(self)
        if b is not None:
            b.stop(3)            # disconnected properly: the Heltec free for the next start

    def where(self):
        b = self._ble
        if b is not None and b.address:
            return "Bluetooth %s" % (b.name or b.address)
        return "Bluetooth" + ("" if self.target == "auto" else " " + self.target)
