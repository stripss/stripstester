from strips_tester import CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET
from strips_tester import logger
from strips_tester.tester import Task
from strips_tester.digitalmultimeter import DigitalMultiMeter
from strips_tester.hid_relay import RelayBoard

# You may set global test level and logging level in config.py file
# Tests severity levels matches python's logging levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Failing "CRITICAL" test will immediately block execution of further tests! (and trigger "on_critical" event)


# Define tests and task as classes that inheriting from tester.Task
# First param is test level, default is set to CRITICAL
# run method should return test status (True if test passed/False if it failed) and result (value)
class BarCodeReadTask(Task):
    super().__init__(CRITICAL)

    def set_up(self):
        pass

    def run(self) -> (bool, str):
        return False, "Not implemented yet"

    def tear_down(self):
        pass


class VoltageTest(Task):
    super().__init__(CRITICAL)

    def set_up(self):
        self.vc820 = DigitalMultiMeter(port='/dev/ttyUSB0')
        self.relay_board = RelayBoard(0x0416, 0x5020, initial_status=0x0000)

    def run(self) -> (bool, str):
        return False, "Not implemented yet"

    def tear_down(self):
        self.vc820.close()
        self.relay_board.open_all_relays()


class UARTConnectionTask(Task):
    super().__init__(CRITICAL)

    def set_up(self):
        pass

    def run(self):
        return False, "Not implemented yet"

    def tear_down(self):
        pass


class FlashWifiModuleTask(Task):
    super().__init__(CRITICAL)

    def set_up(self):
        pass

    def run(self):
        return False, "Not implemented yet"

    def tear_down(self):
        pass


class FlashMCUTask(Task):
    super().__init__(CRITICAL)

    def set_up(self):
        pass

    def run(self):
        return False, "Not implemented yet"

    def tear_down(self):
        pass


class PingTest(Task):
    super().__init__(ERROR)

    def set_up(self):
        pass

    def run(self):
        return False, "Not implemented yet"

    def tear_down(self):
        pass



