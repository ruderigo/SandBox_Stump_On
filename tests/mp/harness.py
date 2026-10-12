# Test harness: loads barkeep under MicroPython with a temp SD tree, an admin
# password "pw", and fake stream objects, so requests run through the real
# request handler. Use: exec(open(HARNESS).read()) then req(...).
import sys, os
class _M: pass
_m = _M(); _m.aes = lambda *a, **k: None
sys.modules['ucryptolib'] = _m; sys.modules['cryptolib'] = _m
sys.path.insert(0, '.')
ROOT = os.getcwd() + '/_sd_web'
os.system('rm -rf %s && mkdir -p %s/shared %s/tools %s/home' % (ROOT, ROOT, ROOT, ROOT))
import fserv
fserv.SD_MOUNT = ROOT; fserv.SHARED_DIR = ROOT + '/shared'; fserv.TOOLS_DIR = ROOT + '/tools'
fserv.HOME_DIR = ROOT + '/home'; fserv.LEDGER_FILE = ROOT + '/ledger.json'
fserv.AWAITING_FILE = ROOT + '/awaiting.json'; fserv.sd_ok = True
import billboard
billboard.storage_file = lambda: ROOT + '/billboard.txt'
import barkeep
barkeep._check_admin_pw = lambda pw: pw == 'pw'
import uasyncio as asyncio, ujson as json


class Rd:
    def __init__(s, lines, body=b''):
        s.lines = list(lines); s.body = body
    async def readline(s):
        return s.lines.pop(0) if s.lines else b''
    async def read(s, n=-1):
        if n < 0: n = len(s.body)
        out, s.body = s.body[:n], s.body[n:]
        return out
    async def readexactly(s, n):
        return await s.read(n)


class Wr:
    def __init__(s, ip='192.168.4.50'):
        s.w = []; s.ip = ip
    def get_extra_info(s, n): return (s.ip, 1)
    async def awrite(s, b, *a):
        s.w.append(b.encode() if isinstance(b, str) else bytes(b))
    def write(s, b):
        s.w.append(b.encode() if isinstance(b, str) else bytes(b))
    async def drain(s): pass
    async def aclose(s): pass
    def close(s): pass
    async def wait_closed(s): pass


def req(path, body=b'', headers=(), method=None, declared=None):
    """-> (status, content_type, body_text)"""
    method = method or ('POST' if body or declared is not None else 'GET')
    hl = [('%s %s HTTP/1.1\r\n' % (method, path)).encode()]
    if method == 'POST':
        hl.append(('Content-Length: %d\r\n' % (len(body) if declared is None else declared)).encode())
    hl += [(h + '\r\n').encode() for h in headers] + [b'\r\n']
    w = Wr(); asyncio.run(barkeep._handle(Rd(hl, body), w))
    raw = b''.join(w.w); head, _, out = raw.partition(b'\r\n\r\n')
    head = head.decode()
    ct = [l.split(': ', 1)[1] for l in head.split('\r\n') if l.lower().startswith('content-type')]
    return head.split('\r\n')[0][9:], (ct[0] if ct else '-'), out.decode('utf-8', 'replace')
