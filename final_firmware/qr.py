# Project Stump -- qr.py
#
# A QR code, as an SVG, for short text (the Stump's address link on
# its /address page): byte mode, error correction M, versions 1-20 (up to
# 666 bytes). Made on
# the Stump itself, so the page needs no internet and no script.
#
# The algorithm is the QR standard's (ISO/IEC 18004), in the shape of
# Project Nayuki's reference implementation (MIT): the function patterns,
# the data in Reed-Solomon blocks, interleaved, laid in the zigzag, then
# the mask with the lowest penalty. tests/mp/qr_test.py checks every
# module against an independent encoder (segno), for each mask.

# Error correction M, versions 1-20: error codewords per block, and blocks.
_ECC = (10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26)
_BLOCKS = (1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16)
MAX_VERSION = 20


def _raw_modules(ver):
    r = (16 * ver + 128) * ver + 64
    if ver >= 2:
        n = ver // 7 + 2
        r -= (25 * n - 10) * n - 55
        if ver >= 7:
            r -= 36
    return r


def _data_codewords(ver):
    return _raw_modules(ver) // 8 - _ECC[ver - 1] * _BLOCKS[ver - 1]


def _align(ver, size):
    if ver == 1:
        return []
    n = ver // 7 + 2
    step = (ver * 4 + n * 2 + 1) // (n * 2 - 2) * 2
    return [6] + [size - 7 - i * step for i in range(n - 2, -1, -1)]


def _mul(x, y):
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _divisor(degree):
    r = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            r[j] = _mul(r[j], root)
            if j + 1 < degree:
                r[j] ^= r[j + 1]
        root = _mul(root, 2)
    return r


def _remainder(data, div):
    r = [0] * len(div)
    for b in data:
        f = b ^ r.pop(0)
        r.append(0)
        for i in range(len(div)):
            r[i] ^= _mul(div[i], f)
    return r


def _codewords(data, ver):
    """The data bytes (byte mode, padded) with their error codewords,
    interleaved as the symbol carries them."""
    bits = []

    def put(v, n):
        for i in range(n - 1, -1, -1):
            bits.append((v >> i) & 1)
    put(4, 4)
    put(len(data), 8 if ver < 10 else 16)
    for b in data:
        put(b, 8)
    cap = _data_codewords(ver) * 8
    put(0, min(4, cap - len(bits)))
    put(0, (-len(bits)) % 8)
    pad = 0xEC
    while len(bits) < cap:
        put(pad, 8)
        pad ^= 0xEC ^ 0x11
    words = [int("".join(str(b) for b in bits[i:i + 8]), 2) for i in range(0, len(bits), 8)]
    nb, ecl = _BLOCKS[ver - 1], _ECC[ver - 1]
    raw = _raw_modules(ver) // 8
    short = nb - raw % nb
    slen = raw // nb
    div = _divisor(ecl)
    blocks, k = [], 0
    for i in range(nb):
        dat = words[k:k + slen - ecl + (0 if i < short else 1)]
        k += len(dat)
        ecc = _remainder(dat, div)
        if i < short:
            dat.append(0)
        blocks.append(dat + ecc)
    out = []
    for i in range(len(blocks[0])):
        for j in range(nb):
            if i != slen - ecl or j >= short:
                out.append(blocks[j][i])
    return out


def _format_bits(mask):
    data = (0 << 3) | mask                      # M is 0b00
    r = data
    for _ in range(10):
        r = (r << 1) ^ ((r >> 9) * 0x537)
    return (data << 10 | r) ^ 0x5412


def _mask_bit(m, x, y):
    if m == 0:
        return (x + y) % 2 == 0
    if m == 1:
        return y % 2 == 0
    if m == 2:
        return x % 3 == 0
    if m == 3:
        return (x + y) % 3 == 0
    if m == 4:
        return (x // 3 + y // 2) % 2 == 0
    if m == 5:
        return x * y % 2 + x * y % 3 == 0
    if m == 6:
        return (x * y % 2 + x * y % 3) % 2 == 0
    return ((x + y) % 2 + x * y % 3) % 2 == 0


class _Grid:
    def __init__(self, ver):
        self.ver = ver
        self.size = n = ver * 4 + 17
        self.m = [bytearray(n) for _ in range(n)]       # dark: 1
        self.f = [bytearray(n) for _ in range(n)]       # a function module: 1

    def fn(self, x, y, dark):
        self.m[y][x] = 1 if dark else 0
        self.f[y][x] = 1

    def patterns(self):
        n = self.size
        for i in range(n):
            self.fn(6, i, i % 2 == 0)
            self.fn(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (n - 4, 3), (3, n - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < n and 0 <= y < n:
                        self.fn(x, y, max(abs(dx), abs(dy)) not in (2, 4))
        pos = _align(self.ver, n)
        last = len(pos) - 1
        for i in range(len(pos)):
            for j in range(len(pos)):
                if (i == 0 and j == 0) or (i == 0 and j == last) or (i == last and j == 0):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self.fn(pos[i] + dx, pos[j] + dy, max(abs(dx), abs(dy)) != 1)
        self.format(0)
        if self.ver >= 7:
            r = self.ver
            for _ in range(12):
                r = (r << 1) ^ ((r >> 11) * 0x1F25)
            bits = self.ver << 12 | r
            for i in range(18):
                b = (bits >> i) & 1
                a, c = n - 11 + i % 3, i // 3
                self.fn(a, c, b)
                self.fn(c, a, b)

    def format(self, mask):
        bits, n = _format_bits(mask), self.size
        b = lambda i: (bits >> i) & 1
        for i in range(6):
            self.fn(8, i, b(i))
        self.fn(8, 7, b(6))
        self.fn(8, 8, b(7))
        self.fn(7, 8, b(8))
        for i in range(9, 15):
            self.fn(14 - i, 8, b(i))
        for i in range(8):
            self.fn(n - 1 - i, 8, b(i))
        for i in range(8, 15):
            self.fn(8, n - 15 + i, b(i))
        self.fn(8, n - 8, 1)

    def place(self, words):
        n, i, total = self.size, 0, len(words) * 8
        right = n - 1
        while right >= 1:
            if right == 6:
                right = 5
            up = ((right + 1) & 2) == 0
            for v in range(n):
                y = n - 1 - v if up else v
                for j in range(2):
                    x = right - j
                    if not self.f[y][x] and i < total:
                        self.m[y][x] = (words[i >> 3] >> (7 - (i & 7))) & 1
                        i += 1
            right -= 2

    def apply(self, mask):
        n = self.size
        for y in range(n):
            row, fr = self.m[y], self.f[y]
            for x in range(n):
                if not fr[x] and _mask_bit(mask, x, y):
                    row[x] ^= 1

    def penalty(self):
        n, m, score = self.size, self.m, 0

        def add(hist, run):
            if hist[0] == 0:
                run += n
            hist.insert(0, run)
            del hist[7:]

        def count(h):
            c = h[1]
            core = c > 0 and h[2] == h[4] == h[5] == c and h[3] == c * 3
            return ((1 if core and h[0] >= c * 4 and h[6] >= c else 0)
                    + (1 if core and h[6] >= c * 4 and h[0] >= c else 0))

        for horiz in (True, False):
            for a in range(n):
                color, run, hist = 0, 0, [0] * 7
                for b in range(n):
                    v = m[a][b] if horiz else m[b][a]
                    if v == color:
                        run += 1
                        if run == 5:
                            score += 3
                        elif run > 5:
                            score += 1
                    else:
                        add(hist, run)
                        if not color:
                            score += count(hist) * 40
                        color, run = v, 1
                if color:
                    add(hist, run)
                    run = 0
                add(hist, run + n)          # (the light border after the last run)
                score += count(hist) * 40
        for y in range(n - 1):
            r0, r1 = m[y], m[y + 1]
            for x in range(n - 1):
                c = r0[x]
                if c == r0[x + 1] == r1[x] == r1[x + 1]:
                    score += 3
        dark = sum(sum(r) for r in m)
        total = n * n
        score += ((abs(dark * 20 - total * 10) + total - 1) // total - 1) * 10
        return score


def matrix(text, mask=None, version=None):
    """The QR code's modules for text (str or bytes): [bytearray] rows,
    1 dark. mask/version: forced (tests); else the smallest version and
    the mask with the lowest penalty."""
    data = text.encode() if isinstance(text, str) else bytes(text)
    ver = version
    if ver is None:
        for v in range(1, MAX_VERSION + 1):
            if 4 + (8 if v < 10 else 16) + 8 * len(data) <= _data_codewords(v) * 8:
                ver = v
                break
        if ver is None:
            raise ValueError("too long for a QR code here")
    words = _codewords(data, ver)
    best, best_score = None, None
    for mk in ([mask] if mask is not None else range(8)):
        g = _Grid(ver)
        g.patterns()
        g.place(words)
        g.apply(mk)
        g.format(mk)
        if mask is not None:
            return g.m
        s = g.penalty()
        if best is None or s < best_score:
            best, best_score = g, s
    return best.m


def svg(text, px=6, border=4):
    """The QR code as an SVG: dark on white whatever the page's theme
    (scanners want that), crisp at any size."""
    m = matrix(text)
    n = len(m)
    path = []
    for y in range(n):
        row, x = m[y], 0
        while x < n:
            if row[x]:
                s = x
                while x < n and row[x]:
                    x += 1
                path.append("M%d %dh%dv1h-%dz" % (s + border, y + border, x - s, x - s))
            else:
                x += 1
    w = n + 2 * border
    return ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 %d %d' width='%d' height='%d' "
            "shape-rendering='crispEdges' role='img'><rect width='%d' height='%d' fill='#fff'/>"
            "<path fill='#000' d='%s'/></svg>") % (w, w, w * px, w * px, w, w, "".join(path))
