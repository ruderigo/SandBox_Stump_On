import sys
class _M: pass
_m = _M(); _m.aes = lambda *a, **k: None
sys.modules['ucryptolib'] = _m; sys.modules['cryptolib'] = _m
sys.path.insert(0, '.')
import config
config.AUTH_ADMIN_PASSWORD = 'pw'; config.FSERVBOT_OP_PASSWORD = 'op'
import rrc, i18n
NEW = True
if NEW:
    import plugins; plugins.load_all()
else:
    for n in ('fservbot', 'stumpid'):
        m = __import__(n + '.install', None, None, ('activate',)); m.activate()
from urns.identity import Identity
ident = Identity(create_keys=False)
ident.load_private_key(bytes(range(64)))
A, B, C = '192.168.4.50', '192.168.4.51', '192.168.4.52'
for c in (A, B, C): i18n.set_lang(c, 'en')
NONCE = [None]
def say(cid, line):
    r, nr = rrc.handle_input(cid, rrc.get_user(cid)['room'], line)
    if nr: rrc.touch_user(cid, room=nr)
    out = []
    for x in r:
        if x.startswith('AUTH-CHALLENGE '):
            nonce = x.split()[1]
            out.append('AUTH-CHALLENGE <nonce>')
            NONCE[0] = nonce
        else:
            out.append(x)
    print('>>', cid[-2:], line, '->', out, nr)
def auth(cid):
    say(cid, '/auth')
    sig = ident.sign(NONCE[0].encode()).hex()
    say(cid, '/auth ' + ident.get_public_key().hex() + ' ' + sig)
say(A, '/nick alice'); say(B, '/nick bob'); say(C, '/nick carol')
for mode in ('hybrid', 'mandatory'):
    say(A, '/admin pw mode ' + mode)
    for line in ('hello', '/join x', '/msg alice hi', '/me waves', '/topic', '/topic t', '/rooms', '/names',
                 '/whoami', '/whoami x', '/help', '/fslist', '/fsset op prefix ?', '/fsset op prefix !', '!list', '/invite alice', '/nick bobby', '/nick bob'):
        say(B, line)
say(A, '/admin pw mode open')
say(A, '/admin pw room vip minted'); say(A, '/admin pw room club hybrid')
say(B, '/rooms'); say(B, '/join vip'); say(B, '/join club')
auth(C); say(C, '/whoami'); say(C, '/nick carla'); say(C, '/whoami')
say(C, '/join club'); say(C, '/invite bob'); say(B, '/join club'); say(B, '/join vip'); say(C, '/join vip')
say(A, '/admin pw mode mandatory'); say(C, 'verified post'); say(C, '/fslist'); say(B, '/auth'); say(B, '/admin pw meshroom')
say(A, '/admin pw revoke ' + ident.hexhash); say(C, '/whoami')
say(A, '/adminx'); say(A, '/admin pw'); say(A, '/admin pw bogus')
