// Project Stump on a Freenove ESP32-WROVER. The board name keeps
// "ESP32" and "SPIRAM" and not "ESP32S3": the Stump and the Provisioner
// tell the two boards apart by that (fserv.sd_pins, board_is_wrover).
#ifndef MICROPY_HW_BOARD_NAME
#define MICROPY_HW_BOARD_NAME "Project Stump on ESP32-WROVER with SPIRAM"
#endif

#ifndef MICROPY_HW_MCU_NAME
#define MICROPY_HW_MCU_NAME "ESP32"
#endif
