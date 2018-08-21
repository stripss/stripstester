import time
import logging
import threading
module_logger = logging.getLogger(".".join(("strips_tester", __name__)))


# Abstract class for voltmeter
class AbstractVoltMeter:
    def __init__(self, delay: float = 0):
        self.delay = delay
        self.voltage = None

    def close(self):
        raise NotImplementedError

    def get_voltage(self):
        raise NotImplementedError

    def read(self):
        time.sleep(self.delay)
        return self.get_voltage()

    def in_range(self, min, max):
        self.voltage = self.read()
        if min < self.voltage and self.voltage < max:
            module_logger.info("Voltage looks normal, measured: %sV", self.voltage)
            return True
        else:
            module_logger.error("Voltage is out of bounds: %sV", self.voltage)
            return False


class AbstractFlasher(threading.Thread):
    def __init__(self,que, reset, dtr, retries: int = 5):
        self.retries = retries
        self.reset = reset
        self.dtr = dtr
        self.que = que

    def flash(self):
        try:
            self.setup(self.reset, self.dtr)

            success = False
            module_logger.info("Programiranje...")
            print("Programiranje")
            for retry_number in range(5):
                print("RETRYING...")
                if self.run_flashing():
                    module_logger.info("Programiranje uspelo")

                    self.que.put(True)
                    return True
            module_logger.error("Programiranje ni uspelo")

            self.que.put(False)
            return False
        except Exception as ee:
            module_logger.info('Exception %s occured in %s ', ee, type(self).__name__)
            self.que.put(False)
            return False

    def setup(self):
        raise NotImplementedError

    def run_flashing(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def erase(self):
        raise NotImplementedError

    def verify(self):
        raise NotImplementedError


class AbstractSensor:
    def __init__(self, delay: float, property: str, unit: str):
        self.delay = delay
        self.value = None
        self.property = property
        self.unit = unit

    def close(self):
        raise NotImplementedError

    def get_value(self):
        raise NotImplementedError

    def read(self):
        time.sleep(self.delay)
        return self.get_value()

    def in_range(self, min, max):
        self.value = self.read()
        if min < self.value < max:
            module_logger.debug("%s looks normal, measured: %s%s", self.property, self.value, self.unit)
            return True
        else:
            module_logger.error("%s is out of bounds: %s%s", self.property, self.value, self.unit)
            return False


class AbstractBarCodeScanner:
    def __init__(self, name):
        self.name = name
        #self.open()

    def get_decoded_data(self):
        return self.get_dec_data()

    def get_raw_data(self):
        return self.read_raw()

    def open(self):
        self.open_scanner()
        module_logger.debug("%s opened", self.name)

    def close(self):
        self.close_scanner()
        module_logger.debug("%s closed", self.name)
