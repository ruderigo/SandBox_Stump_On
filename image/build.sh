#!/bin/sh
# Builds the Stump images: MicroPython with the Stump frozen in, one per
# board (image/README.md). Needs ESP-IDF (idf.py on the PATH, as in the
# espressif/idf container) and a MicroPython checkout.
#
#   sh image/build.sh MICROPYTHON_DIR OUT_DIR [wrover|s3cam ...]
#
# -> OUT_DIR/stump-<release>-wrover.bin (flash at 0x1000)
#    OUT_DIR/stump-<release>-s3cam.bin  (flash at 0x0)
set -e
MP="$1"; OUT="$2"; shift 2
BOARDS="${*:-wrover s3cam}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
RELEASE=$(sed -n 's/^STUMP_RELEASE = "\(.*\)"/\1/p' "$ROOT/final_firmware/example_node.py")
STAGE="$ROOT/build/frozen"
python3 "$HERE/stage.py" "$STAGE"
cp "$HERE/partitions-stump.csv" "$MP/ports/esp32/"
cp -r "$HERE/boards/STUMP_WROVER" "$HERE/boards/STUMP_S3CAM" "$MP/ports/esp32/boards/"
mkdir -p "$OUT"
for b in $BOARDS; do
  case "$b" in
    wrover) BOARD=STUMP_WROVER ;;
    s3cam) BOARD=STUMP_S3CAM ;;
    *) echo "unknown board $b (wrover, s3cam)"; exit 2 ;;
  esac
  STUMP_FROZEN="$STAGE" make -C "$MP/ports/esp32" BOARD=$BOARD FROZEN_MANIFEST="$HERE/manifest.py" -j"$(nproc)"
  cp "$MP/ports/esp32/build-$BOARD/firmware.bin" "$OUT/stump-$RELEASE-$b.bin"
  echo "built $OUT/stump-$RELEASE-$b.bin"
done
cp "$STAGE/stump_image.py" "$OUT/stump_image.py"
