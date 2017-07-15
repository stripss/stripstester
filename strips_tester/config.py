import os
import sys
import logging
import RPi.GPIO as GPIO

sys.path += [os.path.dirname(os.path.dirname(os.path.realpath(__file__))),]


module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

######## CONSTANTS ########
TEST_LEVEL = logging.NOTSET  # test everything above this level. NOTSET (0) is default and covers all levels
LOGGING_LEVEL = logging.INFO  # log everything above this level. NOTSET (0) is default and covers all levels

G_INPUT = GPIO.IN  #1
G_OUTPUT = GPIO.OUT  #0
G_HIGH = R_CLOSED = 1
G_LOW = R_OPEN = 0
G_PUD_DOWN = GPIO.PUD_DOWN  #21
G_PUD_UP = GPIO.PUD_UP  #22
G_PUD_OFF = GPIO.PUD_OFF  #20
# set desired default pull up/down:
DEFAULT_PULL = G_PUD_UP

######## DEFINE GPIOS ########
# example : "START_SWITCH": {"pin": 12, "function": G_INPUT, "pull": G_PUD_DOWN},
#           "RST": {"pin": 18, "function": G_OUTPUT, "initial": G_LOW},

gpios_config = {"START_SWITCH": {"pin": 12, "function": G_INPUT, "pull": G_PUD_UP},  # initial is low because tester waits for rising edge to start...
                "DETECT_SWITCH": {"pin": 26, "function": G_INPUT, "pull": G_PUD_UP},
                "WIFI_PRESENT_SWITCH": {"pin": 16, "function": G_INPUT, "pull": G_PUD_UP},
                "DISPLAY_OK_FAIL_SWITCH": {"pin": 24, "function": G_INPUT, "pull": G_PUD_UP},
                "CONFIRM_GOOD_SWITCH": {"pin": 36, "function": G_INPUT, "pull": G_PUD_UP},
                "CONFIRM_BAD_SWITCH": {"pin": 32, "function": G_INPUT, "pull": G_PUD_UP},
                "RST": {"pin": 18, "function": G_OUTPUT, "initial": G_LOW},
                "DTR": {"pin": 22, "function": G_OUTPUT, "initial": G_LOW},
                "LIGHT_GREEN": {"pin": 24, "function": G_OUTPUT, "initial": G_LOW},

                }
# GPIO pin finder helper. Example: gpios["START_SWITCH"] -> pin_number:int
gpios = {gpio: gpios_config.get(gpio).get("pin") for gpio in gpios_config}

######## DEFINE RELAYS ########
# example :       {"Vc": {"pin": 1, "initial": R_OPEN},
#                  "12V": {"pin": 2, "initial": R_OPEN},
#                  "5V": {"pin": 3, "initial": R_OPEN},}

relays_config = {"Vc": {"pin": 1, "initial": R_OPEN},
                 "12V": {"pin": 2, "initial": R_OPEN},
                 "5V": {"pin": 3, "initial": R_OPEN},
                 "3V3": {"pin": 4, "initial": R_OPEN},
                 "COMMON": {"pin": 5, "initial": R_OPEN},
                 "RE2": {"pin": 6, "initial": R_OPEN},
                 "RE1": {"pin": 7, "initial": R_OPEN},
                 "UART_MCU_RX": {"pin": 8, "initial": R_OPEN},
                 "UART_MCU_TX": {"pin": 9, "initial": R_OPEN},
                 "UART_WIFI_RX": {"pin": 10, "initial": R_OPEN},
                 "UART_WIFI_TX": {"pin": 11, "initial": R_OPEN},
                 "GND": {"pin": 12, "initial": R_OPEN},
                 "DTR_MCU": {"pin": 13, "initial": R_OPEN},
                 "RST": {"pin": 14, "initial": R_OPEN},
                 "DTR_WIFI": {"pin": 15, "initial": R_OPEN},
                 "LED_RED": {"pin": 16, "initial": R_OPEN},
                 }
# Relay pin finder helper. Example: relays["12V"] -> pin_number:int
relays = {relay: relays_config.get(relay).get("pin") for relay in relays_config}


######## SPECIFY TASK ECECUTION ORDER ########

# import here to prevent circular dependency
import custom_tasks
tasks_execution_order = (
    custom_tasks.BarCodeReadTask,
    custom_tasks.StartProcedureTask,

    custom_tasks.VoltageTest,
    # custom_tasks.FlashWifiModuleTask,
    custom_tasks.FlashMCUTask,
    # custom_tasks.UartPingTest,
    custom_tasks.InternalTest,
    # custom_tasks.ManualLCDTest,

    # custom_tasks.CameraTest,
    custom_tasks.FinishProcedureTask,
    custom_tasks.PrintSticker,
)


######## DEFINE KEY FUNCTIONS ########

# called on critical event during testing
def on_critical_event(event: str):
    # insert custom code to prevent possible damage like:
    # GPIO.wait_for_edge(gpios.get("START_SWITCH"), GPIO.RISING)
    module_logger.exception("On critical Event!")
    finish = custom_tasks.FinishProcedureTask()
    finish._execute(logging.NOTSET)  # NOTSET executes it no matter what
    p = custom_tasks.PrintSticker()
    p._execute(logging.NOTSET)

