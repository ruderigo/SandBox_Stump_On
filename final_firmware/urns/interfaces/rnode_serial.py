# µReticulum RNode over USB serial -- a Heltec (or any RNode) plugged into
# a computer running Stump (docs/PC.md).
#
# The same RNode protocol as WiFiSerialInterface -- real KISS framing and
# the radio set-up commands sent on every connect -- with a USB serial
# port underneath instead of a TCP socket. Only the transport changes, so
# the protocol code (tested on the air with the CAM's Heltec bridge) is
# shared rather than copied: _SerialPort gives the serial port the few
# socket calls WiFiSerialInterface makes (settimeout, sendall, readinto,
# close).
#
# Needs pyserial, so it runs on a computer (CPython), not on the ESP32.
#
# config.py:
#   {"type": "RNodeSerialInterface", "name": "Heltec (USB)", "enabled": True,
#    "port": "/dev/cu.usbserial-0001",     # "COM5" on Windows; "auto" finds it
#    "frequency": 915000000, "bandwidth": 125000, "txpower": 7,
#    "spreadingfactor": 8, "codingrate": 5}

import time
from .wifi_serial import (WiFiSerialInterface, FEND, CMD_DETECT, DETECT_REQ, CMD_FW_VERSION,
                          CMD_PLATFORM)
from ..log import log, LOG_NOTICE, LOG_ERROR

HANDSHAKE_S = 3.0     # how long an RNode has to answer "are you an RNode?"

BAUD = 115200
BOOT_WAIT_S = 2.5     # opening the port resets most ESP32 boards; let it boot

# USB-serial chips found on RNode boards (Heltec V3: CP2102; others CH340/CH9102,
# or the ESP32-S3's own USB), for "port": "auto".
_KNOWN_VIDS = (0x10C4, 0x1A86, 0x303A, 0x0403)


def find_port():
    """The first serial port that looks like an RNode board, or None."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return None
    for p in sorted(list_ports.comports(), key=lambda p: p.device):
        if p.vid in _KNOWN_VIDS:
            return p.device
    return None


def describe_port(device):
    """"CP2102 USB to UART Bridge Controller (Silicon Labs)" for a port, so
    the right board can be told apart on a hub; None if unknown."""
    try:
        from serial.tools import list_ports
        for p in list_ports.comports():
            if p.device == device:
                bits = [b for b in (p.product or p.description, p.manufacturer) if b and b != "n/a"]
                return " · ".join(bits) or None
    except Exception:
        pass
    return None


class _SerialPort:
    """A serial port that answers the socket calls WiFiSerialInterface makes."""

    def __init__(self, device):
        import serial
        self._serial = serial
        self.s = serial.Serial(device, BAUD, timeout=0, write_timeout=2,
                               rtscts=False, dsrdtr=False)

    def settimeout(self, t):
        pass                   # reads never block (timeout=0); writes have write_timeout

    def sendall(self, data):
        try:
            self.s.write(data)
        except self._serial.SerialException as e:
            raise OSError(5, str(e))

    def readinto(self, buf):
        try:
            n = min(len(buf), self.s.in_waiting)
            if not n:
                raise OSError(11, "no data")       # EAGAIN, as a non-blocking socket says
            data = self.s.read(n)
        except self._serial.SerialException as e:
            raise OSError(5, str(e))               # unplugged: poll_loop goes offline and retries
        buf[:len(data)] = data
        return len(data)

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


class RNodeSerialInterface(WiFiSerialInterface):
    # USB doesn't drop an idle link the way the Heltec's Wi-Fi mode does: no
    # keepalive frames needed (or wanted -- nothing should go to the radio
    # that isn't a packet).
    KEEPALIVE_INTERVAL = 10 ** 9

    def __init__(self, config):
        port = config.get("port", "auto")
        if port in (None, "", "auto"):
            port = find_port() or "auto"
        self.port = port
        config = dict(config)
        config.setdefault("name", "Heltec (USB)")
        config["target_host"] = port           # WiFiSerialInterface requires one; used in its logs
        super().__init__(config)

    def _connect(self):
        port = self.port
        if port == "auto":
            port = find_port()
            if not port:
                raise OSError(19, "no RNode found on USB (plug the Heltec in)")
            self.port = self.target_host = port
        self.hw["device"] = describe_port(port)
        s = _SerialPort(port)
        time.sleep(BOOT_WAIT_S)
        try:
            s.s.reset_input_buffer()           # the board's boot messages aren't KISS
        except Exception:
            pass
        self._socket = s
        self._in_frame = False
        self._escape = False
        self._command = None
        self._buffer = bytearray()
        # The handshake: an RNode answers DETECT, and says its firmware.
        self.hw["detected"] = False
        self._send_command(CMD_DETECT, bytes([DETECT_REQ]))
        self._send_command(CMD_FW_VERSION, b"\x00")
        self._send_command(CMD_PLATFORM, b"\x00")
        t0 = time.time()
        while not self.hw["detected"] and time.time() - t0 < HANDSHAKE_S:
            try:
                n = s.readinto(self._recv_buf)
                for i in range(n):
                    self._process_byte(self._recv_mv[i])
            except OSError as e:
                if e.args and e.args[0] != 11:
                    raise
                time.sleep(0.05)
        if not self.hw["detected"]:
            s.close()
            self._socket = None
            raise OSError(5, "%s answered nothing to the RNode handshake: is the RNode firmware on it "
                             "(rnodeconf --autoinstall), and nothing else using the port?" % port)
        self.online = True
        self._reconnect_count = 0
        self._last_activity = time.time()
        self.hw["error"] = None
        self.hw["since"] = time.time()
        log("RNode on USB: %s (%s), firmware %s" % (port, self.hw.get("device") or "?",
                                                    self.hw.get("fw") or "?"), LOG_NOTICE)
        self._init_radio()

    def prime(self):
        pass

    def status(self):
        h = WiFiSerialInterface.status(self)
        h["kind"] = "usb"
        h["where"] = self.port
        return h

    def __str__(self):
        return "RNodeSerialInterface[" + self.name + "]"
