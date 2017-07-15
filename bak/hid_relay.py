import hid
from strips_tester import logger


class RelayBoard:
    def __init__(self, vid: int = None, pid=None, path: str = None, initial_status: int = 0x0000):
        if path:
            self.board = hid.Device(vid, pid, path)
        self.status = initial_status
        self.board.write(self.status)

    @staticmethod
    def set_bit(original: int, index: int, value: bool):
        """Set the index-th bit of original to 1 if value is truthy, else to 0, and return the new value."""
        mask = 1 << index  # Compute mask, an integer with just bit 'index' set.
        new = original & ~mask  # Clear the bit indicated by the mask (if value is False)
        if value:
            new = original | mask  # If value was True, set the bit indicated by the mask.
        return new

    def _write(self, relay_number: int, value: bool):
        if 0 < relay_number < 17:
            self.status = self.set_bit(self.status, relay_number - 1, value)
            self.board.write(self.status)
            logger.debug("Relay %s %s", relay_number, "CLOSED" if value else "OPENED")
        else:
            logger.critical("Relay number out of bounds")

    def open(self, relay_number: int):
        """ Opens relay by its number """
        self._write(relay_number, False)

    def close(self, relay_number: int):
        """ Connect/close relay by its number """
        self._write(relay_number, True)

    # Opens all relays
    def open_all(self):
        self.status = 0x0000
        self.board.write(self.status)
        logger.debug("All relays opened")

    # Closes all relays
    def close_all(self):
        self.status = 0xffff
        self.board.write(self.status)
        logger.debug("All relays closed")