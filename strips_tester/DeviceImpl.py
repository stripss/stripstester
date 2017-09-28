
import time
import logging
module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

# Abstract class for voltmeter
class Voltmeter:
    def __init__(self, delay: float = 0):
        self.delay = delay
        self.voltage = None

    def close(self):
        pass
    def get_voltage(self):
        pass

    def read(self):
        time.sleep(self.delay)
        return self.get_voltage()

    def voltage_in_range(self, min, max):
        self.voltage = self.read()
        if min < self.voltage and self.voltage < max:
            module_logger.info("Vc looks normal, measured: %sV", self.voltage)
            return True
        else:
            module_logger.error("Vc is out of bounds: %sV", self.voltage)
            return False


class Flasher:
    def __init__(self, retries: int = 5 ):
        self.retries = retries

    def run_flashing(self):
        self.setup()
        success = False
        module_logger.info("Flashing")
        for retry_number in range(5):
            try:
                self.flash()
                success = True
                break
            except Exception as e:
                module_logger.warning("Flash try failed %s", (self.retries-retry_number))
        self.close()
        if not success:
            return False
        module_logger.info("Flash successful")
        return True

    def setup(self):
        pass
    def flash(self):
        pass
    def close(self):
        pass
    def erase(self):
        pass
    def verify(self):
        pass