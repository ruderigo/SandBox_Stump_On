# A small CBOR (RFC 8949) codec: what RRC envelopes use. Integers, byte
# and text strings, lists, maps, booleans, null and floats (read only).
import struct


def _head(major, n, out):
    if n < 24:
        out.append(major << 5 | n)
    elif n < 0x100:
        out.append(major << 5 | 24)
        out.append(n)
    elif n < 0x10000:
        out.append(major << 5 | 25)
        out.extend(struct.pack(">H", n))
    elif n < 0x100000000:
        out.append(major << 5 | 26)
        out.extend(struct.pack(">I", n))
    else:
        out.append(major << 5 | 27)
        out.extend(struct.pack(">Q", n))


def _enc(v, out):
    if v is None:
        out.append(0xf6)
    elif v is True:
        out.append(0xf5)
    elif v is False:
        out.append(0xf4)
    elif isinstance(v, int):
        if v >= 0:
            _head(0, v, out)
        else:
            _head(1, -1 - v, out)
    elif isinstance(v, (bytes, bytearray)):
        _head(2, len(v), out)
        out.extend(v)
    elif isinstance(v, str):
        b = v.encode("utf-8")
        _head(3, len(b), out)
        out.extend(b)
    elif isinstance(v, (list, tuple)):
        _head(4, len(v), out)
        for x in v:
            _enc(x, out)
    elif isinstance(v, dict):
        _head(5, len(v), out)
        for k in v:
            _enc(k, out)
            _enc(v[k], out)
    elif isinstance(v, float):
        out.append(0xfb)
        out.extend(struct.pack(">d", v))
    else:
        raise TypeError("can't encode %s" % type(v))


def dumps(v):
    out = bytearray()
    _enc(v, out)
    return bytes(out)


MAX_DEPTH = 8
MAX_ITEMS = 256


def _n(data, i, info):
    if info < 24:
        return info, i
    if info == 24:
        return data[i], i + 1
    if info == 25:
        return struct.unpack(">H", data[i:i + 2])[0], i + 2
    if info == 26:
        return struct.unpack(">I", data[i:i + 4])[0], i + 4
    if info == 27:
        return struct.unpack(">Q", data[i:i + 8])[0], i + 8
    raise ValueError("bad length")


def _dec(data, i, depth):
    if depth > MAX_DEPTH:
        raise ValueError("too deep")
    ib = data[i]
    i += 1
    major, info = ib >> 5, ib & 31
    if major == 7:
        if info == 20:
            return False, i
        if info == 21:
            return True, i
        if info in (22, 23):
            return None, i
        if info == 25:
            h = struct.unpack(">H", data[i:i + 2])[0]
            e, m = (h >> 10) & 31, h & 1023
            v = (m / 1024.0) * 2 ** -14 if e == 0 else (1 + m / 1024.0) * 2 ** (e - 15)
            return (-v if h & 0x8000 else v), i + 2
        if info == 26:
            return struct.unpack(">f", data[i:i + 4])[0], i + 4
        if info == 27:
            return struct.unpack(">d", data[i:i + 8])[0], i + 8
        raise ValueError("bad simple value")
    n, i = _n(data, i, info)
    if major == 0:
        return n, i
    if major == 1:
        return -1 - n, i
    if major in (2, 3):
        if i + n > len(data):
            raise ValueError("short")
        b = bytes(data[i:i + n])
        return (b if major == 2 else b.decode("utf-8")), i + n
    if major == 4:
        if n > MAX_ITEMS:
            raise ValueError("too many")
        out = []
        for _ in range(n):
            v, i = _dec(data, i, depth + 1)
            out.append(v)
        return out, i
    if major == 5:
        if n > MAX_ITEMS:
            raise ValueError("too many")
        out = {}
        for _ in range(n):
            k, i = _dec(data, i, depth + 1)
            v, i = _dec(data, i, depth + 1)
            if isinstance(k, (list, dict)):
                raise ValueError("bad key")
            out[k] = v
        return out, i
    if major == 6:
        return _dec(data, i, depth + 1)        # a tag: the value it tags
    raise ValueError("bad item")


def loads(data):
    v, i = _dec(bytes(data), 0, 0)
    return v
