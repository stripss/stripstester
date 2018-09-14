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
from strips_tester.abstract_devices import AbstractVoltMeter, AbstractFlasher, AbstractSensor, AbstractBarCodeScanner
#from matplotlib import pyplot as pp
from collections import OrderedDict
#from smbus2 import SMBus, i2c_msg
from smbus2 import SMBusWrapper
#import wifi
import collections
from ina219 import INA219
import RPi.GPIO as GPIO
import struct

module_logger = logging.getLogger(".".join(("strips_tester", __name__)))


class Honeywell1400gHID(AbstractBarCodeScanner):
    def __init__(self, vid, pid):
        super().__init__(type(self).__name__)
        if vid==None or pid==None:
            raise 'Not anough init parameters for {}'.format(type(self).__name__)
        self.vid = vid
        self.pid = pid
        self.open_scanner()

    def open_scanner(self):
        self.device = hid.device()
        self.device.open(self.vid, self.pid)  # VendorID/ProductID

    def read_raw(self):
        # read HID report descriptor to decode and receive data
        while True:
            raw_data = self.device.read(128)
            if raw_data:
                return raw_data

    def get_dec_data(self):
        # read HID report descriptor to decode and receive data
        '''
        HID descriptor for honeywell 1400g
        byte0 | report ID=2
        byte1 | Symbology Identifier 1
        byte2 | Symbology Identifier 2
        byte3 | Symbology Identifier 3
        byte4 | Used for very large messages
        byte5-byte50 scanned data

        read until 0x00 encountered

        :return: decode string
        '''
        byte = 5
        str_data = ''
        while True:
            raw_data = self.device.read(128)
            if raw_data:
                while raw_data[byte] != 0x00:
                    #print(chr(raw_data[byte]))
                    str_data += (chr(raw_data[byte]))
                    byte += 1
                break
        return str_data

    def close_scanner(self):
        self.device.close()

class Honeywell1400:
    hid_lookup = {4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j', 14: 'k', 15: 'l', 16: 'm',
                  17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's', 23: 't', 24: 'u', 25: 'v', 26: 'w', 27: 'x', 28: 'y', 29: 'z',
                  30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0', 44: ' ', 45: '-', 46: '=',
                  47: '[', 48: ']', 49: '\\', 51: ';', 52: '\'', 53: '~', 54: ',', 55: '.', 56: '/', 81: '\n'}

    def __init__(self, vid: int, pid: int, path: str, max_code_length: int = 50):
        if path==None and (vid==None and pid==None):
            raise 'Not anough init parameters for Honeywell1400'
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
    def __init__(self, port, timeout=3.0):
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

    def __init__(self, vid: int, pid, path: str = None, initial_status=None, number_of_relays: int = 16,ribbon=False):
        self.vid = vid
        self.pid = pid
        self.path = path
        self.__WRITE_CMD = [0xC3, 0x0E, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x48, 0x49, 0x44, 0x43, 0xEE, 0x01, 0x00, 0x00]
        self.number_of_relays = number_of_relays
        self.hid_device = hid.device()
        self.logger = logging.getLogger(__name__)
        self.status = initial_status if initial_status else [False] * number_of_relays
        self.open()
        self.ribbon = ribbon

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
        #print("Relay '{}' opened.".format(relay_number))
        if 1 <= relay_number <= self.number_of_relays:
            if self.ribbon:
                relay_number = self.ribbon_cable(relay_number)
            self.status[relay_number - 1] = False
        else:
            self.logger.critical("Relay number out of bounds")
        self._write_status()
        self.logger.debug("Relay %s OPENED", relay_number)

    def close_relay(self, relay_number: int):
        #print("Relay '{}' closed.".format(relay_number))
        if self.ribbon:
            relay_number = self.ribbon_cable(relay_number)

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

    def ribbon_cable(self,relay_number):
        # return swapped pin number because of ribbon cable which invert pins

        result = (relay_number - 1) - (2 * -(relay_number % 2))

        return result


class INA219a(AbstractSensor):
    ADDR = 0x40
    SHUNT_OHMS = 0.1
    MAX_EXPECTED_AMPS = 0.2

    def __init__(self):
        self.ina = INA219(INA219a.SHUNT_OHMS, INA219a.MAX_EXPECTED_AMPS, INA219a.ADDR)
        self.ina.configure(self.ina.RANGE_16V, self.ina.GAIN_1_40MV)

    def get_voltage(self):
        with SMBusWrapper(1) as bus:
            hibyte = bus.read_byte_data(INA219a.ADDR, 0x02)
            result = (hibyte << 8) + bus.read_byte_data(INA219a.ADDR, 0x02 + 1)

        return (result >> 3) * 4

    def voltmeter(self):
        try:
            repeat = 60
            voltage = 0.0

            for x in range(0, repeat):
                voltage += self.get_voltage()

            voltage /= repeat
            voltage *= 0.001

        except Exception as ee:
            print("ERROR: {}".format(ee))

        return voltage

class YoctoVoltageMeter(AbstractSensor):
    def __init__(self, device_name, delay: int = 1):
        super().__init__(delay,"Voltage", "V")
        self.sensor = None

        errmsg = None
        if YAPI.RegisterHub("usb", errmsg) != YAPI.SUCCESS:
            module_logger.error("Can't load yocto API : %s", errmsg)
            print("poasidjaspiodj")
            raise "Can't load yocto API"

        # find voltage sensor with name: "VOLTAGE1-A08C8.voltage2"
        #sensor = YVoltage.FirstVoltage()

        self.sensor = YVoltage.FindVoltage(device_name)
        if (self.sensor == None):
            raise ("No yocto device is connected")
        m = self.sensor.get_module()
        target = m.get_serialNumber()

        module_logger.debug("Module %s found with serial number %s", m, target);
        if not (self.sensor.isOnline()):
            raise ('yocto volt is not on')
        module_logger.debug("Yocto-volt init done")


    def get_value(self):

        return self.sensor.get_currentValue()

    def close(self):
        YAPI.FreeAPI()


class CameraDevice:
    def __init__(self, Xres: int, Yres: int):
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
            self.imSaveRaw3d('/strips_tester_project/logs/Camera/Picture{}.jpg'.format(i), self.img[i,::,::,::])

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
        #tx = [0, 1, 2, -1, -2]
        #ty = [0, 1, 2, -1, -2]
        #self.Tx, self.Ty = np.meshgrid(tx,ty)
        #self.Tx = self.Tx.flatten()
        #self.Ty = self.Ty.flatten()
        ''' check only cross of pixels to speed up camera test i.e.
                    *
                    *
                * * * * *
                    *
                    *
        '''
        self.Tx, self.Ty = [0, -1, 1, -2, 2, -3, 3, -4, 4, 0, 0, 0, 0, 0, 0, 0, 0], np.multiply([0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 1, -2, 2, -3, 3, -4, 4],2)
        #self.Tx, self.Ty = [0, -1, 1, -2, 2, -3, 3, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, -1, 1, -2, 2, -3, 3] * 3
        #self.Tx, self.Ty = [0, -1, 1, -2, 2, 0, 0, 0, 0], [0, 0, 0, 0, 0, -1, 1, -2, 2]

    def run(self, images, masks, mask_indices_len, masks_length):
        images = images.astype(np.int16)
        for j in range(masks_length):
            for i in range(mask_indices_len[j]): # indices_length[j] number of indices to check
                #mask_num x 50 x 5(x,y,R,G,B)
                x = masks[j,i,0]
                y = masks[j,i,1]
                RGB = masks[j,i,2:]
                if not self.compare_check_cross(x, y, images[j,::,::], RGB):
                    module_logger.error("Failed at picture {} (x:{} y:{}) and index  {} with image RGB {} and mesh RGB {}".format(j, x, y, i, images[j,y,x], RGB))
                    return False
        return True

    def compare_forloop(self, x, y, img1, img2):
        for j in self.span:
            for i in self.span:
                if self.colors_in_range(img1[y-j,x-i,:], img2):
                    return True
        return False

    def compare_start_from_middle(self, x, y, img1, img2):
        for i in range(len(self.Tx)):
            if self.colors_in_range(img1[y - self.Ty[i], x - self.Tx[i], :], img2):
                return True
        return False

    def compare_check_cross(self, x, y, img1, img2):
        for i in range(len(self.Tx)):
            if self.colors_in_range(img1[y + self.Ty[i], x + self.Tx[i], :], img2):
                return True
        return False

    def colors_in_range(self, RGB1, RGB2):
        #if np.sum(RGB1 - RGB2) < 75:
        #if (np.abs(RGB1[0]-RGB2[0])+np.abs(RGB1[1]-RGB2[1])+np.abs(RGB1[2]-RGB2[2]))<60:
        if (np.abs(RGB1[0]-RGB2[0]))<100:
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
        self.indices = np.zeros((mask_num, 50, 5), dtype=np.int16)
        for j in range(mask_num):
            mesh_name = str(j)
            temp_mesh = self.meshes_dict[mesh_name]
            for i in range(len(temp_mesh)):
                x_loc = temp_mesh[i]['x']
                y_loc = temp_mesh[i]['y']
                R = temp_mesh[i]['R']
                G = temp_mesh[i]['G']
                B = temp_mesh[i]['B']
                self.indices[j,i,:] = [x_loc,y_loc,R,G,B]
            self.indices_length.append(len(temp_mesh))





class Arduino:
    def __init__(self,address = 0x04):
        if isinstance(address, str):
            address = int(address,16)

        self.addr = address
        self.ready = 0

        self.ping()

    def ping(self):
        try:
            self.send_command(110)
        except Exception:
            raise IOError("Device did not respond.")

    # Ping MCP23017 to see if address is valid
    def moveStepper(self,index):
        if index < 0 or index > 40:
            return

        self.send_command(100,index)

    def calibrate(self):
        self.send_command(103)

    # Available only in NanoBoard
    def probe(self,index):
        resistance = -1

        self.relay(1)  # Ohmmeter mode
        self.send_command(100,index)
        self.connect()
        resistance = self.measure()
        self.disconnect()

        return resistance

    def test_float(self):
        with SMBusWrapper(1) as bus:
            result = False

            # Try to send bytes 20 times
            for i in range(20):
                try:
                    bus.write_byte(self.addr, 200)

                    ba = bytearray(struct.pack("f", 3.66))
                    bus.write_i2c_block_data(self.addr,0,ba)

                    result = True
                    break
                except OSError:
                    time.sleep(0.1)

            if not result:
                raise Exception

            # Wait for response
            #self.wait_for_response(bus)


    # Connect probes to pogoBoard
    def connect(self):
        self.servo(1,130)

    # Disconnect probes from pogoBoard
    def disconnect(self):
        self.servo(1,60)

    def relay(self,state):
        # If state == 1 OHMMETER
        # if state == 0 VOLTMETER

        self.ready = 0

        if state < 0 or state > 1:
            return

        self.send_command(104,state)

    def servo(self,number,angle):
        # If state == 1 OHMMETER
        # if state == 0 VOLTMETER

        self.ready = 0

        if number < 1 or number > 2:
            return

        if angle < 0 or angle > 180:
            return

        self.send_command(104 + number,angle)

    def send_command(self,command,value = 10):
        # Join i2c line as master
        with SMBusWrapper(1) as bus:
            result = False

            # Try to send bytes 20 times
            for i in range(20):
                try:
                    bus.write_byte(self.addr, command)
                    bus.write_byte(self.addr, value)

                    result = True
                    break
                except OSError:
                    time.sleep(0.1)

            if not result:
                raise Exception

            # Wait for response
            self.wait_for_response(bus)

    def wait_for_response(self,bus):
        while not self.ready:
            try:
                self.ready = bus.read_byte(self.addr)
                break
            except OSError:
                time.sleep(0.1)

    '''
    def measure(self):
        self.ready = 1
        self.send_command(107)
        self.ready = 0

            while not self.ready:
                try:
                    # Read block of 4 bytes (float) via i2c
                    data = bus.read_i2c_block_data(self.addr,0x00,4)
                    print(data)
                    self.resistance = self.get_float(data,0)
                    print("Recieved float: {}".format(self.resistance))
                    self.ready = 1

                except OSError:
                    print("Read OS Error")
                    time.sleep(0.1)

    def get_float(self, data, index):
        bytes1 = data[4 * index:4 * (index + 1)]
        print("DATA: {}".format(bytes1))
        return struct.unpack('f', ''.join(map(chr, bytes1)))
    '''


class MCP23017:
    IODIRA = 0x00
    IODIRB = 0x01
    GPIOA = 0x12
    GPIOB = 0x13
    OLATA = 0x14
    OLATB = 0x15

    LEFT_BLANK = 0x00
    LEFT_RED = 0x20
    LEFT_GREEN = 0x40
    LEFT_YELLOW = 0x60

    RIGHT_BLANK = 0x00
    RIGHT_RED = 0x20
    RIGHT_GREEN = 0x40
    RIGHT_YELLOW = 0x60

    BUZZER_ON = 0x30
    BUZZER_OFF = 0x35

    def __init__(self,address = 0x20):
        if isinstance(address, str):
            address = int(address,16)

        self.addr = address
        self.ping()

    # Ping MCP23017 to see if address is valid
    def ping(self):
        try:
            with SMBusWrapper(1) as bus:
                # Set port A as output
                data = 0x00
                bus.write_byte_data(self.addr, MCP23017.IODIRA, data)
        except OSError:
            raise

    def set_led_status(self,status):
        module_logger.debug("Starting led test in %s",__name__)

        with SMBusWrapper(1) as bus:
            # 0x01 - zelena leva
            # 0x02 - rdeca leva

            # 0x04 - zelena desna
            # 0x08 - rdeca desna


            # Set port A as output
            data = 0x00
            bus.write_byte_data(self.addr, MCP23017.IODIRA, data)

            data = status
            bus.write_byte_data(self.addr, MCP23017.OLATA, data)


    def test_led(self):
        module_logger.debug("Starting led test in %s",__name__)

        with SMBusWrapper(1) as bus:
            # set GPIOB to output
            data = 0x00
            bus.write_byte_data(self.addr, MCP23017.IODIRA, data)
            time.sleep(0.05)

            for i in range(4):
                data = 0x01 << i
                bus.write_byte_data(self.addr, MCP23017.OLATA, data)
                time.sleep(1)

            # turn off
            data = 0x00
            bus.write_byte_data(self.addr, MCP23017.OLATA, data)




    def test_one_led(self,lednum):
        self.lednum = lednum
        module_logger.debug("Starting led test in %s",__name__)

        with SMBusWrapper(1) as bus:
            # set GPIOB to output
            data = 0x00
            bus.write_byte_data(self.addr, MCP23017.IODIRA, data)
            time.sleep(0.05)

            data = 0x01 << lednum
            bus.write_byte_data(self.addr, MCP23017.OLATA, data)
            time.sleep(0.05)

            # turn off
            #data = 0x00
            #bus.write_byte_data(MCP23017.ADDR, MCP23017.OLATA, data)

    def manual_off(self):
        with SMBusWrapper(1) as bus:
            data = 0x00
            bus.write_byte_data(self.addr, MCP23017.OLATA, data)


    def turn_heater_on(self):
        with SMBusWrapper(1) as bus:
        # set GPIOA 7 to output
            data = 0x00
            bus.write_byte_data(self.addr, MCP23017.IODIRA, data)
            time.sleep(0.05)

            data = 0x01 << 7
            bus.write_byte_data(self.addr, MCP23017.OLATA, data)
        module_logger.debug("Heater on")

    def turn_heater_off(self):
        with SMBusWrapper(1) as bus:
            # set GPIOA 7 to output
            data = 0x00
            bus.write_byte_data(self.addr, MCP23017.IODIRA, data)
            time.sleep(0.05)

            data = 0x00 << 7
            bus.write_byte_data(self.addr, MCP23017.OLATA, data)
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

    def __init__(self, delay: int):
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


class Wifi:
    '''
    Dependency on wifi
    Saved configuration for connecting to a wireless network.  This
    class provides a Python interface to the /etc/network/interfaces
    file.
        example for open network:
        network={
            ssid="GARO-MELN-2e8e6e"
            key_mgmt=NONE
        }
    '''
    interfaces = '/etc/wpa_supplicant/wpa_supplicant.conf'
    head = 'ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n'
    head += 'update_config=1\n'
    head += 'country=GB\n\n'


    def __init__(self, interface):
        self.iface = interface
        self.network = collections.OrderedDict()

    def __str__(self):
        '''
        Returns the representation of a scheme that you would need
        in the /etc/wpa_supplicant/wpa_supplicant.conf' file.
        '''
        scheme_str = ''
        scheme_str += 'network={\n'
        for k, v in self.network.items():
            scheme_str += "\t{}={}\n".format(k, v)
        scheme_str += '}\n'
        return scheme_str


    def format_file(self, network_dict):
        str_config = ''
        str_config += Wifi.head
        str_config += 'network={\n'
        for k, v in network_dict.items():
            str_config += "{}={}\n".format(k, v)
        str_config += '}\n'
        return str_config

    def save(self, ssid, psk, encryption_type = 'WPA2-PSK', options = None):
        if psk == '':
            self.network['ssid'] = '"' + ssid + '"'
            self.network['key_mgmt'] = 'NONE'
        else:
            self.network['ssid'] = '"' + ssid + '"'
            self.network['psk'] = '"' + psk + '"'
            # network['key_mgmt'] = self.encryption_type.upper()

        if_file = open(Wifi.interfaces, 'w')
        if_file.write(self.format_file(self.network))

    def activate(self):
        module_logger.debug(os.system('sudo ifup {}'.format(self.iface)))

    @staticmethod
    def search():
        wifilist = []
        cells = wifi.Cell.all('self.iface')
        for cell in cells:
            wifilist.append(cell)
        return wifilist

    @staticmethod
    def find_from_wifi_list(ssid):
        wifilist = Wifi.search()
        for cell in wifilist:
            if cell.ssid == ssid:
                return cell
        return False
