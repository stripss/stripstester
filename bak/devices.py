import os
import select

import logging
import sys
import numpy as np
import serial
import hid
from time import sleep
from datetime import datetime
import picamera.array
#from matplotlib import pyplot as pp
import time
import json
import picamera
from picamera import PiCamera
sys.path += [os.path.dirname(os.path.dirname(os.path.realpath(__file__))),]
from strips_tester import *
from yocto_api import *
from yocto_voltage import *
from abstract_devices import VoltMeter, Flasher, Sensor

from smbus2 import SMBus, i2c_msg
from smbus2 import SMBusWrapper

module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

class Honeywell1400:
    hid_lookup = {4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j', 14: 'k', 15: 'l', 16: 'm',
                  17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's', 23: 't', 24: 'u', 25: 'v', 26: 'w', 27: 'x', 28: 'y', 29: 'z',
                  30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0', 44: ' ', 45: '-', 46: '=',
                  47: '[', 48: ']', 49: '\\', 51: ';', 52: '\'', 53: '~', 54: ',', 55: '.', 56: '/', 81: '\n'}

    def __init__(self, vid: int = 0x0c2e, pid: int = 0x0b81, path: str = "/dev/hilslsdraw1", max_code_length: int = 50):
        self.vid = vid
        self.pid = pid
        self.path = path
        self.max_code_length = max_code_length
        self.logger = logging.getLogger(__name__)

    def flush_input(self, file_descriptor) -> bytearray():
        discarded = bytearray()
        while select.select([file_descriptor], [], [], 0)[0]:
            discarded.append(os.read(file_descriptor, 8))
        return discarded

    def wait_for_read(self, inter_char_timeout_sec: float = 0.1) -> str:
        try:
            reader_fd = os.open(self.path, os.O_RDWR)
            if select.select([reader_fd], [], [], 0)[0]:
                self.flush_input(reader_fd)
            scanned_chars = bytearray()
            first_modifier_bytes = bytearray()
            code_length = 0
            for char in range(self.max_code_length):
                buffer = os.read(reader_fd, 8)
                first_modifier_bytes.append(buffer[0])
                scanned_chars.append(buffer[2])
                code_length += 1
                if not select.select([reader_fd], [], [], inter_char_timeout_sec)[0]:
                    break
            scanned_code = []
            for modifier, char_int in zip(first_modifier_bytes, scanned_chars):
                char = self.hid_lookup.get(char_int, None)
                if char:
                    if modifier == 2:
                        char = char.capitalize()
                    scanned_code.append(char)
            return "".join(scanned_code)
        except Exception as ex:
            self.logger.exception("Reading stream Honeywell1400 Exception %s", ex)



            # def wait_for_read_hid(self, scan_length: int = 29):
            #     device = hid.device()
            #     device.open_relay(self.vendor_id, self.product_id)
            #     device.set_nonblocking(1)
            #
            #     chars = []
            #     for i in range(self.max_code_length):
            #         line = device.read(64)
            #         chars.append(line[2])
            #     return "".join((hid_lookup.get(c) if 3 < c < 57 else "?" for c in chars))



class DigitalMultiMeter:
    """
    # the port that we're going to use.  This can be a number or device name.
    # on linux or posix systems this will look like /dev/tty2 or /dev/ttyUSB0
    # on windows this will look something like COM3
    port = '/dev/ttyUSB0'
    # get an instance of the class
    dmm = tp4000zc.DigitalMultiMeter(port)
    # read a value
    val = dmm.read()

    print val.text       # print the text representation of the value
                         # something like: -4.9 millivolts DC
    print val.numeric_val # and the numeric value
                         # ie: -0.0048
    # recycle the serial port
    dmm.close_relay()
    Public Interface:
    __init__(port, retries=3, timeout=3.0):
        Instantiating the class attempts to open_relay the serial port specified,
        initialize it and read enough from the serial port to synchronize
        the module with the start/end of a full reading.
    read():
        Attempt to get a complete reading off of the serial port, parse it and
        return an instance of DmmValue holding the interpretted reading.
    close_relay():
        Finally you can close_relay the serial port connection with close_relay()
    Exceptions will be raised if
       * PySerial raises an exception (SerialException or ValueError)
       * this module can't get a full reading that passes initial data integrity
         checks (subclasses of DmmException)
       * I made a coding error (whatever python might throw)
    If no exceptions are raised the DmmValue might still fail various sanity
    checks or not have a numeric value.  Ie I believe that showing showing
    multiple decimal points makes no sense but is valid per the protocol so
    no exception is raised but the sane_value flag will be set to False in the
    DmmValue.
    Meter Documentation:
    Per the documentation page, the meter spits out readings which are bursts of
    14 bytes every .25 seconds.  The high nibble of each byte is the byte number
    (1-14) for synchronization and sanity checks, the low nibble holds the data.
    Each data bit represents an individual field on the LCD display of the meter,
    from segments of the 7 segment digits to individual flags.  Bytes 1 and 10-14
    are flags (with four bits reserved/unmapped on this meter) and bytes (2,3),
    (4,5), (5,6) and (7,8) representing the individual digits on the display.
    For the digits, if the high bit of the first nibble of a digit is set then the
    negative sign (for the first digit) or the leading decimal point is turned on.
    the remaining bits of the two nibbles represent the elements of the 7 segment
    digit display as follows:
      pos 1       nibble 1:   S123
     p     p      nibble 2:   4567
     o     o      where S is either the sign or decimal bit.
     s     s
     2     7      The legal values of the segment bits are represented in
      pos 6       digit_table and include the digits 0-9 along with blank and
     p     p      'L'.
     o     o
     s     s
     1     5
      pos 4
    Serial settings for this meter are:
    2400 baud 8N1
    """

    bytes_per_read = 14

    def __init__(self, port='/dev/ttyUSB0', retries=3, timeout=3.0):
        self.logger = logging.getLogger(__name__)
        self.ser = serial.Serial(
            port=port,
            baudrate=2400,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=timeout,
            dsrdtr=False,
            rtscts=False,
            xonxoff=False, )
        self.retries = retries  # the number of times it's allowed to retry to get a valid 14 byte read
        self.ser.dtr = True
        self.ser.rts = False
        self.ser.flushOutput()
        self.ser.flushInput()

        # Workaround for problematic first byte
        self.ser.read(1)

        self._synchronize()


    def close(self):
        """Close the serial port connection."""
        self.ser.close()

    def read(self, flush=True):
        "Attempt to take a reading from the digital multimeter."

        # flush to get fresh value
        if flush:
            self.ser.flushInput()
        # self.ser.flushOutput()
        # first get a set of bytes and validate it.
        # if the first doesn't validate, synch and get a new set.
        success = False
        for read_attempt in range(self.retries):
            bytes = self.ser.read(self.bytes_per_read)
            if len(bytes) != self.bytes_per_read:
                self._synchronize()
                continue

            for pos, byte in enumerate(bytes, start=1):
                if byte // 16 != pos:
                    self._synchronize()
                    break
            else:
                success = True
                break

            # if we're here we need to resync and retry
            self._synchronize()

        if not success:
            raise self.DmmReadFailure()

        val = ''
        for (d1, d2, ch) in self.digits:
            high_bit, digit = self._read_digit(bytes[d1 - 1], bytes[d2 - 1])
            if high_bit:
                val = val + ch
            val = val + digit

        attribs = self._init_attribs()
        for k, v in self.bits.items():
            self._read_attrib_byte(bytes[k - 1], v, attribs)

        return self.DmmValue(val, attribs, read_attempt, bytes)

    def _synchronize(self):
        v = self.ser.read(1)
        if len(v) != 1:
            self.logger.warning("Problem synchronizing Digital multimeter")
            print("Problem synchronizing Digital multimeter")
            raise self.DmmNoData()
        n = ord(v)
        pos = n // 16
        if pos == 0 or pos == 15:
            self.logger.debug("Synchronizing even more...")
            print("Synchronizing even more...")
            self._synchronize()  # watch out, possible infinite loop
            # raise self.DmmInvalidSyncValue()

        bytes_needed = self.bytes_per_read - pos
        if bytes_needed:
            v = self.ser.read(bytes_needed)
            # should we check the validity of these bytes?
            # the read() function allows an occasional invalid
            # read without throwing an exception so for now
            # I'll say no.

    bits = {
        1: [('flags', 'AC'), ('flags', 'DC'), ('flags', 'AUTO'), ('flags', 'RS232')],
        10: [('scale', 'micro'), ('scale', 'nano'), ('scale', 'kilo'), ('measure', 'diode')],
        11: [('scale', 'milli'), ('measure', '% (duty-cycle)'), ('scale', 'mega'),
             ('flags', 'beep')],
        12: [('measure', 'Farads'), ('measure', 'Ohms'), ('flags', 'REL delta'),
             ('flags', 'Hold')],
        13: [('measure', 'Amps'), ('measure', 'volts'), ('measure', 'Hertz'),
             ('other', 'other_13_1')],
        14: [('other', 'other_14_4'), ('measure', 'degrees Celcius'), ('other', 'other_14_2'),
             ('other', 'other_14_1')]}

    digits = [(2, 3, '-'), (4, 5, '.'), (6, 7, '.'), (8, 9, '.')]
    digit_table = {(0, 5): '1', (5, 11): '2', (1, 15): '3', (2, 7): '4', (3, 14): '5',
                   (7, 14): '6', (1, 5): '7', (7, 15): '8', (3, 15): '9', (7, 13): '0',
                   (6, 8): 'L', (0, 0): ' '}

    def _init_attribs(self):
        return {'flags': [], 'scale': [], 'measure': [], 'other': []}

    def _read_attrib_byte(self, byte, bits, attribs):
        b = byte % 16
        bit_val = 8
        for (attr, val) in bits:
            v = b // bit_val
            if v:
                b = b - bit_val
                # print "adding flag type %s, val %s"%(attr, val)
                attribs[attr].append(val)
            bit_val //= 2

    def _read_digit(self, byte1, byte2):
        b1 = byte1 % 16
        highBit = b1 // 8
        b1 = b1 % 8
        b2 = byte2 % 16
        try:
            digit = self.digit_table[(b1, b2)]
        except:
            digit = 'X'
        return highBit, digit

    class DmmValue:
        """
        This is a representation of a single read from the multimeter.
        Attributes in rough order of usefulness:

        Sanity checks:
           sane_value: True if no sanity checks failed.

        High level computed fields:
           text: Nicely formatted text representation of the value.
           numeric_val: numeric value after SI prefixes applied or None if value is non-numeric.
           measurement: what is being measured.
           delta: True if the meter is in delta mode.
           ACDC: 'AC', 'DC' or None.
           read_errors:  Number of failed reads attempts before successfully getting a reading
               from the meter.
        Other, possibly useful, computed fields:
           val: cleaned up display value
           scale: SI prefix for val
        Unprocessed values:
           raw_val: Numeric display
           flags: Various flags modifying the measurement
           scale_flags: SI scaling factor flags
           measurement_flags: Flags to specify what the meter is measuring
           reserved_flags: Flags that are undefined
           raw_bytes:  the raw, 14 byte bitstream that produced this value.

        """

        def __init__(self, val, attribs, readErrors, rawBytes):
            self.sane_value = True
            self.raw_val = self.val = val
            self.flags = attribs['flags']
            self.scale_flags = attribs['scale']
            self.measurement_flags = attribs['measure']
            self.reserved_flags = attribs['other']
            self.read_errors = readErrors
            self.raw_bytes = rawBytes
            self.text = 'Invalid Value'

            self.process_flags()
            self.process_scale()
            self.process_measurement()
            self.process_val()

            if self.sane_value:
                self.create_text_expression()

        def create_text_expression(self):
            text = self.delta_text
            text += self.val
            text += ' '
            text += self.scale
            text += self.measurement
            text += self.ACDCText
            self.text = text

        def process_flags(self):
            flags = self.flags
            self.ACDC = None
            self.ACDCText = ''
            self.delta = False
            self.delta_text = ''

            if 'AC' in flags and 'DC' in flags:
                self.sane_value = False
            if 'AC' in flags:
                self.ACDC = 'AC'
            if 'DC' in flags:
                self.ACDC = 'DC'
            if self.ACDC is not None:
                self.ACDCText = ' ' + self.ACDC
            if 'REL delta' in flags:
                self.delta = True
                self.delta_text = 'delta '

        scale_table = {'nano': 0.000000001, 'micro': 0.000001, 'milli': 0.001,
                       'kilo': 1000.0, 'mega': 1000000.0}

        def process_scale(self):
            s = self.scale_flags
            self.scale = ''
            self.multiplier = 1

            if len(s) == 0:
                return
            if len(s) > 1:
                self.sane_value = False
                return
            self.scale = s[0]
            self.multiplier = self.scale_table[self.scale]

        def process_measurement(self):
            m = self.measurement_flags
            self.measurement = None
            if len(m) != 1:
                self.sane_value = False
                return
            self.measurement = m[0]

        def process_val(self):
            v = self.raw_val
            self.numeric_val = None
            if 'X' in v:
                self.sane_value = False
                return
            if v.count('.') > 1:
                self.sane_value = False
                return

            n = None
            try:
                n = float(v)
            except:
                pass

            if n is not None:
                self.val = '%s' % n  # this should remove leading zeros, spaces etc.
                self.numeric_val = n * self.multiplier

        def __repr__(self):
            return "<DmmValue instance: %s>" % self.text

    class DmmException(Exception):
        "Base exception class for DigitalMultiMeter."

    class DmmNoData(DmmException):
        "Read from serial port timed out with no bytes read."

    class DmmInvalidSyncValue(DmmException):
        "Got an invalid byte during syncronization."

    class DmmReadFailure(DmmException):
        "Unable to get a successful read within the number of allowed retries."


class GoDEXG300:
    def __init__(self, port='/dev/ttyUSB0', timeout=3.0):
        self.ser = serial.Serial(
            port=port,
            baudrate=9600,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=timeout,
            dsrdtr=False,
            rtscts=False,
            xonxoff=False, )
        self.ser.dtr = True
        self.ser.rts = False
        self.ser.flushOutput()
        self.ser.flushInput()
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def generate(article_type: str, release: str, wifi: str, mac_address: str, test_result: str):
        label_str = ('^Q9,3\n'
                     '^W20\n'
                     '^H13\n'
                     '^P1\n'
                     '^S2\n'
                     '^AD\n'
                     '^C1\n'
                     '^R0\n'
                     '~Q+0\n'
                     '^O0\n'
                     '^D0\n'
                     '^E15\n'
                     '~R200\n'
                     '^XSET,ROTATION,0\n'
                     '^L\n'
                     'Dy2-me-dd\n'
                     'Th:m:s\n'
                     'XRB158,10,4,0,10\n'
                     '0123456789\n'
                     'AB,4,10,1,1,0,0E,{}, {}\n'
                     'AB,4,36,1,1,0,0E,{}\n'
                     'AB,4,62,1,1,0,0E,{}\n'
                     'AD,148,60,1,1,0,0E,{}\n'
                     'E\n'.format(article_type, release, wifi, mac_address, test_result).encode(encoding="ascii"))
        return label_str

    def send_to_printer(self, label_str: str):
        w = self.ser.write(label_str)

    def close(self):
        """Close the serial port connection."""
        self.ser.close()


class SainBoard16:
    # define command messages
    is_open = False
    hid_device = None
    OPEN_CMD = (0xD2, 0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x48, 0x49, 0x44, 0x43, 0x80, 0x02, 0x00, 0x00)
    CLOSE_CMD = (0x71, 0x0E, 0x71, 0x00, 0x00, 0x00, 0x11, 0x11, 0x00, 0x00, 0x48, 0x49, 0x44, 0x43, 0x2A, 0x02, 0x00, 0x00)

    def __init__(self, vid: int = 0x0416, pid=0x5020, path: str = None, initial_status=None, number_of_relays: int = 16):
        self.vid = vid
        self.pid = pid
        self.path = path
        self.__WRITE_CMD = [0xC3, 0x0E, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x48, 0x49, 0x44, 0x43, 0xEE, 0x01, 0x00, 0x00]
        self.number_of_relays = number_of_relays
        self.hid_device = hid.device()
        self.logger = logging.getLogger(__name__)
        self.status = initial_status if initial_status else [False] * number_of_relays
        self.open()

    def open(self):
        if self.is_open:
            self.close()
            self.is_open = False
            if self.path:
                self.hid_device.open_path(self.path)
            else:
                self.hid_device.open(self.vid, self.pid)
            self.hid_device.write(self.OPEN_CMD)
            self.is_open = True
            module_logger.debug("Relay device opened")
        else:
            try:
                if self.path:
                    self.hid_device.open_path(self.path)
                else:
                    self.hid_device.open(self.vid, self.pid)
                self.hid_device.write(self.OPEN_CMD)
                self.is_open = True
            except Exception as e:
                self.is_open = False
                module_logger.warning("Could not open device: %s", e)

    def close(self):
        if self.is_open:
            self.hid_device.close()
            self.is_open = False
            module_logger.debug("hid closed")
        else:
            module_logger.debug("hid was already closed")

    def lock(self):
        if self.is_open:
            self.hid_device.write(self.CLOSE_CMD)
            module_logger.debug("device locked")
        else:
            module_logger.debug("device not open")

    def _write_status(self):
        # update status
        status_int = 0
        for i, val in enumerate(self.status):
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
            self.__WRITE_CMD[length + i] = chksum & 0xff
            chksum = chksum >> 8
        self.hid_device.write(self.__WRITE_CMD)

    def open_relay(self, relay_number: int):
        """ Opens relay by its number """
        if 1 <= relay_number <= self.number_of_relays:
            self.status[relay_number - 1] = False
        else:
            self.logger.critical("Relay number out of bounds")
        self._write_status()
        self.logger.debug("Relay %s OPENED", relay_number)

    def close_relay(self, relay_number: int):
        """ Connect/close_relay relay by its number """
        if 1 <= relay_number <= self.number_of_relays:
            self.status[relay_number - 1] = True
        else:
            self.logger.critical("Relay number out of bounds")
        self._write_status()
        self.logger.debug("Relay %s CLOSED", relay_number)

    # Opens all relays_config
    def open_all_relays(self):
        self.status = [False] * self.number_of_relays
        self._write_status()
        self.logger.debug("All relays_config opened")

    # Closes all relays_config
    def close_all_relays(self):
        self.status = [True] * self.number_of_relays
        self._write_status()
        self.logger.debug("All relays_config closed")

        # @staticmethod
        # def set_bit(original: int, index: int, value: bool):
        #     """Set the index-th bit of original to 1 if value is truthy, else to 0, and return the new value."""
        #     mask = 1 << index  # Compute mask, an integer with just bit 'index' set.
        #     new = original & ~mask  # Clear the bit indicated by the mask (if value is False)
        #     if value:
        #         new = original | mask  # If value was True, set the bit indicated by the mask.
        #     return new

class YoctoVolt(Sensor):
    def __init__(self, delay: int = 1):
        super().__init__(delay,"Voltage", "V")
        self.sensor = None

        errmsg = None
        if YAPI.RegisterHub("usb", errmsg) != YAPI.SUCCESS:
            module_logger.error("Can't load yocto API : %s", errmsg)
            raise "Can't load yocto API"
        # find voltage sensor with name: "VOLTAGE1-A08C8.voltage2"
        self.sensor = YVoltage.FindVoltage("VOLTAGE1-A08C8.voltage1");
        if (self.sensor == None):
            raise ("No yocto device is connected")
        m = self.sensor.get_module()
        target = m.get_serialNumber()
        module_logger.debug("Module %s found with serial number %s", m, target);
        if not (self.sensor.isOnline()):
            raise ('yocto volt is not on')
        module_logger.debug("Yocto-volt init done")

    def get_value(self):
        if (self.sensor.isOnline()):
            return self.sensor.get_currentValue()
        raise ("Yocto volt is not active")

    def close(self):
        YAPI.FreeAPI()


class TempSensorLM75A(Sensor):
    TEMP_REG = 0x00
    ID_REG = 0x07
    ADDR = 0x4b
    def __init__(self, delay: int = 1):
        super().__init__(delay, "Temperature", "°C")
        self.bus = SMBus(1)

    def get_value(self):
        block = self.bus.read_i2c_block_data(TempSensorLM75A.ADDR, TempSensorLM75A.TEMP_REG, 2)
        nine_biter = (block[1] >> 7 | block[0] << 1) & 0xFF
        temperature = nine_biter / 2
        if (block[0] & 0x80) == 0x01:
            temperature = -temperature
        return temperature

    def close(self):
        self.bus.close()

class CameraDevice:

    def __init__(self, config_path: str):
        self.Xres = 128
        self.Yres = 80
        self.thr = 0.8
        self.Idx = None
        self.interval = 80
        self.imgNum = 20

        self.dx = None
        self.dy = None
        self.imgCount = 0

        self.load(config_path)
        self.img = np.empty((self.imgNum, self.Yres, self.Xres, 3),dtype=np.uint8)
        self.Mesh = np.empty((128,240,14),dtype=np.uint8)
        self.mesh_all = np.empty((128, 240, 1), dtype=np.uint8)
        self.dil_mesh = np.empty((128, 240, 1), dtype=np.uint8)
        self.loadMeshImages('/strips_tester_project/garo/mesh', 14)
        self.camera = picamera.PiCamera()
        self.set_camera_parameters(flag=False)
        try:
            # logger.debug("Starting self test")
            # self.self_test()
            pass
        except:
            module_logger.error("Failed to init Camera")

    def close(self):
        self.camera.close()

    @staticmethod
    def nom(index):
        if index < 0:
            return index
        else:
            return None

    @staticmethod
    def mom(index):
        return max(0, index)

    def load(self, file_path):
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
            self.Xres = data['Xres']
            self.Yres = data['Yres']
            self.thr = data['threshold']
            self.Idx = data['Idx']
            self.interval = data['interval']
            self.imgNum = data['image number']

    def save(self, file_path):
        data = {
            'Xres': self.Xres,
            'Yres': self.Yres,
            'threshold': self.thr,
            'Idx': self.Idx,
            'interval': self.interval,
            'image number': self.imgNum
        }
        with open(file_path, 'w') as f:
            json.dump(data, f)

    def is_complete(self):
        return self.images is not None and self.t1 is not None and self.t2 is not None

    #@staticmethod
    def shift_picture(self, img, dx, dy):
        non = lambda s: s if s < 0 else None
        mom = lambda s: max(0, s)
        newImg = np.zeros_like(img)
        newImg[mom(dy):non(dy), mom(dx):non(dx)] = img[mom(-dy):non(-dy), mom(-dx):non(-dx)]
        return newImg

    @staticmethod
    def compare_img(img1, img2, perc=0.8):
        sumImg1 = np.sum(img1)
        sumImg2 = np.sum(np.logical_and(img1, img2))
        return (sumImg2 / sumImg1)

    def loadMeshImages(self, path, imgnum=14):
        '''
        :param path: path to save mesh on rpi
        :param imgnum: number of mesh loaded
        :return:
        '''
        tmp_path = path
        for i in range(imgnum):
            path = os.path.join(tmp_path, 'PictureMask{}.jpg'.format(i))
            img = self.imLoadRaw2d(path, 240, 128, order='xy')
            self.Mesh[:, :, i] = img // 255 # load every seperate mesh
        self.mesh_all = self.imLoadRaw2d('/strips_tester_project/garo/mesh/Mesh.jpg', 240, 128, order='xy')
        self.mesh_all = self.mesh_all // 255 # to get 0s and 1s
        #imgcalib =  self.imLoadRaw3d('/strips_tester_project/garo/mesh/cal_dil_mesh.jpg', 240, 128, 3, order = 'yxz')
        self.dil_mesh = self.imLoadRaw2d('/strips_tester_project/garo/mesh/cal_dil_mesh.jpg', 240, 128, order='xy')
        self.dil_mesh = self.dil_mesh * 255

    def imLoadRaw2d(self, fid, width, height, dtype=np.uint8, order='xy'):
        """

        Funkcija nalozi 2d sliko v surovem formatu

        Parametri
        -------
            fid:
                Ime datoteke

            width:
                Sirina slike
            height:
                Visina slike
            dtype:
                Podatkovni tip slikovnega elementa
            order:
                Vrstni red zapisa surove slike:
                    'xy' - slika zapisana po vrsticah
                    'yx' - slika zapisana po stolpcih

            Vrne:
            -------
            Podatkovno polje numpy. Oblika podatkovnega polja je [height,width]

        """

        slika = np.fromfile(fid, dtype=dtype)

        if order == 'xy':
            slika.shape = [height, width]
        elif order == 'yx':
            slika.shape = [width, height]
            slika = slika.transpose()
        else:
            raise ValueError('Vrstni red ima napačno vrednost.' \
                             'Dopustne vrednosti so \'xy\' ali \'yx\'.')
        return slika

    def compare_bin(self, imgnum=14):
        image = np.zeros((128, 240), dtype=np.uint8)
        for i in range(imgnum):
            image = self.img_thr(self.img[i,:,:,0],50)
            sumMesh = np.sum(np.logical_and(image,self.mesh_all))
            sumImg = np.sum(np.logical_and(image, self.Mesh[:, :, i]))
            if sumImg != sumMesh:
                module_logger.warning("Screen test failed at picture %s", i)
                return False
        module_logger.debug("Screen test succesfull")
        return True

    def compare_bin_shift(self, imgnum=14, shift=6):
        x, y, matrix = self.calibrate(self.dil_mesh, self.img[4, :, :, 0])
        module_logger.info('Max match at, dx :%s, dy : %s, dfi : %s', x, y, 0)

        tx = ty = np.arange(-shift, shift + 1)
        Tx, Ty = np.meshgrid(tx, ty, indexing='xy')
        tx = np.asarray(Tx).flatten()
        ty = np.asarray(Ty).flatten()
        img_sum = np.empty((imgnum, tx.size),dtype=np.uint8)
        img_sum1 = np.empty((imgnum, tx.size), dtype=np.uint8)
        image_i = None
        for i in range(imgnum):
            image_i = self.img[i, :, :, 0] #np.copy(self.shift_picture(self.img[4, :, :, 0], x, y))
            xx, yy, matrix = self.calibrate(self.dil_mesh, image_i)
            image_i = self.img_thr(image_i, 128)
            module_logger.info('Max separate match at, dx :%s, dy : %s, dfi : %s', xx, yy, 0)
            for j in range(tx.size):
                image = self.shift_picture(image_i, tx[j], ty[j])
                sumMesh = np.sum(np.logical_and(image, self.mesh_all))
                isum = np.sum(np.logical_and(image, self.Mesh[:, :, i]))
                img_sum[i,j] = isum
                img_sum1[i,j] = sumMesh
            Idx_num =  np.sum(self.Mesh[:, :, i])
            ind = img_sum[i,:] == Idx_num
            if not np.equal(img_sum[i, :], img_sum1[i, :]).all() or not ind.any():
                module_logger.warning("Screen test failed at picture %s", i)
                #return False
        module_logger.debug("Screen test succesfull")
        return True

    def compare_bin_shift2(self, imgnum=14, shift=4):
        fail_flag = 0
        x, y, matrix = self.calibrate(self.dil_mesh, self.img[4, :, :, 0], shift=7)
        module_logger.info('Max match at, dx :%s, dy : %s, dfi : %s', x, y, 0)
        tx = ty = np.arange(-shift, shift + 1)
        Tx, Ty = np.meshgrid(tx, ty, indexing='xy')
        tx = np.asarray(Tx).flatten()
        ty = np.asarray(Ty).flatten()

        img_sum = np.empty((imgnum, tx.size), dtype=np.uint8)
        img_sum1 = np.empty((imgnum, tx.size), dtype=np.uint8)
        for i in range(imgnum):
            image_i = self.shift_picture(self.img[i, :, :, 0], x, y)
            # if i==3:
            #     image_i = shift_picture(images[:, :, 8], x, y)
            image_i = self.img_thr(image_i, 128)
            xx, yy, matrix = self.calibrate(self.dil_mesh, image_i, shift=7)
            module_logger.info('Max separate match at, dx :%s, dy : %s, dfi : %s', xx, yy, 0)
            for j in range(tx.size):
                image = self.shift_picture(image_i, tx[j], ty[j])
                sumMesh = np.sum(np.logical_and(image, self.mesh_all))
                isum = np.sum(np.logical_and(image, self.Mesh[:, :, i]))
                img_sum[i, j] = isum
                img_sum1[i, j] = sumMesh
            Idx_num = np.sum(self.Mesh[:, :, i])
            ind = img_sum[i, :] == Idx_num
            if not np.equal(img_sum[i, :],img_sum1[i, :]).all() or not ind.any():
                module_logger.warning("Screen test failed at picture %s", i)
                fail_flag = 1
        if fail_flag ==1:
            return False
        else:
            return True


    def set_camera_parameters(self, flag=False):
        if flag:
            module_logger.debug("Set parameters. Setting iso and exposure time. Wait 2.5 s")
            self.camera.resolution = (self.Xres, self.Yres)
            self.camera.framerate = 80
            self.camera.brightness = 30
            time.sleep(2)
            self.camera.iso = 1 # change accordingly
            time.sleep(1)
            self.camera.shutter_speed = self.camera.exposure_speed * 3
            self.camera.exposure_mode = 'off'
            g = self.camera.awb_gains
            self.camera.awb_mode = 'off'
            self.camera.awb_gains = g
            time.sleep(0.5)
        else:
            self.camera.resolution = (self.Xres, self.Yres)
            self.camera.framerate = 80
            time.sleep(3)

    def img_thr(self, img, thr = 128):
        oimg = np.zeros_like(img)
        ind1 = img >= thr
        oimg[ind1] = 1
        return oimg

    def im_window(self, img, center, width, ls=1):
        oimg = np.zeros_like(img)
        ind1 = img < center - (width * 0.5)
        ind3 = img > center + (width * 0.5)
        ind2 = np.logical_and(img >= center - width * 0.5, img <= center + width * 0.5)
        oimg[ind1] = False
        oimg[ind3] = False
        oimg[ind2] = ls
        return oimg

    def im_step(self, img, thr=0.6, ls=1):
        oimg = np.zeros_like(img)
        ind1 = img > np.max(img) * thr
        ind2 = img <= np.max(img) * thr
        oimg[ind1] = ls
        oimg[ind2] = 0
        return oimg

    def compare_step_sum(self, img1, img2):
        # img1 = self.im_window(img1,230, 40)
        # img2 = self.im_window(img2, 230, 40)
        img1 = self.im_step(img1, 0.6)
        img2 = self.im_step(img2, 0.6)
        sumImg1 = np.sum(img1)
        sumImg2 = np.sum(np.logical_and(img1, img2))
        if sumImg2 > self.thr * sumImg1:
            return sumImg2 / sumImg1, True
        else:
            return sumImg2 / sumImg1, False

    def rigid_sm(self, imgA, imgB, tx, ty):
        txshape = tx.shape
        tx = np.asarray(tx).flatten()
        ty = np.asarray(ty).flatten()
        txxshape = tx.shape
        MSE = np.zeros(txxshape, dtype=np.float64)
        for i in range(tx.size):
            shiftImg = self.shift_picture(imgB, tx[i], ty[i])
            MSE[i] = self.compare_img(imgA, shiftImg, 0.6)
        MSE.shape = txshape
        return MSE

    def imSM(self, imA, imB, sm='CC', nb=16, span=(0, 255)):
        imA = np.asarray(imA, dtype=np.float64)
        imB = np.asarray(imB, dtype=np.float64)

        if sm == 'MSE':
            f = ((imA - imB) ** 2).mean()
            return f

    def rigid_sm_MSE(self, imgA, imgB, tx, ty, ):
        txshape = tx.shape
        tx = np.asarray(tx).flatten()
        ty = np.asarray(ty).flatten()
        txxshape = tx.shape

        MSE = np.zeros(txxshape[0], dtype=np.float64)
        for i in range(tx.size):
            imgBT = self.shift_picture(imgB, tx[i], ty[i])
            MSE[i] = self.imSM(imgA, imgBT, 'MSE')

        MSE.shape = (txshape[0], txshape[1])
        return MSE

    def compare_idx(self):
        x = 1

    def self_test(self):
        time.sleep(1)
        slika1 = np.zeros((self.Xres, self.Yres, 3), dtype=np.uint8)
        slika2 = np.zeros((self.Xres, self.Yres, 3), dtype=np.uint8)
        self.camera.capture(slika1, 'rgb', use_video_port=True)
        module_logger.debug("first pic")
        time.sleep(1)
        self.camera.capture(slika2, 'rgb', use_video_port=True)
        module_logger.debug("second pic")
        perc, result = self.compare_step_sum(slika1[:, :, 0], slika2[:, :, 0])
        if result:
            module_logger.debug('Self test done. Pictures match by : %s percent', perc)
            return True
        else:
            module_logger.debug('Self test failed !!!. Pictures match by %s percent', perc)
            return False

    def calibrate(self, dilmesh, imgB, shift=6):
        # rgbPath = '/strips_tester_project/garo/mesh'
        # path = os.path.join(rgbPath, 'cal_dil_mesh.jpg')
        tx = ty = np.arange(-8, 8 + 1)
        Tx, Ty = np.meshgrid(tx, ty, indexing='xy')
        matrix = self.rigid_sm_MSE(dilmesh, imgB, Tx, Ty)
        txshape = tx.size

        m = np.argmin(matrix)
        x = np.mod(m, np.size(tx))
        y = int(np.floor(m / np.size(tx)))
        ndx = int(Tx[0, x])
        ndy = int(Ty[y, 0])
        #module_logger.info('Max match at, dx :%s, dy : %s, dfi : %s', ndx, ndy, 0)  ## Todo modeule_logger.info
        return ndx, ndy, matrix


    def take_picture(self):
        if self.imgCount >= 0 and  self.imgCount < self.imgNum:
            self.camera.capture(self.img[self.imgCount,:,:,:], 'rgb', use_video_port=True)
            self.imgCount = self.imgCount + 1
        else:
            module_logger.error("Out of memory for picture capture")

    def get_picture(self, Idx=0):
        if Idx < 0 or Idx > self.imgCount:
            module_logger.error("Idx out of bounds for picture access")
            return False
        else:
            return self.img[Idx,:,:,:]

    def take_img_to_array_RGB(self, xres=128, yres=80, RGB=0):
        slika = np.empty([xres, yres, 3], dtype=np.uint8)
        self.camera.capture(slika, 'rgb')
        return slika[:, :, RGB]

    def take_img_to_file(self, file_path):
        time.sleep(1)
        self.camera.capture(file_path)

    def save_img(self, num=None):
        '''
        Save taken picture in raw format to specified path
        :param num: picture number
        :return:
        '''
        if num == None:
            for i in range(self.imgCount):
                self.imSaveRaw('/home/pi/Desktop/Picture{}.jpg'.format(i), self.img[i,:,:,:])
        else:
            self.imSaveRaw('/home/pi/Desktop/Picture{}.jpg'.format(num), self.img[num,:,:,:])

    def imSaveRaw(self, fid, data):
        """
        Funkcija shrani 2d sliko v surovem formatu.

        Parametri
        -------
            fid:
                Ime datoteke

            data:
                Podatki - slika
        """
        data.tofile(fid)

    def imLoadRaw3d(fid, width, height, depth, dtype=np.uint8, order='xyz'):

        slika = np.fromfile(fid, dtype=dtype)

        if order == 'xyz':
            slika.shape = [depth, height, width]

        # ...
        elif order == 'yxz':
            slika.shape = [height, width, depth]
            # slika = slika.transpose([1, 2, 0])

        elif order == 'zyx':
            # Indeksi osi: [ 0  1  2]
            slika.shape = [width, height, depth]
            slika = slika.transpose([2, 1, 0])
        else:
            raise ValueError('Vrstni red ima napačno vrednost.' \
                             'Dopustne vrednosti so \'xyz\' ali \'zyx\'.')
        return slika
