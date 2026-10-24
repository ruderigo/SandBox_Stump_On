# Hidden Features

Features that are **fully present and working in the code**, but have been
deliberately unlinked from the visible UI because they're confusing,
incomplete, or not the currently-supported path -- without deleting the
underlying code, since removing it outright would be a bigger decision than
"stop showing it for now."

Each entry has a stable ID for referencing directly when these get turned
into real JIRA epics. Nothing here has been fixed or removed at the code
level -- this is a map of what's there and why it's hidden, not a changelog
of work done.

---

## HF-001 — Browser-based WebSerial flasher — **to bring back (roadmap, step 4)**

Decided in October 2026: bring it back (option (a) below), as an
enhancement after the hardening work: see `docs/ROADMAP.md` in the
repository. Until then `/flash` still works by URL, and `flasher_ui` is
loaded only when it's opened, not at every boot.

**Hidden from**: the `/tools` page (previously a prominent "Open the
flasher →" button; later replaced with plain CLI provisioning steps
shown directly on the page, and since then removed from `/tools`
entirely — those steps now live only in `README.md`, which
`install_tools_on_node()` pushes to the node's own `/sd/tools/`
alongside the other technician tools).

**Still fully functional at**: `GET /flash` (renders `flasher_ui.py`'s
page) and `GET /fw?f=<name>` (serves staged firmware images/catalog from
`tools_payload/` for it). Neither route was removed or disabled --
anyone who already has the URL, or types it directly, still gets the
working flasher.

**What it is**: an in-browser ESP32 flashing tool using the WebSerial
API (Chrome/Edge desktop only), so a technician could flash a board
without installing `esptool`/`provisioner.py` locally.

**Why hidden**: the CLI flow (`provisioner.py`) is the actual,
supported, tested provisioning path for every board role this project
has (CAM, Heltec RNode bridge, standalone Heltec transport). The
in-browser flasher duplicates part of that without the same testing
history. The provisioning steps themselves used to be duplicated too
— once shown directly on `/tools`, separately from the README's own
copy — which was confusing on its own; that duplication is gone now
that `/tools` shows downloads only and the README is one of the things
downloaded, but the flasher itself remains a second, untested path to
the same goal regardless.

**Decision an epic would need to make**: either (a) invest in it —
re-link it from `/tools`, confirm its firmware catalog
(`tools_payload/flasher/catalog.json`) is kept current alongside
`provisioner.py`'s own firmware URLs, and give it equal testing
priority, or (b) remove it formally — delete `flasher_ui.py`,
`tools_payload/` in full, the `/flash` and `/fw` route handlers, and
the `_DESTINATIONS["flash"]` nav entry and `_ICON_FLASH` (the
`tools_open_flasher`/`tools_flash_header`/`tools_flash_intro` i18n
keys this entry originally flagged for cleanup here are already gone
— removed along with the CLI-instructions section when `/tools` was
later cut down to downloads only), and stop `provisioner.py`'s
`install_tools_on_node()` from pushing `esptool-bundle.js` /
`catalog.json` / firmware images to `/sd/tools` and `/sd/fw`.

**Code locations**:
- `barkeep.py` — `import flasher_ui`, `_DESTINATIONS["flash"]`,
  `_ICON_FLASH`, the `/flash` and `/fw` `elif` branches in the request
  router
- `flasher_ui.py` — the whole file
- `tools_payload/` — the whole folder (`flasher/esptool-bundle.js`,
  `flasher/catalog.json`, `flasher/esptool-js-LICENSE.txt`,
  `images/README.txt`). That last file now also carries a real GPL-3.0
  §6 warning about what staging a firmware binary there would require
  (see the "File storage" / `/sd/tools` section of the main README) --
  worth preserving or relocating that specific warning even if the
  rest of this folder goes away under option (b), since the licensing
  concern it describes doesn't disappear just because this feature
  does.
- `fserv.py` — `FW_DIR`, `list_fw()` (used only by the `/fw` route)
- `provisioner.py` — `install_tools_on_node()`'s `tools_payload`-pushing
  block, and the `":/sd/fw"` mkdir in the same function
- `i18n.py` — `nav_flash` (defined in `_DESTINATIONS` but never
  actually passed to `_nav()` anywhere, so it was already dead before
  this; `tools_open_flasher`/`tools_flash_header`/`tools_flash_intro`
  are gone already, not just unreferenced -- see the note above)
- `README.md` / `docs/COMMANDS.md` — HTTP API tables still list
  `/flash` and `/fw?f=` as real, working routes, which remains accurate
  either way this resolves

---

## HF-002 — Awaiting-slot upload hash field — **removed (1.0.0-beta.35)**

Removed in the cleanup of October 2026: nothing could ever open a slot
(`fserv.mark_awaiting()` had no caller), so the hidden field, the
`X-Hash` header, the slot branch of `/upload`, `AWAITING_FILE` and the
`home_awaiting_hash` key went. `/upload`'s JSON answer still carries
`"slot": false`, so older clients reading it don't break. If regulated
uploads come back, they start from a design with the producer side
first.

---

## HF-003 — The Concierge (BarKeep) chat box — **brought back (October 2026)**

No longer hidden: BarKeep is the node's **librarian** now. Visitors ask
it what's on the node in French, English or Spanish, from the firefly
in the corner of the Files, Billboard and home pages (and `/concierge`,
still there); `POST /chat` answers, and `!find` asks it from the chat.
It was hidden because visitors took the box for the people's chat room;
it now lives where people look for things, labelled with what it does,
and not on the home page. See *BarKeep, the librarian* in the README
and Part 4 of `COMMANDS.md`.

---

## Adding a new entry

Same shape each time: what it is, where it's hidden from, what still
actually works underneath, why it was hidden (cite the specific code
finding, not just an impression), the decision a real epic would need
to make, and every code location touched by that decision either way.
Next ID is **HF-004**.
