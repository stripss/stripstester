import os

import select
import serial
from strips_tester import logger

hid = {4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j', 14: 'k', 15: 'l', 16: 'm',
       17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's', 23: 't', 24: 'u', 25: 'v', 26: 'w', 27: 'x', 28: 'y', 29: 'z',
       30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0', 44: ' ', 45: '-', 46: '=',
       47: '[', 48: ']', 49: '\\', 51: ';', 52: '\'', 53: '~', 54: ',', 55: '.', 56: '/'}

class CodeReader:
    def __init__(self, path: str = "/dev/hidraw0", scan_code_length: int = 25):
        self.path = path
        self.scan_code_length = scan_code_length

    def wait_for_read(self):
        try:
            reader_fo = os.open(self.path, os.O_RDWR)
            # r, w, e = select.select([reader_fo], [], [], 0)
            scanned_chars = bytearray()
            for line in range(self.scan_code_length):
                buffer = os.read(reader_fo, 8)
                scanned_chars.append(buffer[3])
            scanned_code = "".join(hid.get(i) if 3 < i < 57 else "?" for i in scanned_chars )
            return scanned_code
        except Exception as ex:
            logger.exception("Reading stream CodeReader Exception %s", ex)

    def read_last_read(self):
        #todo implement
        pass

c = 0
while 1:
    c+=1
    [ord(i) for i in os.read(reader_fo, 8)]
    print(c)

reader_fo = os.open("/dev/hidraw0", os.O_RDWR)
# r, w, e = select.select([reader_fo], [], [], 0)
scanned_chars = bytearray()
for _ in range(25):
    buffer = os.read(reader_fo, 8)
    scanned_chars.append(buffer[2])
scanned_code = "".join((hid.get(i) if 3 < i < 57 else "?" for i in scanned_chars))
print(scanned_code)
