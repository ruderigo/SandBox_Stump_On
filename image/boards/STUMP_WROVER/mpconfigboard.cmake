# Project Stump on a Freenove ESP32-WROVER (original ESP32, 4 MB flash,
# 4 MB PSRAM): MicroPython's ESP32_GENERIC SPIRAM variant, the Stump's
# partition table, the Stump frozen in (image/manifest.py).
set(SDKCONFIG_DEFAULTS
    boards/sdkconfig.base
    boards/sdkconfig.ble
    boards/sdkconfig.spiram
    boards/STUMP_WROVER/sdkconfig.stump
)

list(APPEND MICROPY_DEF_BOARD
    MICROPY_HW_BOARD_NAME="Project Stump on ESP32-WROVER with SPIRAM"
)
