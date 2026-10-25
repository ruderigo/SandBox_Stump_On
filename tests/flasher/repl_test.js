// The flasher's board side (scripts/flasher/repl.js) against a pretend board
// (board_sim.py: the REPL protocol, the code run by MicroPython's Unix port).
//   node repl_test.js <micropython> <scratch dir>
"use strict";
const { spawn } = require("child_process");
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const R = require(path.join(__dirname, "../../scripts/flasher/repl.js"));
const MP = process.argv[2], SCRATCH = process.argv[3];
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

  // config.py from the template
  const tpl = "NODE_NAME = @@NODE_NAME@@\nWIFI_PASS = @@WIFI_PASS@@\nON = @@ON@@\nN = @@N@@\nF = @@F@@\n";
  const cfg = R.makeConfig(tpl, { NODE_NAME: "Café \"Le Coin\"", WIFI_PASS: "a'b\\c", ON: true, N: 7, F: ["chat", "files"] });
  check("makeConfig: Python values (quotes, accents, backslashes)", cfg.includes('NODE_NAME = "Café \\"Le Coin\\""') && cfg.includes("ON = True") && cfg.includes('F = ["chat", "files"]'), cfg);
  let missing = null;
  try { R.makeConfig(tpl, { NODE_NAME: "x" }); } catch (e) { missing = e.message; }
  check("makeConfig: an unanswered key is an error, not a silent None", /WIFI_PASS/.test(missing || ""), missing);
  console.log("FAILURES: " + JSON.stringify(FAIL));
  process.exit(FAIL.length ? 1 : 0);
})();
