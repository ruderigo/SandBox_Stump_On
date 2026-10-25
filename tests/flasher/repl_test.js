// The flasher's board side (scripts/flasher/repl.js) against a pretend board
// (board_sim.py: the REPL protocol, the code run by MicroPython's Unix port).
//   node repl_test.js <micropython> <scratch dir>
"use strict";
const { spawn } = require("child_process");
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const R = require(path.join(__dirname, "../../scripts/flasher/repl.js"));
const MP = process.argv[2], SCRATCH = process.argv[3], TEMPLATE = process.argv[4], FW = process.argv[5];
const FAIL = [];
function check(name, ok, info) {
  console.log((ok ? "PASS " : "FAIL ") + name + (ok ? "" : "  " + String(info === undefined ? "" : info).slice(0, 400)));
  if (!ok) FAIL.push(name);
}
const sha = (b) => crypto.createHash("sha256").update(b).digest("hex");

function board(root, extra) {
  fs.mkdirSync(root, { recursive: true });
  const p = spawn("python3", [path.join(__dirname, "board_sim.py"), "--root", root, "--micropython", MP].concat(extra || []),
                  { stdio: ["pipe", "pipe", "inherit"] });
  const repl = new R.Repl((u8) => new Promise((ok) => p.stdin.write(Buffer.from(u8), ok)));
  p.stdout.on("data", (d) => repl.feed(new Uint8Array(d)));
  p.on("exit", () => repl.closed(new Error("the board went away")));
  repl.stop = () => p.kill();
  return repl;
}

function someFiles() {
  const big = crypto.randomBytes(20000);                       // several chunks, and bytes of every value
  const files = [
    { path: "main.py", data: Buffer.from("print('hello from main')\n") },
    { path: "rrc.mpy", data: crypto.randomBytes(5000) },
    { path: "urns/crypto/pure25519/basic.mpy", data: big },
    { path: "urns/__init__.py", data: Buffer.from("") },
    { path: "web/opus.wasm", data: crypto.randomBytes(7001) },
  ];
  return files.map((f) => ({ path: f.path, data: new Uint8Array(f.data), sha256: sha(f.data) }));
}

async function scenario(name, extra, chunk) {
  const root = path.join(SCRATCH, name);
  fs.rmSync(root, { recursive: true, force: true });
  fs.mkdirSync(root, { recursive: true });
  fs.writeFileSync(path.join(root, "rrc.py"), "old source\n");             // shadowed by rrc.mpy: must go
  fs.mkdirSync(path.join(root, "urns"));
  fs.writeFileSync(path.join(root, "urns/__init__.mpy"), "stale");          // shadows the new __init__.py: must go
  fs.writeFileSync(path.join(root, "main.py"), "old main\n");
  const repl = board(root, extra);
  try {
    await R.prepare(repl, 8000);
    check(name + ": raw REPL entered" + (extra && extra.includes("--running") ? " (a running Stump stopped first)" : ""), true);
    const info = await R.boardInfo(repl);
    check(name + ": the board's MicroPython and .mpy version", /^\d+\.\d+\.\d+$/.test(info.release) && info.mpy === "6.3", JSON.stringify(info));
    const files = someFiles(), seen = [];
    await R.upload(repl, files, (d, t, p) => seen.push([d, t]), chunk);
    check(name + ": raw-paste " + (extra && extra.includes("--no-paste") ? "refused, plain raw used" : "used"),
          repl.rawPaste === !(extra && extra.includes("--no-paste")), repl.rawPaste);
    const same = files.every((f) => {
      const p = path.join(root, f.path);
      return fs.existsSync(p) && sha(fs.readFileSync(p)) === f.sha256;
    });
    check(name + ": every file arrived, byte for byte (folders made)", same);
    const left = [];
    (function walk(d) { for (const n of fs.readdirSync(d)) { const p = path.join(d, n); fs.statSync(p).isDirectory() ? walk(p) : left.push(path.relative(root, p)); } })(root);
    check(name + ": no .part left", !left.some((p) => p.endsWith(".part")), left);
    check(name + ": the .py a .mpy replaces is gone, and the .mpy a .py replaces",
          !fs.existsSync(path.join(root, "rrc.py")) && !fs.existsSync(path.join(root, "urns/__init__.mpy")), left);
    const total = files.reduce((a, f) => a + f.data.length, 0);
    check(name + ": progress goes up to the total", seen.length > 5 && seen[seen.length - 1][0] === total
          && seen.every((s, i) => !i || s[0] >= seen[i - 1][0]), JSON.stringify(seen.slice(-3)));
    // A file damaged on the way: refused, and the old one stays.
    fs.writeFileSync(path.join(root, "keep.py"), "the old one\n");
    let err = null;
    try { await R.upload(repl, [{ path: "keep.py", data: new Uint8Array(Buffer.from("new\n")), sha256: "0".repeat(64) }]); }
    catch (e) { err = e; }
    check(name + ": a file that arrives damaged: an error, the old file kept, no .part",
          err && /arrived damaged/.test(err.message) && fs.readFileSync(path.join(root, "keep.py"), "utf8") === "the old one\n"
          && !fs.existsSync(path.join(root, "keep.py.part")), err && err.message);
    const out = await repl.exec("print(1+1)\nraise ValueError('nope')\n");
    check(name + ": output and traceback come back apart", out.out.trim() === "2" && /ValueError: nope/.test(out.err), JSON.stringify(out));
    check(name + ": ... and the REPL still works after it", (await repl.run("print('again')")).trim() === "again");
  } catch (e) {
    check(name + ": ran through", false, e.stack + (e.tail ? "\n tail: " + JSON.stringify(e.tail) : ""));
  } finally { repl.stop(); }
}

(async () => {
  await scenario("paste", []);
  await scenario("paste_small_window", ["--window", "32"], 1024);
  await scenario("plain", ["--no-paste"]);
  await scenario("running", ["--running"]);

  // The board going away (cable out) mid-way: an error, not a hang.
  const root = path.join(SCRATCH, "gone");
  const repl = board(root);
  await repl.enterRaw(8000);
  let err = null, t0 = 0;
  try { await R.upload(repl, someFiles(), (d) => { if (d && !t0) { t0 = Date.now(); repl.stop(); } }); } catch (e) { err = e; }
  check("cable pulled mid-upload: says so at once", err && /went away/.test(err.message) && Date.now() - t0 < 5000, err && err.message);

  // -- the form's answers -> settings (the rules of /admin and the Provisioner) --
  const base = { name: "Café du Coin", bot: "BarKeep", greeting: "", pw: "s3cret", pw2: "s3cret", ssid: "", wpass: "",
                 radio: "none", features: ["chat", "files"], theme: "paper", mode: "open", hotspot: "", chain: "none" };
  const S = (o) => R.settingsFrom(Object.assign({}, base, o));
  let r = S({});
  check("settings: a plain new Stump", !r.error && r.values.NODE_NAME === "Café du Coin" && r.values.AUTH_ADMIN_PASSWORD === "s3cret"
        && r.values.FSERVBOT_OP_PASSWORD === "s3cret" && r.values.CHAIN_ENABLED === false && r.values.HELTEC.enabled === false
        && r.values.SSID_NAME === null, JSON.stringify(r));
  const errs = [
    [{ name: "" }, /name/], [{ name: "x".repeat(21) }, /name/], [{ pw: "abc", pw2: "abc" }, /password/], [{ pw2: "other" }, /aren't the same/],
    [{ wpass: "longenough" }, /no Wi-Fi name/], [{ ssid: "Home", wpass: "short" }, /8 to 63/],
    [{ radio: "lan", hhost: "300.1.1.1", ssid: "Home" }, /address/], [{ radio: "lan", hhost: "192.168.1.50" }, /home Wi-Fi/],
    [{ chain: "first", channel: "14", secret: "s" }, /channel/], [{ chain: "member", upSsid: "", subnet: "5" }, /joins/],
    [{ chain: "member", upSsid: "LaBuche-Stump.web.app", subnet: "4" }, /5 to 254/], [{ chain: "first", channel: "6", secret: "a'b" }, /quotes/],
    [{ greeting: "x".repeat(201) }, /greeting/], [{ theme: "neon" }, /theme/],
  ];
  const bad = errs.filter(([o, re]) => !re.test(S(o).error || ""));
  check("settings: each wrong answer refused, with why (" + errs.length + ")", !bad.length, JSON.stringify(bad.map(([o]) => [o, S(o)])));
  r = S({ keepPw: true, pw: "", pw2: "" });
  check("settings: a blank password on a Stump that has one: kept (not written)", !r.error && !("AUTH_ADMIN_PASSWORD" in r.values), JSON.stringify(r));
  r = S({ keepPw: false, pw: "", pw2: "" });
  check("... on a new one: refused", /password/.test(r.error || ""));
  r = S({ chain: "member", upSsid: "LaBuche-Stump.web.app", upPass: "", subnet: "7", secret: "abc", radio: "ap" });
  check("settings: a chain member, its Heltec on its own Wi-Fi at 192.168.<its number>.2", !r.error && r.values.CHAIN_SUBNET === 7
        && r.values.CHAIN_CHANNEL === 0 && r.values.HELTEC.host === "192.168.7.2" && r.values.HELTEC.enabled, JSON.stringify(r));
  r = S({ chain: "first", channel: "6", secret: "" });
  check("settings: the first Stump, no secret: allowed, with a warning", !r.error && r.values.CHAIN_SUBNET === 4 && r.values.CHAIN_CHANNEL === 6
        && r.warn.some((w) => /secret/.test(w)), JSON.stringify(r));

  // -- on a board: written by the firmware's settings.py, read back -----------
  {
    const root = path.join(SCRATCH, "settings");
    fs.rmSync(root, { recursive: true, force: true });
    fs.mkdirSync(root, { recursive: true });
    fs.copyFileSync(TEMPLATE, path.join(root, "config.py"));
    fs.copyFileSync(path.join(FW, "settings.py"), path.join(root, "settings.py"));
    fs.copyFileSync(path.join(FW, "lora_boards.py"), path.join(root, "lora_boards.py"));
    const tplText = fs.readFileSync(TEMPLATE, "utf8");
    const repl = board(root, ["--running"]);
    try {
      await R.prepare(repl, 8000);
      const want = S({ name: "L'Atelier \"2\"", ssid: "Home Net", wpass: "pa'ss\\word", radio: "lan", hhost: "192.168.1.50",
                       features: ["chat", "about"], theme: "oled", mode: "hybrid", hotspot: "Atelier", bot: "Bob",
                       greeting: "Hi, I'm Bob", chain: "member", upSsid: "First-Stump", upPass: "upPass12", subnet: "9", secret: "s3cr3t" });
      await R.writeSettings(repl, want.values);
      const cfg = fs.readFileSync(path.join(root, "config.py"), "utf8");
      const kept = tplText.split("\n").filter((l) => l.startsWith("#") && l.length > 20);
      check("written: the file's comments and other lines kept", kept.length > 20 && kept.every((l) => cfg.includes(l)), kept.filter((l) => !cfg.includes(l)).slice(0, 3));
      check("written: the old one kept as config.py.bak", fs.readFileSync(path.join(root, "config.py.bak"), "utf8") === tplText);
      const got = await R.readSettings(repl);
      const a = R.answersFrom(got);
      check("read back: what was written", a.name === "L'Atelier \"2\"" && a.ssid === "Home Net" && a.radio === "lan" && a.hhost === "192.168.1.50"
            && a.features.join() === "chat,about" && a.theme === "oled" && a.mode === "hybrid" && a.hotspot === "Atelier" && a.bot === "Bob"
            && a.greeting === "Hi, I'm Bob" && a.chain === "member" && a.upSsid === "First-Stump" && a.upPass === "upPass12" && a.subnet === 9
            && a.secret === "s3cr3t" && a.hasPw && a.hasWifiPass, JSON.stringify(a));
      check("read: the passwords not sent to the page, only whether they're set", !("AUTH_ADMIN_PASSWORD" in got) && !("WIFI_PASS" in got)
            && !JSON.stringify(got).includes("pa'ss"), JSON.stringify(got));
      const py = (await repl.run("import config as c\nprint(repr((c.WIFI_PASS, c.AUTH_ADMIN_PASSWORD, c.FSERVBOT_OP_PASSWORD, c.CHAIN_CHANNEL, c.SSID_INCLUDE_IP)))\n")).trim();
      check("... and the passwords, as MicroPython reads them", py === "(\"pa'ss\\\\word\", 's3cret', 's3cret', 0, False)", py);
      // A Stump changed again: a blank password stays, a chain left.
      const again = R.settingsFrom(Object.assign({}, a, { keepPw: true, keepWifiPass: true, pw: "", pw2: "", wpass: "", chain: "none", radio: "ap" }));
      await R.writeSettings(repl, again.values);
      const py2 = (await repl.run("import config as c\nb=[i for i in c.CONFIG['interfaces'] if i['name']=='Heltec Bridge'][0]\n" +
                                  "print(repr((c.WIFI_PASS, c.AUTH_ADMIN_PASSWORD, c.CHAIN_ENABLED, b['target_host'], b['enabled'])))\n")).trim();
      check("changed again: blank passwords kept, out of the chain, the Heltec on its Wi-Fi", py2 === "(\"pa'ss\\\\word\", 's3cret', False, '192.168.4.2', True)", py2);
      // config.py, whole: read, put back; something that isn't Python: refused.
      const file = await R.readConfigFile(repl);
      check("its config.py read whole, byte for byte", Buffer.from(file).equals(fs.readFileSync(path.join(root, "config.py"))));
      const before = fs.readFileSync(path.join(root, "config.py"));
      let err = null;
      try { const junk = new Uint8Array(Buffer.from("NODE_NAME = 'x\n")); await R.putConfigFile(repl, junk, sha(junk)); } catch (e) { err = e; }
      check("a file put back that isn't Python: refused, the board's kept", err && /not Python/.test(err.message)
            && fs.readFileSync(path.join(root, "config.py")).equals(before), err && err.message);
      const mine = new Uint8Array(Buffer.from(tplText));
      await R.putConfigFile(repl, mine, sha(mine));
      check("a config.py put back: on it as it is, the old one as .bak", fs.readFileSync(path.join(root, "config.py"), "utf8") === tplText
            && fs.readFileSync(path.join(root, "config.py.bak")).equals(before));
      fs.writeFileSync(path.join(root, "config.py"), "NODE_NAME = 'x'\nCONFIG = {'interfaces': []}\n");
      err = null;
      try { await R.writeSettings(repl, S({}).values); } catch (e) { err = e; }
      check("a config.py with no Heltec Bridge to set: says so", err && /Heltec Bridge/.test(err.message), err && err.message);
    } catch (e) {
      check("settings on a board: ran through", false, e.stack + (e.traceback ? "\n" + e.traceback : ""));
    } finally { repl.stop(); }
  }

  const sum = R.bootSummary("ESP-ROM\r\nMicroPython v1.28.0 on 2026\r\nProject Stump -- Beta A (1.0.0-beta.38)\r\n[watchdog] armed: x\r\n" +
                            "WiFi unavailable (no AP)\r\nTraceback (most recent call last):\r\nOSError: [Errno 19] ENODEV\r\n[web] serving on 192.168.4.1:80\r\n");
  check("what it said at start, summed up", sum.release === "1.0.0-beta.38" && sum.micropython === "v1.28.0" && sum.serving
        && sum.problems.length === 2 && sum.notes.some((n) => /WiFi unavailable/.test(n)), JSON.stringify(sum));
  console.log("FAILURES: " + JSON.stringify(FAIL));
  process.exit(FAIL.length ? 1 : 0);
})();
