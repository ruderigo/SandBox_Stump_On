#!/usr/bin/env python3
"""Runs the Stump test suite.

    python3 tests/run.py                 # everything
    python3 tests/run.py plugin_api      # one test
    MICROPYTHON=/path/to/micropython python3 tests/run.py

The firmware tests run under the MicroPython Unix port built with
single-precision floats, like the ESP32-S3 (see tests/README.md), each in
a fresh copy of final_firmware/ (plus the plugins it needs), so nothing
writes into the source tree. Two kinds:

  assert    the script checks itself and ends with "FAILURES: []"
  snapshot  the output, normalised (random nonces, signatures, clock
            values, log lines), must match tests/expected/<name>.txt.
            --update rewrites those files: review the diff before
            committing it.
"""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FW = ROOT / "final_firmware"
PACKS = ROOT / "packs"
MP = os.environ.get("MICROPYTHON", "micropython")
TEST_PLUGINS = [HERE / "plugins" / n for n in ("dice", "crashy", "future")]
PACK_PLUGINS = [PACKS / "tavern-pack" / "tavern", PACKS / "rnfs-pack" / "rnfs"]

# name, kind, extra plugin folders
TESTS = [
    ("chat_golden", "snapshot", []),
    ("access_golden", "snapshot", []),
    ("mesh_golden", "snapshot", []),
    ("plugin_api", "assert", TEST_PLUGINS),
    ("plugin_web", "assert", TEST_PLUGINS),
    ("safe_mode", "safe", TEST_PLUGINS),
    ("fservbot_storage", "snapshot", []),
    ("packs_chat", "assert", PACK_PLUGINS),
    ("packs_web", "snapshot", PACK_PLUGINS),
    ("relay_fastpath", "assert", []),
    ("json_api", "snapshot", []),
    ("latin1_names", "snapshot", []),
]

_NORM = [
    (re.compile(r"AUTH-CHALLENGE [0-9a-f]{32}"), "AUTH-CHALLENGE <nonce>"),
    (re.compile(r"(/auth [0-9a-f]{128}) [0-9a-f]{128}"), r"\1 <sig>"),
    (re.compile(r"\b1[6-9]\d{8}(\.\d+)?\b"), "<time>"),
    (re.compile(r"/tmp/[^\s'\"]*?(/_sd\w*)"), r"<tmp>\1"),
    (re.compile(r"guest-[0-9a-f]{4}"), "guest-xxxx"),
]


def normalise(text, workdir):
    out = []
    for line in text.replace(str(workdir), "<work>").splitlines():
        if re.match(r"^\[\d+\]\[(WARN|INFO|DEBUG)\]", line):
            continue
        for rx, rep in _NORM:
            line = rx.sub(rep, line)
        out.append(line.rstrip())
    return "\n".join(out).strip() + "\n"


def tree(extra):
    d = Path(tempfile.mkdtemp(prefix="stump-test-"))
    shutil.copytree(FW, d / "fw", ignore=shutil.ignore_patterns("__pycache__", "third_party", "tools_payload"))
    for p in extra:
        shutil.copytree(p, d / "fw" / p.name, ignore=shutil.ignore_patterns("__pycache__"))
    # A fixed config, not the repository's (which is a real node's): the
    # snapshots must not change because someone renamed their bot.
    shutil.copy(HERE / "config.py", d / "fw" / "config.py")
    return d / "fw"


def run_mp(script, cwd, *args):
    r = subprocess.run([MP, str(HERE / "mp" / script)] + [str(HERE / "mp")] + list(args),
                       cwd=cwd, capture_output=True, text=True, timeout=600)
    return r.stdout + r.stderr


def main():
    update = "--update" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    failed = []
    for name, kind, extra in TESTS:
        if only and name not in only:
            continue
        cwd = tree(extra)
        try:
            if kind == "safe":
                seq = ["reset", "culprit", "normal", "reset", "running", "normal"]
                out = "".join("== %s\n" % m + "\n".join(l for l in run_mp(name + ".py", cwd, m).splitlines()
                                                       if l.startswith(("RUNNING", "SAFE ", "OFF", "MARKER", "[plugin] SAFE")))
                              + "\n" for m in seq)
                kind = "snapshot"
            else:
                out = run_mp(name + ".py", cwd)
            if kind == "assert":
                ok = re.search(r"^FAILURES:? \[\]$", out, re.M) is not None and "Traceback" not in out
                detail = "\n".join(l for l in out.splitlines() if l.startswith("FAIL") or "Error" in l)[:2000]
            else:
                got = normalise(out, cwd)
                exp_file = HERE / "expected" / (name + ".txt")
                if update:
                    exp_file.write_text(got)
                want = exp_file.read_text() if exp_file.exists() else ""
                ok = got == want
                if not ok:
                    import difflib
                    detail = "".join(difflib.unified_diff(want.splitlines(True), got.splitlines(True),
                                                          "expected", "got", n=1))[:3000]
            print(("ok    " if ok else "FAIL  ") + name)
            if not ok:
                print(detail)
                failed.append(name)
        finally:
            shutil.rmtree(cwd.parent, ignore_errors=True)
    if not only or "provisioner" in only:
        r = subprocess.run([sys.executable, str(HERE / "provisioner_test.py")], capture_output=True, text=True)
        ok = "FAILURES []" in r.stdout
        print(("ok    " if ok else "FAIL  ") + "provisioner")
        if not ok:
            print((r.stdout + r.stderr)[-3000:])
            failed.append("provisioner")
    print("\n%d failed: %s" % (len(failed), ", ".join(failed)) if failed else "\nall passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
