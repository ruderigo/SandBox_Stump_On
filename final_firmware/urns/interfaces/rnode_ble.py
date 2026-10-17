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
from .rnode_serial import RNodeSerialInterface
from .wifi_serial import WiFiSerialInterface, CMD_RADIO_STATE, RADIO_STATE_OFF, CMD_LEAVE

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

    def stop(self):
        self._run = False

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
                    self.error = ("no RNode found over Bluetooth%s: is the Heltec on, with Bluetooth on "
                                  "(rnodeconf <port> --bluetooth-on) and paired with this computer?"
                                  % ("" if self.target == "auto" else " named " + self.target))
                    await asyncio.sleep(RETRY_S)
                    continue
                self.name, self.address = dev.name, dev.address
                gone = asyncio.Event()

                def on_disconnect(_client):
                    self.connected = False
                    gone.set()

                def on_rx(_char, data):
                    with self._lock:
                        self._rx += data

                async with BleakClient(dev, disconnected_callback=on_disconnect, timeout=CONNECT_S) as c:
                    rx = c.services.get_service(UART_SERVICE).get_characteristic(UART_RX)
                    await c.start_notify(UART_TX, on_rx)
                    size = max(20, getattr(rx, "max_write_without_response_size", 20) or 20)
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
                            await c.write_gatt_char(rx, chunk, response=False)
                        else:
                            await asyncio.sleep(0.02)
                self.connected = False
                if self._drop:
                    self._drop = False
                elif self._run:
                    self.error = "the Bluetooth link to %s dropped (it reconnects by itself)" % (self.name or "the Heltec")
            except Exception as e:
                self.connected = False
                self.error = ("Bluetooth: %s -- paired? (rnodeconf <port> --bluetooth-pair shows a PIN; "
                              "pair from this computer's Bluetooth settings)" % (str(e) or e.__class__.__name__))
            if self._run:
                await asyncio.sleep(RETRY_S)


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

    def _connect(self):
        try:
            RNodeSerialInterface._connect(self)
        except OSError as e:
            if self._ble is not None and self._ble.connected and "handshake" in str(e):
                # Connected but nothing came back: start the Bluetooth link
                # over (a subscription made before the bond is dropped).
                self._ble.drop()
                raise OSError(5, "the Heltec answered nothing over Bluetooth yet (reconnecting it); "
                                 "if it keeps on: forget it in this computer's Bluetooth settings and pair again")
            raise

    def _open_failed_text(self):
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
            b.stop()

    def where(self):
        b = self._ble
        if b is not None and b.address:
            return "Bluetooth %s" % (b.name or b.address)
        return "Bluetooth" + ("" if self.target == "auto" else " " + self.target)
