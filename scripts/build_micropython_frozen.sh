#!/bin/sh
# Builds the MicroPython Unix port with the Stump frozen in, the way a Stump
# image has it (image/README.md), at the same commit as the test suite's
# build (scripts/build_micropython.sh): the suite then runs on a tree that
# holds only what a board running the image has on its filesystem.
#   sh scripts/build_micropython_frozen.sh [DIR]   -> DIR/micropython
#   STUMP_FROZEN=1 MICROPYTHON=DIR/micropython python3 tests/run.py
set -e
DIR="${1:-$HOME/micropython-frozen}"
COMMIT=a129b2fba1a3348088c94d0462eef16d20874dea
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGE="$ROOT/build/frozen"
python3 "$ROOT/image/stage.py" "$STAGE"
SRC="${MICROPYTHON_SRC:-$(mktemp -d)/micropython}"
if [ ! -d "$SRC/ports/unix" ]; then
  git init -q "$SRC"
  git -C "$SRC" remote add origin https://github.com/micropython/micropython
  git -C "$SRC" fetch -q --depth 1 origin "$COMMIT"
  git -C "$SRC" checkout -q FETCH_HEAD
  make -s -C "$SRC/ports/unix" submodules >/dev/null
  make -s -C "$SRC/mpy-cross" -j4 >/dev/null
fi
rm -rf "$SRC/ports/unix/build-frozen"
STUMP_FROZEN="$STAGE" make -s -C "$SRC/ports/unix" BUILD=build-frozen -j4 \
     FROZEN_MANIFEST="$ROOT/image/manifest_check.py" \
     CFLAGS_EXTRA='-DMICROPY_FLOAT_IMPL=MICROPY_FLOAT_IMPL_FLOAT' >/dev/null
mkdir -p "$DIR"
cp "$SRC/ports/unix/build-frozen/micropython" "$DIR/micropython"
echo "$DIR/micropython"
