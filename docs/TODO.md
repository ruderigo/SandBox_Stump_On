# To do

The plan, in order: [ROADMAP.md](ROADMAP.md). Things noted for later, newest first. Each with what was seen and what
we think the fix is.

## A computer Stump stopping: a traceback now and then

**Seen** (pc_three_stumps, 24 Oct, 1 run in 3): stopping Alpha
(SIGTERM) printed a traceback out of `asyncio.run` in example_node.py's
`main`, through asyncio's `_cancel_all_tasks`: an exception other than
the KeyboardInterrupt the stop handler raises, while the tasks were being
cancelled. Not reproduced on its own (6 starts and stops). The test now
shows the end of a traceback, so the next one names the exception.

**Likely fix**: once a stop was asked for, treat whatever comes out of
the shutdown as the stop (stump_pc.py knows a stop is under way).

## Provisioner: uploads to a CAM restart the board now and then

**Seen** (LaBuche, 20-21 Oct, beta.30-34): during `--upload-app`, a file
fails with `could not complete raw paste: b"ESP-ROM:esp32s3..."` -- the
board restarted mid-copy. It happens most during the slow Tools copy to
the SD card (`provisioner.py (296 KB) ... FAILED`), sometimes during the
app files (the verify step then resends them). The board's own log says
`[watchdog] last reset: power on / USB (code 1)`: not the watchdog, not a
crash.

**Likely cause**: the CAM's USB-serial chip ("USB Single Serial") wires its
control lines to the ESP32's reset. The Provisioner opens and closes the
port once per file (one `mpremote` run each), and now and then, on macOS,
opening it pulses those lines and restarts the board. A cable or USB port
dropping power briefly looks the same.

**Workaround for now**: copy the Tools files straight onto the SD card
(card reader), or re-run `--upload-app` (files already there are skipped).

**Fix to make**:
- send many files per `mpremote` run (its `+` chaining), so the port opens
  a handful of times instead of once per file -- fewer resets, and faster;
- after a failed file, wait for the board to finish starting, then resend
  it (today only the app files are resent, by the verify step; the Tools
  copy just reports FAILED);
- consider opening the port with the reset lines held steady (pyserial
  `dtr`/`rts` set before `open()`), if mpremote can be made to.

## /admin: who's who, with identities

A page for an admin, `/admin/people.json`: everyone a Stump lists, with
where it knows them from (browser, app, LoRa, another Stump), their
identity, and whether a Wi-Fi visitor and a LoRa identity are linked. To
check a duplicate name without reading code.
