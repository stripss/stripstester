import RPi.GPIO as GPIO
import devices
from config_loader import *

from strips_tester import *
import strips_tester
from strips_tester import settings
from tester import Task, timeout

import datetime

module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

gpios = strips_tester.settings.gpios
relays = strips_tester.settings.relays
custom_data = strips_tester.settings.custom_data

class StartProcedureTask(Task):
    def run(self) -> (bool, str):
        gui_web.send({"command": "status", "value": "Za začetek testiranja zapri pokrov."})
        gui_web.send({"command": "progress", "nest": 0, "value": "0"})

        while True:
            state_GPIO_SWITCH = GPIO.input(gpios.get("START_SWITCH"))
            if not state_GPIO_SWITCH:
                break

            time.sleep(0.01)

        shifter = LED_Indicator()
        shifter.set(int(custom_data['led_green_' + str(self.nest_id + 1)], 16))
        shifter.set(int(custom_data['led_red_' + str(self.nest_id + 1)], 16))



        gui_web.send({"command": "progress", "nest": self.nest_id, "value": "25"})
        strips_tester.data['start_time'][self.nest_id] = datetime.datetime.utcnow()  # Get start test date
        gui_web.send({"command": "time", "mode": "start", "nest": self.nest_id})  # Start count for test
        gui_web.send({"command": "error", "nest": self.nest_id, "value": -1})  # Clear all error messages
        gui_web.send({"command": "info", "nest": self.nest_id, "value": -1})  # Clear all info messages

        gui_web.send({"command": "semafor", "nest": self.nest_id, "value": (0, 1, 0), "blink": (0, 0, 0)})

        time.sleep(1)  # Delay for DUT insertion

        return

    def tear_down(self):
        pass

# Perform product detection
class InitialTest(Task):
    def set_up(self):
        pass

    def run(self) -> (bool, str):
        gui_web.send({"command": "status", "nest": self.nest_id, "value": "Blinkanje LED diod"})  # Clear all info messages
        gui_web.send({"command": "progress", "nest": self.nest_id, "value": "34"})


        gui_web.send({"command": "progress", "nest": self.nest_id, "value": "69"})

        GPIO.output(gpios['ENABLE_' + str(self.nest_id + 1)], GPIO.LOW)
        acc = 0.005
        for i in range(3600):
            if acc > 0:
                acc = acc - 0.00001
            GPIO.output(gpios['STEP_' + str(self.nest_id + 1)], GPIO.HIGH)
            GPIO.output(gpios['STEP_' + str(self.nest_id + 1)], GPIO.LOW)
            time.sleep(0.0001 + acc)
        GPIO.output(gpios['ENABLE_' + str(self.nest_id + 1)], GPIO.HIGH)

        end_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=5)


        gui_web.send({"command": "status", "nest": self.nest_id, "value": "Test preklopov stikala"})  # Clear all info messages
        preklop = 0
        old_state = GPIO.input(gpios.get('SIGNAL_' + str(self.nest_id + 1)))
        while datetime.datetime.utcnow() < end_time and preklop <= 5:
            state = GPIO.input(gpios.get('SIGNAL_' + str(self.nest_id + 1)))

            if not old_state and state:
                preklop = preklop + 1
                time.sleep(0.01)

                gui_web.send({"command": "info", "nest": self.nest_id, "value": "Preklop"})

            old_state = state

        gui_web.send({"command": "info", "nest": self.nest_id, "value": "Čas za preklope se je iztekel"})

        strips_tester.data['exist'][self.nest_id] = True

        if preklop > 5:
            self.add_measurement(self.nest_id, True, "switches", preklop, "")
            gui_web.send({"command": "info", "nest": self.nest_id, "value": "Preklopi OK. ({})" . format(preklop)})
        else:
            self.add_measurement(self.nest_id, False, "switches", preklop, "")
            gui_web.send({"command": "error", "nest": self.nest_id, "value": "Nezadostno število preklopov! ({})" . format(preklop)})

        time.sleep(0.5)
        return

    def tear_down(self):
        pass


class ProductConfigTask(Task):
    def set_up(self):
        module_logger.debug("ProductConfigTask init")

    def run(self):
        if strips_tester.data['exist'][self.nest_id]:
            if strips_tester.data['status'][self.nest_id] == -1:
                strips_tester.data['status'][self.nest_id] = True

        return

    def tear_down(self):
        pass


class PrintSticker(Task):
    def set_up(self):
        self.godex_found = False
        for i in range(10):
            try:
                self.godex = devices.GoDEXG300(port='/dev/godex', timeout=3.0)
                self.godex_found = True
                break
            except Exception as ee:
                print(ee)

                time.sleep(0.1)

        #self.godex = devices.Godex(port='/dev/usb/lp0', timeout=3.0)
        self.shifter = devices.HEF4094BT(24, 31, 26, 29)

    def run(self):
        # Unlock test device
        self.shifter.set("K9", False)
        self.shifter.invertShiftOut()

        for i in range(2):
            gui_web.send({"command": "progress", "nest": i, "value": "100"})
            #gui_web.send({"command": "semafor", "nest": i, "blink": (0, 1, 0)})

        # wait for open lid
        if not strips_tester.data['exist'][0] and not strips_tester.data['exist'][1]:
            gui_web.send({"command": "status", "value": "Za konec testa odpri pokrov"})
            module_logger.info("Za konec testa odpri pokrov")
        else:
            module_logger.info("Za tiskanje nalepke odpri pokrov")
            gui_web.send({"command": "status", "value": "Za tiskanje nalepke odpri pokrov"})

        if not self.godex_found:
            for current_nest in range(2):
                if strips_tester.data['exist'][current_nest]:
                    gui_web.send({"command": "error", "nest": current_nest, "value": "Tiskalnika ni mogoče najti!"})
            return

        # Lid is now opened.
        if strips_tester.data['exist'][0]:
            if strips_tester.data['status'][0] != -1:  # if product was tested
                try:
                    self.print_sticker(strips_tester.data['status'][0])
                except Exception:
                    pass

        if strips_tester.data['exist'][1]:
            if strips_tester.data['status'][1] != -1:  # if product was tested
                try:
                    self.print_sticker(strips_tester.data['status'][1])
                except Exception:
                    pass

        return

    def print_sticker(self, test_status):
        program = get_program_number()

        code = {}
        code['S001'] = 435545
        code['S002'] = 552943
        qc_id = strips_tester.data['worker_id']

        date = datetime.datetime.now().strftime("%d.%m.%Y")

        if test_status == True:  # Test OK
            inverse = '^L\r'
            darkness = '^H15\r'
        elif test_status == False:  # Test FAIL
            inverse = '^LI\r'
            darkness = '^H4\r'
        else:
            return

        if qc_id != -1:
            qc = "QC {}".format(qc_id)
        else:
            qc = ""

        label = ('^Q9,3\n'
                 '^W21\n'
                 '{}'
                 '^P1\n'
                 '^S2\n'
                 '^AD\n'
                 '^C1\n'
                 '^R12\n'
                 '~Q+0\n'
                 '^O0\n'
                 '^D0\n'
                 '^E12\n'
                 '~R200\n'
                 '^XSET,ROTATION,0\n'
                 '{}'
                 'Dy2-me-dd\n'
                 'Th:m:s\n'
                 'AA,8,10,1,1,0,0E,ID:{}     {}\n'
                 'AA,8,29,1,1,0,0E,C-19_PL_UF_{}\n'
                 'AA,8,48,1,1,0,0E,{}  {}\n'
                 'E\n').format(darkness, inverse, code[program], " ", program, date, qc)

        self.godex.send_to_printer(label)
        time.sleep(1)

    def tear_down(self):
        try:
            self.godex.close()
        except Exception:
            pass

class FinishProcedureTask(Task):
    def set_up(self):
        module_logger.debug("FinishProcedureTask init")

    def run(self):
        gui_web.send({"command": "status", "nest": self.nest_id, "value": "Odstrani kos iz ležišča."})  # Clear all info messages
        gui_web.send({"command": "progress", "nest": self.nest_id, "value": "90"})

        while self.lid_closed():
            time.sleep(0.01)

        gui_web.send({"command": "semafor", "nest": self.nest_id, "value": (0, 0, 0)})

        shifter = LED_Indicator()
        shifter.clear(int(custom_data['led_green_' + str(self.nest_id + 1)], 16))
        shifter.clear(int(custom_data['led_red_' + str(self.nest_id + 1)], 16))

        if strips_tester.data['exist'][self.nest_id]:
            if strips_tester.data['status'][self.nest_id]:
                shifter.set(int(custom_data['led_green_' + str(self.nest_id + 1)], 16))
                gui_web.send({"command": "semafor", "nest": self.nest_id, "value": (0, 0, 1)})
            else:
                shifter.set(int(custom_data['led_red_' + str(self.nest_id + 1)], 16))
                gui_web.send({"command": "semafor", "nest": self.nest_id, "value": (1, 0, 0)})

        gui_web.send({"command": "progress", "nest": self.nest_id, "value": "100"})

        return

    def lid_closed(self):
        state = GPIO.input(gpios.get("START_SWITCH_" + str(self.nest_id + 1)))

        if state:
            return False
        else:
            return True

    def tear_down(self):
        pass

