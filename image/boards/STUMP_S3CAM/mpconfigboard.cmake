# Project Stump on a Freenove ESP32-S3-WROOM CAM (ESP32-S3, Octal PSRAM,
# 8 MB flash): MicroPython's ESP32_GENERIC_S3 SPIRAM_OCT variant, the
# Stump's partition table, the Stump frozen in (image/manifest.py).
set(IDF_TARGET esp32s3)

set(SDKCONFIG_DEFAULTS
    boards/sdkconfig.base
    boards/sdkconfig.ble
    boards/sdkconfig.spiram_sx
    boards/sdkconfig.240mhz
    boards/sdkconfig.spiram_oct
    boards/STUMP_S3CAM/sdkconfig.board
    boards/STUMP_S3CAM/sdkconfig.stump
)

list(APPEND MICROPY_DEF_BOARD
    MICROPY_HW_BOARD_NAME="Project Stump on ESP32S3 with Octal-SPIRAM"
)
