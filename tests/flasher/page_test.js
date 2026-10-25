// The built flasher page, opened from file:// in Chromium, Web Serial
// replaced by a pipe to the pretend board (board_sim.py), and esptool-js by
// a stand-in (the flashing itself is esptool-js's, tested upstream): a new
// Stump made, and one updated, end to end.
//   node page_test.js <flasher.html> <micropython> <scratch dir>
"use strict";
const { chromium } = require("playwright");
const { spawn, execFileSync } = require("child_process");
const fs = require("fs"), path = require("path");
const [PAGE, MP, SCRATCH] = process.argv.slice(2);
const FAIL = [];
function check(name, ok, info) {
  console.log((ok ? "PASS " : "FAIL ") + name + (ok ? "" : "  " + String(info === undefined ? "" : info).slice(0, 600)));
  if (!ok) FAIL.push(name);
}

// In the page, before its own scripts: a navigator.serial whose one port is the pipe.
const FAKE_SERIAL = `
(() => {
  const listeners = [];
  window.__simFeed = (b64) => { const s = atob(b64), u = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) u[i] = s.charCodeAt(i); listeners.forEach((f) => f(u)); };
  class FakePort {
    constructor() { this.readable = null; this.writable = null; this.opens = 0; }
    getInfo() { return { usbVendorId: 0x1a86, usbProductId: 0x55d3 }; }
    async open(o) {
      if (this.readable) throw new Error("The port is already open.");
      this.opens++; window.__opens = this.opens; window.__baud = o.baudRate;
      let ctl;
      this.readable = new ReadableStream({ start(c) { ctl = c; } });
      const feed = (u) => { try { ctl.enqueue(u); } catch (e) {} };
      listeners.push(feed);
      this._feed = feed;
      this.writable = new WritableStream({ write: (u) => window.__simWrite(btoa(String.fromCharCode.apply(null, u))) });
    }
    async setSignals() {}
    async close() { listeners.splice(listeners.indexOf(this._feed), 1); this.readable = this.writable = null; }
  }
  const port = new FakePort();
  Object.defineProperty(navigator, "serial", { value: { requestPort: async () => port, getPorts: async () => [port] } });
  // esptool-js stand-in: says what it was asked to write.
  window.__flashed = null;
  const fake = {
    Transport: class { constructor(p) { this.p = p; } async disconnect() {} },
    ESPLoader: class {
      constructor(o) { this.o = o; }
      async main() { this.o.terminal.writeLine("Chip is ESP32-S3 (QFN56)"); return "ESP32-S3 (QFN56) (revision v0.2)"; }
      async writeFlash(a) { window.__flashed = { n: a.fileArray.length, len: a.fileArray[0].data.length, addr: a.fileArray[0].address, erase: a.eraseAll };
                            for (let i = 0; i <= 4; i++) a.reportProgress(0, i * 25, 100); }
      async after(m) { window.__after = m; }
    }
  };
  Object.defineProperty(window, "esptool", { get: () => fake, set: () => {} });
})();`;

async function run(name, root, simArgs, fill) {
  fs.rmSync(root, { recursive: true, force: true });
  fs.mkdirSync(root, { recursive: true });
  if (fill) fill(root);
  const sim = spawn("python3", [path.join(__dirname, "board_sim.py"), "--root", root, "--micropython", MP].concat(simArgs),
                    { stdio: ["pipe", "pipe", "inherit"] });
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("dialog", (d) => d.accept());
  await page.exposeFunction("__simWrite", (b64) => new Promise((ok) => sim.stdin.write(Buffer.from(b64, "base64"), ok)));
  sim.stdout.on("data", (d) => page.evaluate((b) => window.__simFeed(b), d.toString("base64")).catch(() => {}));
  await page.addInitScript(FAKE_SERIAL);
  await page.goto("file://" + path.resolve(PAGE));
  return { page, browser, sim, errors };
}

(async () => {
  // -- the page itself, no board -------------------------------------------------
  {
    const browser = await chromium.launch();
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto("file://" + path.resolve(PAGE));
    check("opened from file://: the form, not the gate (Chromium has Web Serial)", await page.isVisible("#form") && !(await page.isVisible("#gate")));
    check("no errors on load", errors.length === 0, errors.join("\n"));
    await page.click("#go");
    check("an empty password: the form says so", /password/i.test(await page.textContent("#formerr")) || await page.evaluate(() => !document.getElementById("pw").checkValidity()));
    await page.fill("#pw", "secret1"); await page.fill("#pw2", "secret2");
    await page.click("#go");
    check("two passwords that differ: says so", /aren't the same/.test(await page.textContent("#formerr")), await page.textContent("#formerr"));
    await page.fill("#pw2", "secret1");
    await page.check("input[name=radio][value=lan]");
    await page.fill("#hhost", "not an address");
    await page.click("#go");
    check("a Heltec address that isn't one: says so", /192\.168/.test(await page.textContent("#formerr")), await page.textContent("#formerr"));
    const ver = await page.textContent(".sub");
    check("the page names its release", /Stump 1\.0\.0-\S+/.test(ver), ver);
    await browser.close();
  }

  // -- a new Stump --------------------------------------------------------------------
  {
    const root = path.join(SCRATCH, "page_new");
    const t = await run("new", root, []);
    const { page } = t;
    await page.fill("#name", "Café du Coin");
    await page.fill("#pw", "s3cret!"); await page.fill("#pw2", "s3cret!");
    await page.fill("#ssid", "Home \"Net\""); await page.fill("#wpass", "pa'ss");
    await page.check("input[name=radio][value=ap]");
    await page.click("#go");
    try { await page.waitForSelector("#worktitle .ok, #worktitle .err", { timeout: 240000 }); } catch (e) {}
    const title = await page.textContent("#worktitle"), result = await page.textContent("#result");
    check("a new Stump: done", /Done/.test(title), title + " | " + result + " | " + (await page.textContent("#log")).slice(-800));
    const fl = await page.evaluate(() => window.__flashed);
    check("... MicroPython written at 0, the board erased first, then reset", fl && fl.addr === 0 && fl.erase && fl.len > 500000
          && (await page.evaluate(() => window.__after)) === "hard_reset", JSON.stringify(fl));
    check("... then the REPL at 115200", (await page.evaluate(() => window.__baud)) === 115200);
    check("... the Stump's files on the board, compiled", fs.existsSync(path.join(root, "barkeep.mpy")) && fs.existsSync(path.join(root, "main.py"))
          && fs.existsSync(path.join(root, "urns")) && !fs.existsSync(path.join(root, "barkeep.py")));
    check("... the plugins too (their plugin.json stays on the computer, as with the Provisioner)", fs.existsSync(path.join(root, "stumpid/core.mpy")) && !fs.existsSync(path.join(root, "stumpid/plugin.json")) && fs.existsSync(path.join(root, "fservbot/core.mpy")));
    const cfgPath = path.join(root, "config.py");
    check("... and a config.py", fs.existsSync(cfgPath));
    if (fs.existsSync(cfgPath)) {
      const cfg = fs.readFileSync(cfgPath, "utf8");
      fs.writeFileSync(path.join(root, "lora_boards.py"), "LORA_BOARDS = {}\n");
      const out = execFileSync(MP, ["-c", "import config as c\nb=[i for i in c.CONFIG['interfaces'] if i['name']=='Heltec Bridge'][0]\n" +
        "print(repr((c.NODE_NAME, c.AUTH_ADMIN_PASSWORD, c.FSERVBOT_OP_PASSWORD, c.WIFI_SSID, c.WIFI_PASS, b['enabled'], b['target_host'], b['target_port'], c.CHAIN_ENABLED, c.CHAIN_SECRET, c.BOT_NAME)))"],
        { cwd: root }).toString().trim();
      check("... with the answers, as MicroPython reads them", out === "('Café du Coin', 's3cret!', 's3cret!', 'Home \"Net\"', \"pa'ss\", True, '192.168.4.2', 7633, False, '', 'BarKeep')", out);
      check("... nothing of LaBuche's own config.py", !/LaBuche'|TeK|SalutComment|Bob's Glitch|Concierge/.test(cfg));
    }
    check("... no errors in the page", t.errors.length === 0, t.errors.join("\n"));
    await t.browser.close(); t.sim.kill();
  }

  // -- updating a Stump -----------------------------------------------------------------
  {
    const root = path.join(SCRATCH, "page_update");
    const t = await run("update", root, ["--running"], (r) => {
      fs.writeFileSync(path.join(r, "config.py"), "NODE_NAME = 'Mine'\n");
      fs.mkdirSync(path.join(r, "rns")); fs.writeFileSync(path.join(r, "rns/identity"), "its identity");
      fs.writeFileSync(path.join(r, "barkeep.py"), "old");
    });
    const { page } = t;
    await page.check("input[name=mode][value=update]");
    check("update: the settings fields go away", !(await page.isVisible("#newfields")) && /Update/.test(await page.textContent("#go")));
    await page.click("#go");
    try { await page.waitForSelector("#worktitle .ok, #worktitle .err", { timeout: 240000 }); } catch (e) {}
    const title = await page.textContent("#worktitle");
    check("update: done (the running Stump stopped first)", /Done/.test(title), title + " | " + (await page.textContent("#result")) + " | " + (await page.textContent("#log")).slice(-600));
    check("... nothing flashed", (await page.evaluate(() => window.__flashed)) === null);
    check("... its config.py and identity kept", fs.readFileSync(path.join(root, "config.py"), "utf8") === "NODE_NAME = 'Mine'\n"
          && fs.readFileSync(path.join(root, "rns/identity"), "utf8") === "its identity");
    check("... the new files there, the old source gone", fs.existsSync(path.join(root, "barkeep.mpy")) && !fs.existsSync(path.join(root, "barkeep.py")));
    await t.browser.close(); t.sim.kill();
  }

  // -- updating a board with no Stump: refused ---------------------------------------
  {
    const root = path.join(SCRATCH, "page_update_none");
    const t = await run("none", root, []);
    await t.page.check("input[name=mode][value=update]");
    await t.page.click("#go");
    try { await t.page.waitForSelector("#worktitle .ok, #worktitle .err", { timeout: 60000 }); } catch (e) {}
    const res = await t.page.textContent("#result");
    check("update on a board with no Stump: stopped, with why", /no Stump on this board/.test(res), res);
    check("... nothing copied", !fs.existsSync(path.join(root, "barkeep.mpy")));
    await t.browser.close(); t.sim.kill();
  }
  console.log("FAILURES: " + JSON.stringify(FAIL));
  process.exit(FAIL.length ? 1 : 0);
})().catch((e) => { console.log("FAIL crashed: " + e.stack); console.log("FAILURES: [\"crashed\"]"); process.exit(1); });
