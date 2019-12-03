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
import time
import json
import picamera
from picamera import PiCamera
import cv2

sys.path += [os.path.dirname(os.path.dirname(os.path.realpath(__file__))), ]
from strips_tester import *
from yoctopuce.yocto_api import *
from yoctopuce.yocto_voltage import *
from yoctopuce.yocto_weighscale import *
from yoctopuce.yocto_genericsensor import *

from strips_tester.abstract_devices import AbstractVoltMeter, AbstractFlasher, AbstractSensor, AbstractBarCodeScanner
from collections import OrderedDict
import collections
import RPi.GPIO as GPIO
import struct
from smbus2 import SMBusWrapper
import ina219
import subprocess
import io
from binascii import unhexlify
import base64
import colorsys
from strips_tester import stm32loader

module_logger = logging.getLogger(".".join(("strips_tester", "devices")))


class Honeywell1400gHID(AbstractBarCodeScanner):
    hid_lookup = {4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j', 14: 'k', 15: 'l', 16: 'm',
                  17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's', 23: 't', 24: 'u', 25: 'v', 26: 'w', 27: 'x', 28: 'y', 29: 'z',
                  30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0', 44: ' ', 45: '-', 46: '=',
                  47: '[', 48: ']', 49: '\\', 51: ';', 52: '\'', 53: '~', 54: ',', 55: '.', 56: '/', 81: '\n'}

    def __init__(self, vid, pid):
        super().__init__(type(self).__name__)
        if vid == None or pid == None:
            raise 'Not anough init parameters for {}'.format(type(self).__name__)
        self.vid = vid
        self.pid = pid
        self.found = False
        self.open_scanner()

    def open_scanner(self):
        self.device = hid.device()
        self.device.open(self.vid, self.pid)  # VendorID/ProductID
        self.found = True

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
        i = 0
        while True:
            i += 1
            raw_data = self.device.read(8)  # Read buffer from scanner

            if raw_data:
                print(i, end="")

                print(raw_data)


                '''
                while raw_data[byte] != 0x00:
                    print(chr(raw_data[byte]))
                    str_data += (chr(raw_data[byte]))
                    byte += 1
                break
                '''
        return str_data

    def close(self):
        self.device.close()


class Honeywell1400:
    hid_lookup = {4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j', 14: 'k', 15: 'l', 16: 'm',
                  17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's', 23: 't', 24: 'u', 25: 'v', 26: 'w', 27: 'x', 28: 'y', 29: 'z',
                  30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0', 44: ' ', 45: '-', 46: '=',
                  47: '[', 48: ']', 49: '\\', 51: ';', 52: '\'', 53: '~', 54: ',', 55: '.', 56: '/', 81: '\n'}

    def __init__(self, vid=None, pid=None, path="/dev/hidraw0", max_code_length: int = 50):
        if path is None and (vid is None and pid is None):
            raise "Not anough init parameters for Honeywell1400"

        self.found = False
        self.vid = vid
        self.pid = pid
        self.path = path
        self.max_code_length = max_code_length

        self.device = hid.device()
        self.device.open(self.vid, self.pid)  # VendorID/ProductID

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



class Honeywell_1900HID:
    '''
        Honeywell scanner driver, configured as HID. Made by Marcel Jancar 7.10.2019
        May add flush_input in the future and timeout function if needed.
    '''

    hid = {4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j', 14: 'k', 15: 'l', 16: 'm',
           17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's', 23: 't', 24: 'u', 25: 'v', 26: 'w', 27: 'x', 28: 'y',
           29: 'z', 30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0', 44: ' ',
           45: '-', 46: '=', 47: '[', 48: ']', 49: '\\', 51: ';', 52: '\'', 53: '~', 54: ',', 55: '.', 56: '/'}

    hid2 = {4: 'A', 5: 'B', 6: 'C', 7: 'D', 8: 'E', 9: 'F', 10: 'G', 11: 'H', 12: 'I', 13: 'J', 14: 'K', 15: 'L', 16: 'M',
            17: 'N', 18: 'O', 19: 'P', 20: 'Q', 21: 'R', 22: 'S', 23: 'T', 24: 'U', 25: 'V', 26: 'W', 27: 'X', 28: 'Y',
            29: 'Z', 30: '!', 31: '@', 32: '#', 33: '$', 34: '%', 35: '^', 36: '&', 37: '*', 38: '(', 39: ')', 44: ' ',
            45: '_', 46: '+', 47: '{', 48: '}', 49: '|', 51: ':', 52: '"', 53: '~', 54: '<', 55: '>', 56: '?'}

    def __init__(self, vid=None, pid=None):
        self.vid = vid
        self.pid = pid
        self.found = False

        # Create new instande of HID device
        self.device = hid.device()

        # Try to connect to device using VID and PID
        try:
            self.device.open(self.vid, self.pid)  # VendorID/ProductID
            self.found = True
        except Exception:
            pass

        if not self.found:
            module_logger.error("Honeywell device not found")

    # Read barcode data until carriage return is found
    def read(self):
        print("Waiting code to be scanned...")

        result = ""

        while True:
            ## Get the character from the HID
            buffer = self.device.read(8)

            if buffer[2] > 0:
                ##  40 is carriage return which signifies
                ##  we are done looking for characters
                if int(buffer[2]) == 40:
                    break

                if int(buffer[0]) == 2:
                    result += self.hid2[int(buffer[2])]
                else:
                    result += self.hid[int(buffer[2])]

        return result

    # Close scanner device
    def close(self):
        self.device.close()


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

    def __init__(self, port='/dev/ttyUSB0', retries=5, timeout=3.0):
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
            xonxoff=False)
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


class Godex:
    '''
        Driver for Godex thermal printers. Performs like writing to file. Every line must be terminated with \n.
        Does not need USB to RS232 converter. Made by Marcel Jancar 08.05.2019
    '''

    INTERFACE_AUTOSELECT = 0
    INTERFACE_SERIAL = 1
    INTERFACE_USB = 2

    # Initialisation of printer port
    def __init__(self, port_usb='/dev/usb/lp0', port_serial='/dev/ttyUSB0', timeout=3.0, interface=0):
        self.interface = interface  # 0 - autoselect, 1 - serial, 2 - usb
        self.port_usb = port_usb
        self.port_serial = port_serial
        self.timeout = timeout
        self.found = False

        if not self.interface:  # Autoselect
            for retry in range(10):
                if self.set_serial():  # Check if serial available
                    self.interface = 1
                    self.found = True
                    break

            if not self.interface:  # Serial port not detected
                if self.set_usb():
                    self.interface = 2  # Using USB from now on
                    self.found = True

        elif self.interface == 1:
            for retry in range(10):
                if self.set_serial():
                    self.found = True
                    break
        else:
            if self.set_usb():
                self.found = True

        if not self.found:
            module_logger.error("Godex device not found")

    def set_usb(self):
        if os.path.exists(self.port_usb):
            return True
        else:
            return False

    def set_serial(self):
        try:
            self.ser = serial.Serial(
                port=self.port_serial,
                baudrate=9600,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=self.timeout,
                dsrdtr=False,
                rtscts=False,
                xonxoff=False, )

            self.found = True
            self.ser.dtr = True
            self.ser.rts = False
            self.ser.flushOutput()
            self.ser.flushInput()
            return True

        except Exception as ee:
            return False

    def load_label(self, filename):
        string = ''

        if not os.path.isfile(filename):
            return print("Label {} does not exist!" . format(filename))

        with open(filename) as file:
            for line in file:
                string += line

        return string

    # Command for actual printing.
    def send_to_printer(self, string):
        if self.interface == 2:
            with open(self.port_usb, 'w') as lpt:
                lpt.write(string)
        elif self.interface == 1:
            self.ser.write(string.encode(encoding="ascii"))

    def close(self):
        if self.interface == 1 and self.found:
            try:
                self.ser.close()  # Close serial port
            except Exception as e:
                module_logger.error("Cannot close Godex device ({})." . format(e))

class SainBoard16:
    # define command messages
    is_open = False
    hid_device = None
    OPEN_CMD = (0xD2, 0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x48, 0x49, 0x44, 0x43, 0x80, 0x02, 0x00, 0x00)
    CLOSE_CMD = (0x71, 0x0E, 0x71, 0x00, 0x00, 0x00, 0x11, 0x11, 0x00, 0x00, 0x48, 0x49, 0x44, 0x43, 0x2A, 0x02, 0x00, 0x00)

    def __init__(self, vid: int, pid, path: str = None, initial_status=None, number_of_relays: int = 16, ribbon=False):
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
        # print("Relay '{}' opened.".format(relay_number))
        if 1 <= relay_number <= self.number_of_relays:
            if self.ribbon:
                relay_number = self.ribbon_cable(relay_number)
            self.status[relay_number - 1] = False
        else:
            self.logger.critical("Relay number out of bounds")
        self._write_status()
        self.logger.debug("Relay %s OPENED", relay_number)

    def close_relay(self, relay_number: int):
        # print("Relay '{}' closed.".format(relay_number))
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

    def ribbon_cable(self, relay_number):
        # return swapped pin number because of ribbon cable which invert pins

        result = (relay_number - 1) - (2 * -(relay_number % 2))

        return result


# Driver for voltmeter or ammeter INA219. Made by Marcel Jancar
class INA219:
    def __init__(self):  # Initialize sensor with 0.1 resistor
        self.ina = ina219.INA219(0.1)

    def voltage(self, repeat=10):
        voltage = 0.0

        for x in range(0, repeat):
            voltage += self.ina.voltage()

        voltage /= repeat

        return round(voltage,2)


class TI74HC595:
    def __init__(self, datapin, latchpin, clockpin, oepin):
        self.datapin = datapin
        self.latchpin = latchpin
        self.clockpin = clockpin
        self.oepin = oepin

        self.dataa = []

        for i in range(48):
            self.dataa.append(0)

        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)

        GPIO.setup(self.datapin, GPIO.OUT)
        GPIO.setup(self.latchpin, GPIO.OUT)
        GPIO.setup(self.clockpin, GPIO.OUT)
        GPIO.setup(self.oepin, GPIO.OUT)

    def reset(self):
        for bit in range(48):
            self.dataa[bit] = 0

        # print("RST", end='')
        self.invertShiftOut()

    def writeraw(self, raw):
        for i in range(48):
            self.dataa[bit] = raw[i]

        # print("RAW", end='')
        self.invertShiftOut()

    def set(self, position, state):
        if position[0] == 'K':
            series = 0
        elif position[0] == 'M':
            series = 1
        elif position[0] == 'L':
            series = 2
        else:
            raise Exception("Unknown series on relay board.")
            return

        ordered = [1, 3, 5, 7, 9, 11, 13, 15, 16, 14, 12, 10, 8, 6, 4, 2]
        index = series * 16 + ordered.index(int(position[1:]))

        # index = - (2 * -(index % 2))
        self.dataa[index] = state * 1

        # self.invertShiftOut()
        return

    def invertShiftOut(self):  # Data is 48-bit number

        for bit in range(48):
            # print(self.data[bit], end='')
            GPIO.output(self.datapin, self.dataa[bit])
            GPIO.output(self.clockpin, GPIO.HIGH)
            GPIO.output(self.clockpin, GPIO.LOW)

        GPIO.output(self.latchpin, GPIO.HIGH)
        GPIO.output(self.latchpin, GPIO.LOW)

        GPIO.output(self.oepin, GPIO.HIGH)

        return


class HEF4094BT:
    def __init__(self, datapin, latchpin, clockpin, oepin, checkpin=12):
        self.datapin = datapin
        self.latchpin = latchpin
        self.clockpin = clockpin
        self.oepin = oepin
        self.delay = 0.00001
        self.checkpin = checkpin
        self.data = []
        self.checkstate = []

        for i in range(48):
            self.data.append(0)

        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)

        GPIO.setup(self.datapin, GPIO.OUT)
        GPIO.setup(self.latchpin, GPIO.OUT)
        GPIO.setup(self.clockpin, GPIO.OUT)
        GPIO.setup(self.oepin, GPIO.OUT) # maybe pullup

    def reset(self):
        for bit in range(48):
            self.data[bit] = 0

        self.invertShiftOut()

    def set(self, position, state):
        if position[0] == 'K':
            series = 0
        elif position[0] == 'L':
            series = 1
        elif position[0] == 'M':
            series = 2
        else:
            raise Exception("Unknown series on relay board.")
            return

        ordered = [7,5,3,1,9,11,13,15,10,12,14,16,8,6,4,2]
        index = series * 16 + ordered.index(int(position[1:]))

        # index = - (2 * -(index % 2))
        self.data[index] = state * 1

        # self.invertShiftOut()
        return

    def invertShiftOut(self):  # Data is 48-bit number
        GPIO.output(self.latchpin, GPIO.HIGH)
        time.sleep(self.delay)

        # output 101
        GPIO.output(self.datapin, GPIO.LOW)
        time.sleep(self.delay)
        self.clock_shift()
        GPIO.output(self.datapin, GPIO.HIGH)
        time.sleep(self.delay)
        self.clock_shift()
        GPIO.output(self.datapin, GPIO.LOW)
        time.sleep(self.delay)
        self.clock_shift()


        for bit in range(48):
            #print(self.data[bit], end='')
            GPIO.output(self.datapin, self.data[bit])
            time.sleep(self.delay)

            if bit > 44:
                state = GPIO.input(self.checkpin)
                #print(state, end="")
                self.checkstate.append(state)

            self.clock_shift()

        GPIO.output(self.latchpin, GPIO.LOW)
        time.sleep(self.delay)
        GPIO.output(self.oepin, GPIO.LOW)
        time.sleep(self.delay)
        GPIO.output(self.datapin, GPIO.HIGH)

        if self.checkstate != [1, 0, 1]:
            module_logger.error("Shifter data not consistent!")

        self.checkstate = []

        '''
        # Debug purpose
        for bit in range(48):
            if self.data[bit]:
                series = int(bit / 16)

                if series == 0:
                    series_str = 'K'
                elif series == 1:
                    series_str = 'L'
                elif series == 2:
                    series_str = 'M'

                idx = bit - series * 16

                ordered = [7, 5, 3, 1, 9, 11, 13, 15, 10, 12, 14, 16, 8, 6, 4, 2]
                idx_real = ordered[idx]
                print("{}{}, ".format(series_str, idx_real), end='')
        print("")
        '''

        return

    def clock_shift(self):
        GPIO.output(self.clockpin, GPIO.LOW)
        time.sleep(self.delay)
        GPIO.output(self.clockpin, GPIO.HIGH)
        time.sleep(self.delay)


    def shiftout(byte):
        GPIO.output(gpios['LATCH'], 0)

        for x in range(8):
            GPIO.output(gpios['DATA'], (byte >> x) & 1)
            GPIO.output(gpios['CLOCK'], 1)
            GPIO.output(gpios['CLOCK'], 0)

        GPIO.output(gpios['LATCH'], 1)


# Yocto Library - must execute for each sensor available. Made by Marcel Jancar 4.11.2019
class Yocto:
    def __init__(self, device_name, delay = 0.16):
        self.sensor = None
        self.found = True
        self.delay = delay

        errmsg = None
        if YAPI.RegisterHub("usb", errmsg) != YAPI.SUCCESS:
            module_logger.error("Cannot load Yocto API! %s", errmsg)
            self.found = False
            return

        try:
            # Initialize sensor (more common than YVoltage)
            self.sensor = YSensor.FindSensor(device_name)
            self.sensor.set_resolution(0.01)

        except YAPI.YAPI_Exception:
            self.found = False
            return

    def get_name(self):
        module = self.sensor.get_module()
        target = module.get_serialNumber()
        return target

    def read(self):
        time.sleep(self.delay)  # Sleep before taking measurement
        return self.sensor.get_currentValue()

    def get_highest_value(self):
        time.sleep(self.delay)  # Sleep before taking measurement
        return self.sensor.get_highestValue()

    def close(self):
        YAPI.FreeAPI()


class YoctoVoltageMeter(AbstractSensor):
    def __init__(self, device_name, delay: int = 1):
        super().__init__(delay, "Voltage", "V")
        self.sensor = None
        self.found = True

        errmsg = None
        if YAPI.RegisterHub("usb", errmsg) != YAPI.SUCCESS:
            module_logger.error("Can't load yocto API : %s", errmsg)
            self.found = False
            return

        try:
            # Initialize sensor (more common than YVoltage)
            self.sensor = YSensor.FindSensor(device_name)
            self.sensor.set_resolution(0.01)
        except YAPI.YAPI_Exception:
            self.found = False
            return

        # module_logger.debug("Module %s found with serial number %s", m, target);
        if not (self.sensor.isOnline()):
            raise ('yocto volt is not on')

    def get_name(self):
        self.m = self.sensor.get_module()
        target = self.m.get_serialNumber()
        #print(target)
        return target

        # if not (self.sensor2.isOnline()):
        # raise ('yocto volt2 is not on')
        # module_logger.debug("Yocto-volt init done")

    def get_value(self):
        while not (self.sensor.isOnline()):
            time.sleep(0.1)
            print("YoctoVolt not found... Retrying...")

        return self.sensor.get_currentValue()

    def close(self):
        YAPI.FreeAPI()

class YoctoBridge:
    def __init__(self, device_name, delay=1):
        self.sensor = None
        self.found = True
        self.delay = delay

        errmsg = None
        if YAPI.RegisterHub("usb", errmsg) != YAPI.SUCCESS:
            print("YoctoBridge did not load correctly.")
            self.found = False
            return

        try:
            # Initialize sensor (more common than YVoltage)
            self.sensor1 = YWeighScale.FindWeighScale(device_name)
            self.sensor1.set_zeroTracking(0)
            self.sensor1.set_excitation(YWeighScale.EXCITATION_AC)

            self.sensor = YSensor.FindSensor(device_name)
            module = self.sensor.module()
            serial = module.get_serialNumber()
            self.sensor = YGenericSensor.FindGenericSensor(serial+".genericSensor1")

            self.sensor.set_signalSampling(1)  # Sample as HIGH RATE FILTERED
        except YAPI.YAPI_Exception as err:
            self.found = False
            print("YAPI Error: {}" . format(err))
            return


        # module_logger.debug("Module %s found with serial number %s", m, target);
        if not (self.sensor.isOnline()):
            raise ('yocto bridge is not on')

    def set_excitation(self, mode):
        self.sensor1.set_excitation(mode)
        print("Excitation set - {}" . format(mode))

    def get_name(self):
        self.m = self.sensor.get_module()
        target = self.m.get_serialNumber()
        #print(target)
        return target

        # if not (self.sensor2.isOnline()):
        # raise ('yocto volt2 is not on')
        # module_logger.debug("Yocto-volt init done")

    def get_value(self):
        time.sleep(self.delay)
        return self.sensor.get_currentValue()

    def get_signal_value(self):
        time.sleep(self.delay)
        while not (self.sensor.isOnline()):
            time.sleep(0.1)
            print("YoctoBridge not found... Retrying...")
        return self.sensor.get_signalValue()

    def set_signal_range(self, rangeFrom, rangeTo):
        self.sensor.set_signalRange('{f}...{t}' . format(f=rangeFrom,t=rangeTo))
        print("range set to {}". format(self.sensor.get_signalRange()))

    def get_resistance(self):
        sig = self.get_signal_value()

        maxsig = 1000000
        ref = 218000

        if sig < 0.99 * maxsig:
            res = round((ref * 2000.0 * sig / (1000000 - sig)) / 1000)
        else:
            res = -1
        #print(res)
        return res

    def get_highest_value(self):
        return self.sensor.get_highestValue()

    def close(self):
        YAPI.FreeAPI()

class CameraDevice:
    def __init__(self, Xres: int, Yres: int):
        self.Xres = Xres
        self.Yres = Yres
        self.img_count = 0
        # max 20 pictures
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
            self.camera.iso = 1  # change accordingly
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
        self.camera.capture(self.img[self.img_count, ::, ::, ::], 'rgb', use_video_port=True)
        self.img_count += 1

    def take_one_picture(self):
        self.take_picture()
        return self.img[self.img_count - 1, ::, ::, ::]

    def get_picture(self, Idx=0):
        return self.img[Idx, ::, ::, ::]

    def take_img_to_array_RGB(self, xres=128, yres=80, RGB=0):
        slika = np.empty([xres, yres, 3], dtype=np.uint8)
        self.camera.capture(slika, 'rgb')
        return slika[:, :, RGB]

    def take_img_to_file(self, file_path):
        time.sleep(1)
        self.camera.capture(file_path)

    def save_all_imgs_to_file(self, qr=""):
        cas = time.time()

        for i in range(self.img_count):
            self.imSaveRaw3d('/strips_tester_project/logs/Camera/{}_{}_Picture{}.jpg'.format(cas, qr, i), self.img[i, ::, ::, ::])

    def imSaveRaw3d(self, fid, data):
        data.tofile(fid)







class RPICamera:
    def __init__(self):
        self.camera_device = PiCamera()
        self.camera_device.resolution = (640, 480)
        self.last_image = None
        #self.camera_device.start_preview()
        self.stream = io.BytesIO()
        self.camera_device.framerate = 30  # 10 frames per second

        time.sleep(1)
        for i in range(3):
            self.get_image()

    def get_image(self):
        self.last_image = np.empty((480, 640, 3), dtype=np.uint8)

        for i in range(3):
            self.camera_device.capture(self.last_image, 'bgr', use_video_port=True)

        #data = np.fromstring(self.stream.getvalue(), dtype=np.uint8)
        #self.last_image = cv2.imdecode(data, 1)  # Make OpenCV image from RAW
        #self.stream.seek(0)
        #self.stream.truncate()
        #self.last_image = self.last_image[:, :, ::-1]  # Set BGR to RGB
        #cv2.imwrite(settings.test_dir + "/mask/img.raw", self.last_image)
        return self.last_image

    def crop_image(self,x,y,width,height):
        self.last_image = self.last_image[y:y+height,x:x+width]

    def close(self):
        self.stream.seek(0)
        self.stream.truncate()
        #self.camera_device.stop_preview()
        self.camera_device.close()

# Algorithms
##################################################################################################################
class CompareAlgorithm:
    def __init__(self, span: int = 2):
        '''
        :param span: area on each size of index to check
        '''
        self.span = np.arange(-span, span)
        self.color_edge = 0.2 * 3 * 255
        # tx = [0, 1, 2, -1, -2]
        # ty = [0, 1, 2, -1, -2]
        # self.Tx, self.Ty = np.meshgrid(tx,ty)
        # self.Tx = self.Tx.flatten()
        # self.Ty = self.Ty.flatten()
        ''' check only cross of pixels to speed up camera test i.e.
                    *
                    *
                * * * * *
                    *
                    *
        '''
        self.Tx, self.Ty = [0, -1, 1, -2, 2, -3, 3, -4, 4, 0, 0, 0, 0, 0, 0, 0, 0], np.multiply([0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 1, -2, 2, -3, 3, -4, 4], 2)
        # self.Tx, self.Ty = [0, -1, 1, -2, 2, -3, 3, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, -1, 1, -2, 2, -3, 3] * 3
        # self.Tx, self.Ty = [0, -1, 1, -2, 2, 0, 0, 0, 0], [0, 0, 0, 0, 0, -1, 1, -2, 2]

    def run(self, images, masks, mask_indices_len, masks_length):
        images = images.astype(np.int16)
        for j in range(masks_length):
            for i in range(mask_indices_len[j]):  # indices_length[j] number of indices to check
                # mask_num x 50 x 5(x,y,R,G,B)
                x = masks[j, i, 0]
                y = masks[j, i, 1]
                RGB = masks[j, i, 2:]
                if not self.compare_check_cross(x, y, images[j, ::, ::], RGB):
                    module_logger.error("Failed at picture {} (x:{} y:{}) and index  {} with image RGB {} and mesh RGB {}".format(j, x, y, i, images[j, y, x], RGB))
                    return False
        return True

    def compare_forloop(self, x, y, img1, img2):
        for j in self.span:
            for i in self.span:
                if self.colors_in_range(img1[y - j, x - i, :], img2):
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
        # if np.sum(RGB1 - RGB2) < 75:
        # if (np.abs(RGB1[0]-RGB2[0])+np.abs(RGB1[1]-RGB2[1])+np.abs(RGB1[2]-RGB2[2]))<60:
        if (np.abs(RGB1[0] - RGB2[0])) < 100:
            return True
        return False



class ArduinoSerial:
    def __init__(self, port='/dev/ttyACM0', baudrate=9600, timeout=0.2, mode="ascii"):
        self.found = False
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.mode = mode

        for retry in range(10):
            if self.set_serial():  # Check if serial available

                self.found = True
                break

        if not self.found:
            module_logger.error("ArduinoSerial device not found")

    def set_serial(self):
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=self.timeout
            )

            self.ser.flushOutput()
            self.ser.flushInput()
            return True

        except Exception:
            return False

    def write(self, command, timeout=0, response="ok", append="\r\n", wait=0, retry=1):
        if not self.found:
            return
        string = command + append

        self.ser.flushInput()

        for i in range(retry):
            if self.mode == "ascii":
                self.ser.write(string.encode())
            elif self.mode == "hex":
                self.ser.write(unhexlify(string))

            time.sleep(wait)  # serial wait for answer

            if response is not None:
                if self.wait_for_response(timeout, response):
                    return True
                else:
                    module_logger.debug("wait_for_response timeout")

        if response is None:
            return True

        return False

    def wait_for_response(self, timeout, resp, return_resp=False):
        start = datetime.datetime.now()

        while True:
            if timeout:
                end = datetime.datetime.now()

                if end > start + datetime.timedelta(seconds=timeout):
                    return False

            response = self.ser.readline()
            if self.mode == "hex":
                response = response.hex()
            else:
                response = str(response)

            #print("Arduino: {}".format(response))

            if return_resp:
                return response
            else:
                if resp.lower() in response.lower():
                    return True

    def close(self):
        self.ser.close()


class Segger:
    def __init__(self, port='/dev/ttyUSB1', retries=5, timeout=3.0):
        try:
            # Segger serial communication configuration
            self.ser = serial.Serial(
                port=port,
                baudrate=9600,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=timeout
            )

        except Exception:
            raise

    def status(self):
        reply = self.send_command("STATUS")

        if 'STATUS:READY' in reply:
            return True
        else:
            return False

    def select_file(self, file):
        # Both flashing files are uploaded to:
        #   S001.dat
        #   S001.cfg

        #   S002.dat
        #   S002.cfg

        # we need just to replace Flasher.ini file
        # To do that, we use SELECT command (see 5.3.4 in segger user guide)

        self.send_command("SELECT {}".format(file))

        return

    # Get response from Segger programmer
    def get_response(self):
        out = ''

        while self.ser.inWaiting():
            out += (self.ser.read(size=1)).decode()

        result = out.split("#")
        result = [x.replace("\r\n", "") for x in result]
        result.pop(0)

        return result

    # Get response from Segger programmer via RS232
    def send_command(self, cmd):
        cmd = '#' + cmd + '\r'
        # eliminate OK from SELECT command
        self.ser.write(cmd.encode("ascii"))

        # Sleep for half a second to send serial commands and get answer
        time.sleep(0.5)

        response = self.get_response()
        return response

    def download(self):
        result = False

        for i in range(10):
            response = self.send_command("AUTO NOINFO")

            for i in response:
                print(i)

                if "OK" in i:
                    result = True
                    break

                if "ERR255" in response:  # Flashing failed
                    result = False
                    print("File not found on Segger!")
                    break

            # Break from loop if we succeed flashing
            if result:
                break

        return result

    def close(self):
        self.ser.close()


class MCP23017:
    IODIRA = 0x00
    IODIRB = 0x01
    GPIOA = 0x12
    GPIOB = 0x13
    OLATA = 0x14
    OLATB = 0x15

    LEFT_RED = 0x08
    LEFT_GREEN = 0x10
    LEFT_YELLOW = 0x18

    RIGHT_RED = 0x02
    RIGHT_GREEN = 0x04
    RIGHT_YELLOW = 0x06

    BUZZER = 0x01

    def __init__(self, address=0x20):
        if isinstance(address, str):
            address = int(address, 16)

        self.addr = address
        self.ping()
        self.current_mask = 0x00

    # Ping MCP23017 to see if address is valid
    def ping(self):
        try:
            with SMBusWrapper(1) as bus:
                # Set port A as output
                data = 0x00
                bus.write_byte_data(self.addr, MCP23017.IODIRA, data)
        except OSError:
            raise

    def set_led_status(self, status):
        module_logger.debug("Starting led test in %s", __name__)

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
        module_logger.debug("Starting led test in %s", __name__)

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

    def test_one_led(self, lednum):
        with SMBusWrapper(1) as bus:
            # set GPIOB to output
            data = 0x00
            bus.write_byte_data(self.addr, MCP23017.IODIRA, data)
            time.sleep(0.05)

            data = 0x01 << lednum
            bus.write_byte_data(self.addr, MCP23017.OLATA, data)
            time.sleep(0.05)

            # turn off
            # data = 0x00
            # bus.write_byte_data(MCP23017.ADDR, MCP23017.OLATA, data)

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

    def turn_heater_off(self):
        with SMBusWrapper(1) as bus:
            # set GPIOA 7 to output
            data = 0x00
            bus.write_byte_data(self.addr, MCP23017.IODIRA, data)
            time.sleep(0.05)

            data = 0x00 << 7
            bus.write_byte_data(self.addr, MCP23017.OLATA, data)

    def apply_mask(self):
        with SMBusWrapper(1) as bus:
            try:
                # set GPIOB to output
                data = 0x00
                bus.write_byte_data(self.addr, MCP23017.IODIRA, data)
                bus.write_byte_data(self.addr, MCP23017.OLATA, self.current_mask)
            except OSError as err:
                time.sleep(0.1)
                print("IO Error MCP23017! {}".format(err))

    def set_bit(self, mask):
        self.current_mask = self.current_mask | mask
        self.apply_mask()
        return

    def clear_bit(self, mask):
        self.current_mask = self.current_mask & ~mask
        self.apply_mask()
        return


class LM75A(AbstractSensor):
    TEMP_REG = 0x00
    ID_REG = 0x07

    ADDR = 0x4b

    def __init__(self, delay: int = 1):
        super().__init__(delay, "Temperature", "Â°C")
        self.sensor = None

    def get_value(self):
        with SMBusWrapper(1) as bus:
            # Read a block of 2 bytes from address ADDR, offset 0
            block = bus.read_i2c_block_data(LM75A.ADDR, LM75A.TEMP_REG, 2)

        nine_biter = (block[1] >> 7 | block[0] << 1) & 0xFF
        temperatura = nine_biter / 2
        if (block[0] & 0x80) == 0x01:
            temperatura = -temperatura

        return temperatura

    def close(self):
        pass


class IRTemperatureSensor(AbstractSensor):
    MLX90615_I2C_ADDR = 0x5B
    MLX90615_REG_TEMP_AMBIENT = 0x26
    MLX90615_REG_TEMP_OBJECT = 0x27

    def __init__(self, delay: int):
        super().__init__(delay, "Temperature", "Â°C")
        self.sensor = None

    def get_value(self):
        with SMBusWrapper(1) as bus:
            block = bus.read_i2c_block_data(IRTemperatureSensor.MLX90615_I2C_ADDR,
                                            IRTemperatureSensor.MLX90615_REG_TEMP_OBJECT,
                                            2)
        temperature = (block[0] | block[1] << 8) * 0.02 - 273.15
        return temperature

    def close(self):
        # self.bus.close()
        pass



# Visual algoritm for detecting LED statuses, 8-segment displays... Made by Marcel Jancar
class Visual:
    def __init__(self):
        self.mask = []
        self.image = None
        self.selected = 0
        self.option_selected = 0
        self.option_list = ['h1','s1','v1','h2','s2','v2']
        self.option_command = 0
        self.mask_offset_x = 0
        self.mask_offset_y = 0
        self.error = []

    # Not tested yet
    def load_image(self, filename):
        if os.path.isfile(filename):
            self.image = cv2.imread(filename)
            self.camera = False
        else:
            print("File '{}' does not exist" . format(filename))

    # Working OK
    def set_image(self, image):
        self.image = image.copy()

    def load_mask(self, filename):

        try:
            input_file = open(filename)
            json_array = json.load(input_file)

            for point in json_array:
                self.mask.append([])

                for point1 in point:
                    self.mask[-1].append(point1)

        except FileNotFoundError:
            pass

    # Use this function if you want to check every point defined in mask. This function returns bool or matching percent
    def compare_mask(self, mask_num):
        if self.image is None:
            return

        # Check every mask
        # Check every vertex of current mask

        for subindex in range(len(self.mask)):  # Loop through masks
            for index in range(len(self.mask[subindex])):
                if not self.detect_point_state(subindex, index):
                    if subindex == mask_num:  # Current vertex must be disabled
                        self.error.append((self.mask[subindex][index]['x'],self.mask[subindex][index]['y']))  # If current vertex is enabled (had to be disabled) - mark as error
                else:
                    if subindex != mask_num:
                        self.error.append((self.mask[subindex][index]['x'], self.mask[subindex][index]['y']))  # If current vertex is enabled (had to be disabled) - mark as error

        # Check results
        if len(self.error):  # If any vertex is not as planned, throw error
            return False

        return True


    # Detect Region of Interest (or point) if the background is white
    def detect_point_state(self, mask_num, index, roi_size=3):
        # Define center of vertex
        x = self.mask[mask_num][index]['x'] + self.mask_offset_x
        y = self.mask[mask_num][index]['y'] + self.mask_offset_y

        # Define color mask in HSV colorspace
        mask_min = np.array([self.mask[mask_num][index]['h1'],self.mask[mask_num][index]['s1'],self.mask[mask_num][index]['v1']], np.uint8)
        mask_max = np.array([self.mask[mask_num][index]['h2'],self.mask[mask_num][index]['s2'],self.mask[mask_num][index]['v2']], np.uint8)

        # Pick up small region of interest (ROI)
        roi = self.image[y - roi_size:y+roi_size, x-roi_size:x+roi_size]

        # Convert BRG to HSV image
        hsv_image = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # Apply color mask
        frame_thresh = cv2.inRange(hsv_image, mask_min, mask_max)

        # Calculate white and black threshold points
        height, width = frame_thresh.shape[:2]
        white = cv2.countNonZero(frame_thresh)
        black = (height * width) - white

        #  Return True if there is more white than black
        if white > black:
            return True

        return False




class STM32Loader:
    def __init__(self, reset_pin, boot_pin, baud = 115200, port = "/dev/ttyAMA0"):
        self.config = None
        self.config.reset_pin = reset_pin
        self.config.boot_pin = boot_pin
        self.baud = baud
        self.port = port
        self.binary = None
        self.cmd = stm32loader.CommandInterface(self.config)

    def set_binary(self, binary):
        # Check if binary exists
        if os.path.isfile(binary):
            self.binary = binary
            module_logger.info("Successfully set '{}' binary.".format(self.binary))
        else:
            module_logger.error("Binary '{}' does not exist.".format(binary))
            return False

        return True

    def flash(self):
        if self.binary is None:
            module_logger.error("Binary is not defined!")
            return False

        self.cmd.open(self.port, self.baud)

        try:
            self.cmd.initChip()
            module_logger.debug("Init done")
        except Exception as ex:
            module_logger.debug("Can't init. Ensure that BOOT0 is enabled and reset device, exception: %s", ex)
            return False

        data = open(self.binary, 'rb').read()

        self.cmd.cmdEraseMemory()
        self.cmd.writeMemory(0x08000000, data)

        self.cmd.unreset()
        return True


# STLink programmer - usable only ST Discovery for now!
# http://startingelectronics.org/tutorials/STM32-microcontrollers/programming-STM32-flash-in-Linux/
# https://github.com/pavelrevak/pystlink

class STLink:
    def __init__(self):
        self.binary = None
        self.process = None
        self.mcu = None
        self.flash = 0x008000

    def flash(self):
        if self.binary is None:
            module_logger.error("Binary is not defined!")
            return False

        #self.process = subprocess.Popen(['/venv_strips_tester/bin/python', '/strips_tester_project/strips_tester/drivers/pystlink/pystlink.py', '-v', '-c', 'STM32F030x8', 'flash:erase:verify:0x08000000:{}' . format(self.binary)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if self.is_hex():
            #print("is hex file")
            self.process = subprocess.Popen(['/stlink/build/Release/st-flash', '--format', 'ihex', 'write', self.binary], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        else:
            #print("not hex")
            self.process = subprocess.Popen(['/stlink/build/Release/st-flash', '--format', 'binary', 'write', self.binary, '0x08000000'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        out, err = self.process.communicate()

        if "jolly" in out.decode() or "Writing FLASH: [========================================] done in " in out.decode():
            #print(out)
            module_logger.info("Successfully flashed '{}' binary." . format(self.binary))
            return True
        else:
            #print(out)
            module_logger.error("Flashing '{}' binary failed." . format(self.binary))
            return False
        # Check if flashing is succeeded!

    def flash_stm8(self):
        if self.binary is None:
            module_logger.error("Binary is not defined!")
            return False

        if self.mcu is None:
            module_logger.error("Processor is not defined!")
            return False

        #self.process = subprocess.Popen(['/venv_strips_tester/bin/python', '/strips_tester_project/strips_tester/drivers/pystlink/pystlink.py', '-v', '-c', 'STM32F030x8', 'flash:erase:verify:0x08000000:{}' . format(self.binary)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if self.is_hex():
            #print("is hex file")
            self.process = subprocess.Popen(['/strips_tester_project/strips_tester/drivers/stm8flash/stm8flash', '-c', 'stlinkv2', '-p', self.mcu, '-w', self.binary,], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        out, err = self.process.communicate()

        if "OK" in out.decode():
            module_logger.info("Successfully flashed '{}' binary." . format(self.binary))
            return True
        else:
            print(out)
            module_logger.error("Flashing '{}' binary failed." . format(self.binary))
            return False
        # Check if flashing is succeeded!

    def set_binary(self, binary):
        # Check if binary exists
        if os.path.isfile(binary):
            self.binary = binary
            module_logger.info("Successfully set '{}' binary." . format(self.binary))
        else:
            module_logger.error("Binary '{}' does not exist." . format(binary))
            return False

        return True

    def set_mcu(self, mcu):
        # Check if binary exists
        self.mcu = mcu
        module_logger.info("Successfully set '{}' processor." . format(self.mcu))

        return True

    def is_hex(self):
        try:
            extension = os.path.splitext(self.binary)[1]

            if 'hex' in extension:
                return True
            else:
                return False
        except Exception:  # File has no extension
            module_logger.error("Binary '{}' has no extension." . format(self.binary))
            return False

    def close(self):
        pass

# Feasa module for LED analitics. Working via USB as serial port emulator
class Feasa:
    def __init__(self, port='/dev/ttyUSB0'):
        # Class variables
        self.found = False
        self.ser = None
        self.port = port
        self.terminator = b'\x04'  # EOL termination (Feasa command 'enableeot' must be send before!)

        # Establish serial connection
        for retries in range(5):
            try:
                self.ser = serial.Serial(port,
                                         timeout=5,
                                         baudrate=57600,
                                         bytesize=serial.EIGHTBITS,
                                         stopbits=serial.STOPBITS_ONE,
                                         parity=serial.PARITY_NONE)

                # Flush serial buffer
                self.ser.flushInput()
                self.ser.flushOutput()

                self.found = True
                break

            #Device not found, retry
            except Exception:
                pass

    # Closes serial connection.
    def close(self):
        if self.found:
            self.ser.close()

        return

    # Sends formatted command to Feasa
    def send(self, command):
        command += "\n"
        self.ser.write(command.encode('ascii'))

    # Recieve response from Freasa with EOT character
    def recieve(self):
        response = self.ser.read_until(self.terminator).decode().split("\r\n")
        response.remove(self.terminator.decode())

        return response

    # Free communication bus
    def free_bus(self):
        if not self.found:
            print("Cannot connect to Feasa module")
            return False

        self.send("busfree")
        response = self.recieve()

        if "OK" in response:
            return True

        return False

    # Capture new measurements. Return True if succeded
    def capture(self, range=5):
        if not self.found:
            print("Cannot connect to Feasa module")
            return False

        if not range:
            self.send("c")
        else:
            self.send("c{}" . format(range))

        response = self.recieve()

        if "OK" in response:
            return True

        return False

    # Get intensity values for all captured values from sensors
    def get_intensity(self):
        if not self.found:
            print("Cannot connect to Feasa module")
            return

        self.send("getintensityall")
        response = self.recieve()

        for current in range(len(response)):
            response[current] = int(response[current][3:])

        return response

    # Get CCT values fro all captured values from sensor
    def get_CCT(self):
        if not self.found:
            print("Cannot connect to Feasa module")
            return

        self.send("getcctall")
        response = self.recieve()

        for current in range(len(response)):
            response[current] = int(response[current][3:8])

        return response

    # Get RGB values fro all captured values from sensor
    def get_RGB(self):
        if not self.found:
            print("Cannot connect to Feasa module")
            return

        self.send("getRGBIall")
        response = self.recieve()

        result = []

        for current in response:
            result.append({})
            result[-1]['R'] = int(current[3:6])
            result[-1]['G'] = int(current[7:10])
            result[-1]['B'] = int(current[11:14])

        return result

    # Get HSI values fro all captured values from sensor
    def get_HSI(self):
        if not self.found:
            print("Cannot connect to Feasa module")
            return

        self.send("getHSIall")
        response = self.recieve()

        result = []

        for current in response:
            result.append({})
            result[-1]['H'] = float(current[3:9])
            result[-1]['S'] = int(current[10:13])
            result[-1]['I'] = int(current[14:19])

        return result

    # Get uv values fro all captured values from sensor
    def get_uv(self):
        if not self.found:
            print("Cannot connect to Feasa module")
            return

        self.send("getuvall")
        response = self.recieve()

        result = []

        for current in response:
            result.append({})
            result[-1]['u'] = float(current[3:9])
            result[-1]['v'] = float(current[10:16])

        return result