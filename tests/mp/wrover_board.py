# A Stump on an ESP32-WROVER board (Freenove ESP32-WROVER v3.0,
# 1.0.0-beta.56): its SD slot's pins, the voice engines served from the
# card when they aren't in flash.
import sys
exec(open(sys.argv[1] + '/harness.py').read())
import fserv, barkeep, os
FAIL = []


def check(n, c, i=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else '  ' + repr(i)[:300]))
    if not c:
        FAIL.append(n)


S3 = "ESP32S3 module with Octal-SPIRAM with ESP32S3"
WROVER = "Generic ESP32 module with SPIRAM with ESP32"      # what the real board says
check("SD pins on the S3-CAM: unchanged (CLK 39, CMD 38, D0 40)",
      fserv.sd_pins(S3) == {"slot": 1, "width": 1, "sck": 39, "cmd": 38, "data": (40,)})
check("SD pins on a WROVER: slot 1's fixed pins, none given", fserv.sd_pins(WROVER) == {"slot": 1, "width": 1})

# The voice engines: from flash on a CAM; from <card>/web where the
# Provisioner put them on a WROVER.
moved = []
for n in ("opus.wasm", "codec2.wasm"):
    try:
        os.rename("web/" + n, "web/" + n + ".away")
        moved.append(n)
    except OSError:
        pass
os.system('mkdir -p %s/web' % ROOT)
open(ROOT + '/web/opus.wasm', 'wb').write(b'\x00asm-from-the-card')
s, ct, b = req('/opus.wasm')
check("a voice engine not in flash: served from the SD card", s.startswith('200') and 'asm-from-the-card' in b, (s, b[:60]))
s, ct, b = req('/codec2.wasm')
check("... one on neither: 404, said plainly", s.startswith('404'), s)
for n in moved:
    os.rename("web/" + n + ".away", "web/" + n)
s, ct, b = req('/opus.wasm')
check("in flash (a CAM): flash first", s.startswith('200') and 'asm-from-the-card' not in b[:40])
print('FAILURES:', FAIL)
