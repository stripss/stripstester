import hid
from strips_tester import logger


class SainBoard16:
    # define command messages
    OPEN_CMD = (0xD2, 0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x48, 0x49, 0x44, 0x43, 0x80, 0x02, 0x00, 0x00)
    CLOSE_CMD = (0x71, 0x0E, 0x71, 0x00, 0x00, 0x00, 0x11, 0x11, 0x00, 0x00, 0x48, 0x49, 0x44, 0x43, 0x2A, 0x02, 0x00, 0x00)

    def __init__(self, vid: int = 0x0416, pid=0x5020, path: str = None, initial_status=None, number_of_relays: int = 16):
        self.__WRITE_CMD = [0xC3, 0x0E, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x48, 0x49, 0x44, 0x43, 0xEE, 0x01, 0x00, 0x00]
        self.number_of_relays = number_of_relays
        self.board = hid.device()
        if path:
            self.board.open_path(path)
        else:
            self.board.open(vid, pid)
        self.board.write(self.OPEN_CMD)
        logger.debug("Relayboard opened")
        self.status = initial_status if initial_status else [False] * number_of_relays

    def __del__(self):
        self.board.write(self.CLOSE_CMD)
        self.board.close()

    def _write_status(self):
        # update status
        status_int = 0
        for i, val in enumerate(reversed(self.status)):
            if val:
                status_int += 1 << i
        self.__WRITE_CMD[2] = status_int & 0xff
        self.__WRITE_CMD[3] = status_int >> 8
        # update checksum
        chksum = 0
        length = self.__WRITE_CMD[1]
        for i in range(length):
            chksum += self.__WRITE_CMD[i]
        for i in range(4):
            self.__WRITE_CMD[length+i] = chksum & 0xff
            chksum = chksum >> 8
        self.board.write(self.__WRITE_CMD)


    def open_relay(self, relay_number: int):
        """ Opens relay by its number """
        if 1 <= relay_number <= self.number_of_relays:
            self.status[relay_number - 1] = False
        else:
            logger.critical("Relay number out of bounds")
        self._write_status()
        logger.debug("Relay %s OPENED", relay_number)

    def close_relay(self, relay_number: int):
        """ Connect/close_relay relay by its number """
        if 1 <= relay_number <= self.number_of_relays:
            self.status[relay_number - 1] = True
        else:
            logger.critical("Relay number out of bounds")
        self._write_status()
        logger.debug("Relay %s CLOSED", relay_number)

    # Opens all relays_config
    def open_all(self):
        self.status = [False] * self.number_of_relays
        self._write_status()
        logger.debug("All relays_config opened")

    # Closes all relays_config
    def close_all(self):
        self.status = [True] * self.number_of_relays
        self._write_status()
        logger.debug("All relays_config closed")

    # @staticmethod
    # def set_bit(original: int, index: int, value: bool):
    #     """Set the index-th bit of original to 1 if value is truthy, else to 0, and return the new value."""
    #     mask = 1 << index  # Compute mask, an integer with just bit 'index' set.
    #     new = original & ~mask  # Clear the bit indicated by the mask (if value is False)
    #     if value:
    #         new = original | mask  # If value was True, set the bit indicated by the mask.
    #     return new
