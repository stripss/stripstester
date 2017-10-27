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
from yoctopuce.yocto_api import *
from yoctopuce.yocto_voltage import *
from strips_tester.abstract_devices import AbstractVoltMeter, AbstractFlasher, AbstractSensor
#from matplotlib import pyplot as pp
from collections import OrderedDict
#from smbus2 import SMBus, i2c_msg
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
    def generate(product_type: str, hw_release: str, variant: str, serial: str, test_result: str):
        # label_str = ('^Q9,3\n'
        #              '^W20\n'
        #              '^H13\n'
        #              '^P1\n'
        #              '^S2\n'
        #              '^AD\n'
        #              '^C1\n'
        #              '^R0\n'
        #              '~Q+0\n'
        #              '^O0\n'
        #              '^D0\n'
        #              '^E15\n'
        #              '~R200\n'
        #              '^XSET,ROTATION,0\n'
        #              '^L\n'
        #              'Dy2-me-dd\n'
        #              'Th:m:s\n'
        #              'XRB158,10,4,0,10\n'
        #              '0123456789\n'
        #              'AB,4,10,1,1,0,0E,{}, {}\n'
        #              'AB,4,36,1,1,0,0E,{}\n'
        #              'AB,4,62,1,1,0,0E,{}\n'
        #              'AD,148,60,1,1,0,0E,{}\n'
        #              'E\n'.format(product_type, hw_release, variant, serial, test_result).encode(encoding="ascii"))
        pass

    def send_to_printer(self, label_str: str):
        w = self.ser.write(label_str.encode(encoding="ascii"))

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

class YoctoVoltageMeter(AbstractSensor):
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


class CameraDevice:
    def __init__(self, Xres: int=640, Yres: int=480):
        self.Xres = Xres
        self.Yres = Yres
        self.img_count = 0
        #max 20 pictures
        self.img = np.empty((20, self.Yres, self.Xres, 3), dtype=np.uint8)

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
            self.camera.framerate = 20
            self.camera.exposure_mode = 'off'
            self.camera.shutter_speed = 50000
            time.sleep(1)

    def take_picture(self):
        self.camera.capture(self.img[self.img_count,::,::,::], 'rgb', use_video_port=True)
        self.img_count += 1

    def take_one_picture(self):
        self.take_picture()
        return self.img[self.img_count-1,::,::,::]

    def get_picture(self, Idx=0):
        return self.img[Idx,::,::,::]

    def take_img_to_array_RGB(self, xres=128, yres=80, RGB=0):
        slika = np.empty([xres, yres, 3], dtype=np.uint8)
        self.camera.capture(slika, 'rgb')
        return slika[:, :, RGB]

    def take_img_to_file(self, file_path):
        time.sleep(1)
        self.camera.capture(file_path)

    def save_all_imgs_to_file(self):
        for i in range(self.img_count):
            self.imSaveRaw3d('/home/pi/Desktop/Picture{}.jpg'.format(i), self.img[i,::,::,::])

    def imSaveRaw3d(self, fid, data):
        data.tofile(fid)



# Algorithms
##################################################################################################################
class CompareAlgorithm:
    def __init__(self, span: int=2):
        '''
        :param span: area on each size of index to check
        '''
        self.span = np.arange(-span, span)
        self.color_edge = 0.2*3*255

    def run(self, images, masks, mask_indices_len, masks_length):
        for j in range(masks_length):
            for i in range(mask_indices_len[j]): # indices_length[j] number of indices to check
                #mask_num x 50 x 5(x,y,R,G,B)
                x = masks[j,i,0]
                y = masks[j,i,1]
                RGB = masks[j,i,2:]
                if not self.compare(x, y, images[j,::,::], RGB):
                    module_logger.error("Failed at picture {} and index  {} with image RGB {} and mesh RGB {}".format(j,i,images[j,y,x], RGB))
                    return False
                break
        return True

    def compare(self, x, y, img1, img2):
        for j in self.span:
            for i in self.span:
                if self.colors_in_range(img1[y-j,x-i,:], img2):
                    return True
        return False

    def colors_in_range(self, RGB1, RGB2):
        #if np.sum(RGB1 - RGB2) < 75:
        if np.abs(RGB1[0]-100)>0:
            return True
        return False

class MeshLoaderToList:
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.indices_length=[]
        self.mesh_count = None
        self.matrix_code_location = None
        self.load()

    def load(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                data = json.load(f,object_pairs_hook=OrderedDict)
                self.meshes_dict = data['Meshes']
                self.span = data['span']
                self.Xres = data['Xres']
                self.Yres = data['Yres']
                self.matrix_code_location = data['Data matrix']
                #self.data_matrix_location = data["Data matrix"]
                self.construct_mask_array()
        else:
            module_logger.error("Mesh file does not exist")

    def construct_mask_array(self):
        mask_num = len(self.meshes_dict)
        # max 50 x 5(x,y,R,G,B) x mask_num
        self.indices = np.zeros((mask_num, 50, 5), dtype=np.uint8)
        for j in range(mask_num):
            mesh_name = str(j)
            temp_mesh = self.meshes_dict[mesh_name]
            for i in range(len(temp_mesh)):
                x = temp_mesh[i]['x']
                y = temp_mesh[i]['y']
                R = temp_mesh[i]['R']
                G = temp_mesh[i]['G']
                B = temp_mesh[i]['B']
                self.indices[j,i,:] = [x,y,R,G,B]
            self.indices_length.append(len(temp_mesh))

class MCP23017:
    IODIRA = 0x00
    IODIRB = 0x01
    GPIOA = 0x12
    GPIOB = 0x13
    OLATA = 0x14
    OLATB = 0x15

    ADDR = 0x20
    def __init__(self):
        pass

    def test_led(self):
        module_logger.debug("Starting led test in %s",__name__)

        with SMBusWrapper(1) as bus:
            # set GPIOB to output
            data = 0x00
            bus.write_byte_data(MCP23017.ADDR, MCP23017.IODIRA, data)
            time.sleep(0.05)

            # turn on every GPIOA
            for i in range(7):
                data = 0x01 << i
                bus.write_byte_data(MCP23017.ADDR, MCP23017.OLATA, data)
                time.sleep(1)
            # turn off
            data = 0x00
            bus.write_byte_data(MCP23017.ADDR, MCP23017.OLATA, data)

    def turn_heater_on(self):
        with SMBusWrapper(1) as bus:
        # set GPIOA 7 to output
            data = 0x00
            bus.write_byte_data(MCP23017.ADDR, MCP23017.IODIRA, data)
            time.sleep(0.05)

            data = 0x01 << 7
            bus.write_byte_data(MCP23017.ADDR, MCP23017.OLATA, data)
        module_logger.debug("Heater on")

    def turn_heater_off(self):
        with SMBusWrapper(1) as bus:
            # set GPIOA 7 to output
            data = 0x00
            bus.write_byte_data(MCP23017.ADDR, MCP23017.IODIRA, data)
            time.sleep(0.05)

            data = 0x00 << 7
            bus.write_byte_data(MCP23017.ADDR, MCP23017.OLATA, data)
        module_logger.debug("Heater off")


class LM75A(AbstractSensor):
    TEMP_REG = 0x00
    ID_REG = 0x07

    ADDR = 0x4b
    def __init__(self, delay: int = 1):
        super().__init__(delay, "Temperature", "°C")
        self.sensor = None

    def get_value(self):
        with SMBusWrapper(1) as bus:
            # Read a block of 2 bytes from address ADDR, offset 0
            block = bus.read_i2c_block_data(LM75A.ADDR, LM75A.TEMP_REG, 2)

        nine_biter = (block[1] >> 7 | block[0] << 1) & 0xFF
        temperatura = nine_biter / 2
        if(block[0] & 0x80) == 0x01:
            temperatura = -temperatura

        return temperatura

    def close(self):
        pass

class IRTemperatureSensor(AbstractSensor):
    MLX90615_I2C_ADDR = 0x5B
    MLX90615_REG_TEMP_AMBIENT = 0x26
    MLX90615_REG_TEMP_OBJECT = 0x27

    def __init__(self, delay: int = 1):
        super().__init__(delay, "Temperature", "°C")
        self.sensor = None

    def get_value(self):
        with SMBusWrapper(1) as bus:
            block = bus.read_i2c_block_data(IRTemperatureSensor.MLX90615_I2C_ADDR,
                                                 IRTemperatureSensor.MLX90615_REG_TEMP_OBJECT,
                                                 2)
        temperature = (block[0] | block[1] << 8) * 0.02 - 273.15
        return temperature

    def close(self):
        #self.bus.close()
        pass
