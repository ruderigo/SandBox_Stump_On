// Stump flasher: putting the Stump on a board that runs MicroPython, over
// its USB serial line -- the same steps as `mpremote` (what the Provisioner
// uses), in the browser. Three parts:
//
//   Repl      MicroPython's raw REPL over a byte stream: write(bytes) out,
//             feed(bytes) in. Raw-paste mode when the board has it (flow
//             control: the board says how much it can take), plain raw
//             mode otherwise.
//   upload    the app's files: folders first, each file in chunks to
//             <file>.part, its SHA-256 checked on the board, then renamed
//             over the old one -- a cut cable never leaves half a module.
//             A module that arrives compiled (.mpy) has its .py removed
//             (MicroPython would load the .py first), and the other way.
//   makeConfig  config.py from the template the build scrubbed, with the
//             answers of the setup form.
//
// No browser API here except TextEncoder/btoa/setTimeout, so the tests run
// it in Node against a simulated board (tests/flasher_test.py).
(function (root) {
  "use strict";
  var enc = new TextEncoder(), dec = new TextDecoder();
  var RAW_BANNER = "raw REPL; CTRL-B to exit\r\n>";

  function bytes(x) { return typeof x === "string" ? enc.encode(x) : x instanceof Uint8Array ? x : new Uint8Array(x); }
  function indexOf(hay, pat) {
    outer: for (var i = 0; i + pat.length <= hay.length; i++) {
      for (var j = 0; j < pat.length; j++) if (hay[i + j] !== pat[j]) continue outer;
      return i;
    }
    return -1;
  }
  function sleep(ms) { return new Promise(function (ok) { setTimeout(ok, ms); }); }
  function b64(u8) {
    var s = "";
    for (var i = 0; i < u8.length; i += 4096) s += String.fromCharCode.apply(null, u8.subarray(i, i + 4096));
    return btoa(s);
  }
  function py(s) { return JSON.stringify(String(s)); }      // a JSON string is a Python string literal

  function Repl(write, opts) {
    opts = opts || {};
    this._write = write;
    this.buf = new Uint8Array(0);
    this.waiter = null;
    this.dead = null;
    this.rawPaste = opts.rawPaste === false ? false : undefined;
    this.log = opts.log || function () {};
  }
  Repl.prototype.feed = function (u8) {
    var b = new Uint8Array(this.buf.length + u8.length);
    b.set(this.buf); b.set(u8, this.buf.length);
    this.buf = b;
    if (this.waiter) this.waiter();
  };
  Repl.prototype.closed = function (err) {
    this.dead = err || new Error("the board went away");
    if (this.waiter) this.waiter();
  };
  Repl.prototype.write = function (x) { return this._write(bytes(x)); };
  Repl.prototype.drain = function () { var b = this.buf; this.buf = new Uint8Array(0); return b; };
  Repl.prototype._wait = function (ms) {
    var self = this;
    return new Promise(function (ok) {
      var t = setTimeout(function () { self.waiter = null; ok(false); }, Math.max(ms, 1));
      self.waiter = function () { clearTimeout(t); self.waiter = null; ok(true); };
    });
  };
  // Everything up to and including `pat`; what follows stays for the next read.
  Repl.prototype.readUntil = async function (pat, ms) {
    pat = bytes(pat);
    var until = Date.now() + (ms || 5000);
    for (;;) {
      var i = indexOf(this.buf, pat);
      if (i >= 0) {
        var out = this.buf.slice(0, i + pat.length);
        this.buf = this.buf.slice(i + pat.length);
        return out;
      }
      if (this.dead) throw this.dead;
      var left = until - Date.now();
      if (left <= 0) {
        var e = new Error("the board didn't answer (waited for " + JSON.stringify(dec.decode(pat)) + ")");
        e.tail = dec.decode(this.buf.slice(-300));
        throw e;
      }
      await this._wait(left);
    }
  };
  Repl.prototype.readN = async function (n, ms) {
    var until = Date.now() + (ms || 5000);
    while (this.buf.length < n) {
      if (this.dead) throw this.dead;
      var left = until - Date.now();
      if (left <= 0) throw new Error("the board didn't answer");
      await this._wait(left);
    }
    var out = this.buf.slice(0, n);
    this.buf = this.buf.slice(n);
    return out;
  };

  // Stop whatever runs (a Stump's main loop too) and enter the raw REPL.
  Repl.prototype.enterRaw = async function (ms) {
    for (var i = 0; i < 3; i++) { await this.write("\r\x03"); await sleep(150); }
    this.drain();
    await this.write("\r\x01");
    await this.readUntil(RAW_BANNER, ms || 5000);
  };
  // A soft reset from the raw REPL: a clean interpreter, main.py not run.
  Repl.prototype.softReset = async function (ms) {
    await this.write("\x04");
    await this.readUntil("soft reboot\r\n", ms || 10000);
    await this.readUntil(RAW_BANNER, ms || 10000);
  };
  Repl.prototype._paste = async function (data) {
    var w = await this.readN(2), win = w[0] | (w[1] << 8), remain = win, i = 0;
    while (i < data.length) {
      while (remain === 0 || this.buf.length) {
        var b = (await this.readN(1, 10000))[0];
        if (b === 1) remain += win;
        else if (b === 4) { await this.write("\x04"); throw new Error("the board stopped taking the code"); }
        else throw new Error("the board said something unexpected (" + b + ")");
      }
      var n = Math.min(remain, data.length - i);
      await this.write(data.subarray(i, i + n));
      remain -= n; i += n;
    }
    await this.write("\x04");
    await this.readUntil("\x04", 10000);
  };
  // Run code; {out, err} (err: the traceback, "" when it ran fine).
  Repl.prototype.exec = async function (code, ms) {
    var data = bytes(code), plain = this.rawPaste === false;
    if (!plain) {
      await this.write("\x05A\x01");
      var r = await this.readN(2, 3000);
      if (r[0] === 82 && r[1] === 1) { this.rawPaste = true; await this._paste(data); }
      else {
        this.rawPaste = false; plain = true;
        if (!(r[0] === 82 && r[1] === 0)) await this.readUntil("w REPL; CTRL-B to exit\r\n>", 3000);
      }
    }
    if (plain) {
      for (var i = 0; i < data.length; i += 256) { await this.write(data.subarray(i, i + 256)); await sleep(10); }
      await this.write("\x04");
      var ok = await this.readN(2, 5000);
      if (ok[0] !== 79 || ok[1] !== 75) throw new Error("the board didn't take the code");
    }
    var out = await this.readUntil("\x04", ms || 30000);
    var err = await this.readUntil("\x04", ms || 30000);
    await this.readUntil(">", 5000);
    return { out: dec.decode(out.slice(0, -1)), err: dec.decode(err.slice(0, -1)) };
  };
  // exec, and a traceback is an error.
  Repl.prototype.run = async function (code, ms) {
    var r = await this.exec(code, ms);
    if (r.err) { var e = new Error(r.err.trim().split("\n").pop()); e.traceback = r.err; throw e; }
    return r.out;
  };

  // Before anything: a running Stump stopped, its watchdog (keepalive.py)
  // given 2 hours -- it can't be switched off, and a reset mid-copy would
  // cut the upload -- and a clean interpreter (main.py not run). As the
  // Provisioner does (QUIET_WATCHDOG there).
  var QUIET_WATCHDOG = "try:\n import machine\n machine.WDT(timeout=7200000).feed()\nexcept Exception:\n pass\n";
  async function prepare(repl, ms) {
    await repl.enterRaw(ms);
    await repl.run(QUIET_WATCHDOG);
    await repl.softReset();
  }
  // Restart the board into the Stump (from the friendly REPL, so nothing waits for an answer).
  async function restart(repl) {
    await repl.write("\x02");
    await sleep(300);
    await repl.write("import machine; machine.reset()\r\n");
    await sleep(300);
  }

  // The board's MicroPython: {release: "1.28.0", mpy: "6.3"}.
  async function boardInfo(repl) {
    var out = await repl.run("import sys\nv=getattr(sys.implementation,'_mpy',0)\n" +
      "print('INFO', '.'.join(str(x) for x in sys.implementation.version[:3]), '%d.%d' % (v & 0xff, (v >> 8) & 3))\n");
    var m = /INFO (\S+) (\S+)/.exec(out) || [];
    return { release: m[1], mpy: m[2] };
  }

  // files: [{path, data: Uint8Array, sha256: hex}]. progress(done, total, path) in bytes.
  async function upload(repl, files, progress, chunk) {
    chunk = chunk || 3072;
    progress = progress || function () {};
    var dirs = {}, total = 0, done = 0;
    files.forEach(function (f) {
      total += f.data.length;
      var parts = f.path.split("/");
      for (var i = 1; i < parts.length; i++) dirs[parts.slice(0, i).join("/")] = 1;
    });
    var dl = Object.keys(dirs).sort(function (a, b) { return a.split("/").length - b.split("/").length || (a < b ? -1 : 1); });
    if (dl.length)
      await repl.run("import os\nfor d in " + JSON.stringify(dl) + ":\n try:\n  os.mkdir(d)\n except OSError:\n  pass\n");
    for (var k = 0; k < files.length; k++) {
      var f = files[k], tmp = f.path + ".part";
      progress(done, total, f.path);
      if (!f.data.length) await repl.run("open(" + py(tmp) + ",'wb').close()\n");
      for (var off = 0; off < f.data.length; off += chunk) {
        await repl.run("import binascii\nf=open(" + py(tmp) + ",'" + (off ? "ab" : "wb") + "')\n" +
                       "f.write(binascii.a2b_base64('" + b64(f.data.subarray(off, off + chunk)) + "'))\nf.close()\n");
        done += Math.min(chunk, f.data.length - off);
        progress(done, total, f.path);
      }
      await repl.run(
        "import os,hashlib,binascii\nh=hashlib.sha256()\nf=open(" + py(tmp) + ",'rb')\nwhile 1:\n b=f.read(2048)\n" +
        " if not b:\n  break\n h.update(b)\nf.close()\nd=binascii.hexlify(h.digest()).decode()\n" +
        "if d!=" + py(f.sha256) + ":\n os.remove(" + py(tmp) + ")\n raise OSError(" + py(f.path + " arrived damaged") + ")\n" +
        "try:\n os.remove(" + py(f.path) + ")\nexcept OSError:\n pass\nos.rename(" + py(tmp) + "," + py(f.path) + ")\n", 60000);
    }
    var gone = [];
    files.forEach(function (f) {
      if (/\.mpy$/.test(f.path)) gone.push(f.path.slice(0, -4) + ".py");
      else if (/\.py$/.test(f.path) && !/(^|\/)(boot|main|config)\.py$/.test(f.path)) gone.push(f.path.slice(0, -3) + ".mpy");
    });
    if (gone.length)
      await repl.run("import os\nfor p in " + JSON.stringify(gone) + ":\n try:\n  os.remove(p)\n except OSError:\n  pass\n");
    progress(total, total, "");
  }

  // config.py from the scrubbed template: each @@KEY@@ becomes the answer, as Python.
  function pyValue(v) {
    if (v === true) return "True";
    if (v === false) return "False";
    if (v === null || v === undefined) return "None";
    if (typeof v === "number") { if (!isFinite(v) || Math.floor(v) !== v) throw new Error("not a whole number: " + v); return String(v); }
    if (Array.isArray(v)) return "[" + v.map(pyValue).join(", ") + "]";
    return py(v);
  }
  function makeConfig(template, answers) {
    var missing = [];
    var out = template.replace(/@@([A-Z0-9_]+)@@/g, function (_, k) {
      if (!(k in answers)) { missing.push(k); return "None"; }
      return pyValue(answers[k]);
    });
    if (missing.length) throw new Error("no answer for " + missing.join(", "));
    return out;
  }

  var api = { Repl: Repl, prepare: prepare, restart: restart, upload: upload, boardInfo: boardInfo, makeConfig: makeConfig, pyValue: pyValue, sleep: sleep, b64: b64 };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.StumpRepl = api;
})(typeof window !== "undefined" ? window : globalThis);
