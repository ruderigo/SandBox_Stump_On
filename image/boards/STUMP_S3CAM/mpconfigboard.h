// Project Stump on a Freenove ESP32-S3-WROOM CAM. The board name keeps
// "ESP32S3": the Stump and the Provisioner tell the two boards apart by
// that (fserv.sd_pins, board_is_wrover).
#ifndef MICROPY_HW_BOARD_NAME
#define MICROPY_HW_BOARD_NAME               "Project Stump on ESP32S3 with Octal-SPIRAM"
#endif
#define MICROPY_HW_MCU_NAME                 "ESP32S3"

// Enable UART REPL for modules that have an external USB-UART and don't use native USB.
#define MICROPY_HW_ENABLE_UART_REPL         (1)

#define MICROPY_HW_I2C0_SCL                 (9)
#define MICROPY_HW_I2C0_SDA                 (8)
