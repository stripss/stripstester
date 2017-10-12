import time
import logging

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


class AbstractFlasher:
    def __init__(self, reset, dtr, retries: int = 5, ):
        self.retries = retries
        self.reset = reset
        self.dtr = dtr

    def flash(self):
        self.setup(self.reset, self.dtr)
        success = False
        module_logger.info("Flashing")
        for retry_number in range(5):
            if self.run_flashing():
                module_logger.info("Flash successful")
                return True
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
            module_logger.info("%s looks normal, measured: %s%s", self.property, self.value, self.unit)
            return True
        else:
            module_logger.error("%s is out of bounds: %s%s", self.property, self.value, self.unit)
            return False


