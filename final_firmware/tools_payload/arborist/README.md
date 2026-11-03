# Arborist

Makes a Freenove ESP32-S3-CAM into a Stump, updates one, changes its
settings and watches it start: one page, with no internet and nothing
to install.

- `Arborist-<release>.html` — save it on a computer, then open the saved
  file in Chrome or Edge (opened from this Stump's address it can't reach
  USB: browsers only allow it from a saved file or a secure page). Plug
  the CAM in by USB and follow the page.

It carries MicroPython 1.28 (MIT) and this Stump's release, and checks
every file it writes on the board. Release files and checksums:
https://github.com/ruderigo/LaBuche-Stump/releases
