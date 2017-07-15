from strips_tester import CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET
from strips_tester.custom_tests import *

try:
    import RPi.GPIO as GPIO
except RuntimeError:
    print("Error importing RPi.GPIO!  This is probably because you need superuser privileges.  You can achieve this by using 'sudo' to run your script")

# test everything above this level. NOTSET (0) is default and covers all levels
TEST_LEVEL = NOTSET

# log everything above this level. NOTSET (0) is default and covers all levels
LOGGING_LEVEL = NOTSET

# for full functionality define at least this GPIOs:
# example : "START_SWITCH": {"channel": 666, "in/out": GPIO.IN, "initial": GPIO.LOW},  # initial is low because tester waits for rising edge to start...
#           "STATUS_LED": {"channel": 666, "in/out": GPIO.OUT, "initial": GPIO.LOW},
gpios = {"START_SWITCH": {"pin": 12, "direction": GPIO.IN, "initial": GPIO.LOW},
         "DETECT_SWITCH": {"pin": 26, "direction": GPIO.IN, "initial": GPIO.LOW},
         "WIFI_PRESET_SWITCH": {"pin": 16, "direction": GPIO.IN, "initial": GPIO.LOW},
         "DISPLAY_OK_FAIL_SWITCH": {"pin": 24, "direction": GPIO.IN, "initial": GPIO.LOW},
         "CONFIRM_GOOD_SWITCH": {"pin": 36, "direction": GPIO.IN, "initial": GPIO.LOW},
         "CONFIRM_BAD_SWITCH": {"pin": 32, "direction": GPIO.IN, "initial": GPIO.LOW},
         "GREEN_LED": {"pin": 18, "direction": GPIO.OUT, "initial": GPIO.LOW},
         "RED_LED": {"pin": 22, "direction": GPIO.OUT, "initial": GPIO.LOW},
         }

tasks_execution_order = (BarCodeReadTask,
                        VoltageTest,
                         UARTConnectionTask,
                         FlashWifiModuleTask,
                         FlashMCUTask,
                         PingTest,
                         )



# self.test_voltages,
# self.connect_uart,
# self.flash_wifi_module,
# self.flash_mcu,
# self.test_ping,
# self.get_self_test_report,
# self.test_segment_screen,
# self.test_leds,
# self.test_buttons,
# self.test_relay,
# self.test_slider,
# self.print_sticker,
# self.test_wifi_connect,
# self.test_voltages,
# )
