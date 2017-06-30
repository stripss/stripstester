import os
import select

import logging

import numpy as np
import serial
import hid
from time import sleep
from datetime import datetime
import picamera.array
from matplotlib import pyplot as pp
import time
import json
import picamera
from picamera import PiCamera
from strips_tester import *

module_logger = logging.getLogger(".".join((PACKAGE_NAME, __name__)))


class Honeywell1400:
    hid_lookup = {4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j', 14: 'k', 15: 'l', 16: 'm',
                  17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's', 23: 't', 24: 'u', 25: 'v', 26: 'w', 27: 'x', 28: 'y', 29: 'z',
                  30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0', 44: ' ', 45: '-', 46: '=',
                  47: '[', 48: ']', 49: '\\', 51: ';', 52: '\'', 53: '~', 54: ',', 55: '.', 56: '/', 81: '\n'}

    def __init__(self, vendor_id: int = 0x0c2e, product_id: int = 0x0b81, path: str = "/dev/hidraw1", max_code_length: int = 50):
        self.vendor_id = vendor_id
        self.product_id = product_id
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

    def __init__(self, port='/dev/ttyUSB1', retries=3, timeout=3.0):
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

        self.logger = logging.getLogger(__name__)

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
            raise self.DmmNoData()
        n = ord(v)
        pos = n // 16
        if pos == 0 or pos == 15:
            logger.warning("Problem synchronizing Digital multimeter")
            module_logger.debug("Synchronizing")
            self._synchronize()  # watch out, possible infinite loop
            raise self.DmmInvalidSyncValue()

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
    OPEN_CMD = (0xD2, 0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x48, 0x49, 0x44, 0x43, 0x80, 0x02, 0x00, 0x00)
    CLOSE_CMD = (0x71, 0x0E, 0x71, 0x00, 0x00, 0x00, 0x11, 0x11, 0x00, 0x00, 0x48, 0x49, 0x44, 0x43, 0x2A, 0x02, 0x00, 0x00)

    def __init__(self, vid: int = 0x0416, pid=0x5020, path: str = None, initial_status=None, number_of_relays: int = 16):
        self.__WRITE_CMD = [0xC3, 0x0E, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x48, 0x49, 0x44, 0x43, 0xEE, 0x01, 0x00, 0x00]
        self.number_of_relays = number_of_relays
        self.hid_device = hid.device()
        if path:
            self.hid_device.open_path(path)
        else:
            self.hid_device.open(vid, pid)
        self.hid_device.write(self.OPEN_CMD)
        self.logger = logging.getLogger(__name__)
        self.status = initial_status if initial_status else [False] * number_of_relays

    # def __del__(self):
    #     self.hid_device.write(self.CLOSE_CMD)
    #     self.hid_device.close()

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
    def open_all(self):
        self.status = [False] * self.number_of_relays
        self._write_status()
        self.logger.debug("All relays_config opened")

    # Closes all relays_config
    def close_all(self):
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


class CameraDevice:
    logger = logging.getLogger(".".join((PACKAGE_NAME, __name__, "CameraDevice")))
    def __init__(self, config_path: str):
        self.Xres = 128
        self.Yres = 80
        self.thr = 0.8
        self.Idx = None
        self.images = None
        self.interval = 80
        self.imgNum = 40

        self.dx = None
        self.dy = None
        self.imgCount = 0

        self.load(config_path)
        self.img = np.empty((self.Xres, self.Yres,self.imgNum), dtype=np.uint8)
        self.camera = picamera.PiCamera()
        self.set_camera_parameters()
        try:
            logger.debug("Starting self test")
            self.self_test()
        except:
            logger.error("Failed to init Camera")


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
            self.images = data['images']
            self.interval = data['interval']
            self.imgNum = data['image number']

    def save(self, file_path):
        data = {
            'Xres': self.Xres,
            'Yres': self.Yres,
            'threshold': self.thr,
            'Idx': self.Idx,
            'images': self.images,
            'interval': self.interval,
            'image number': self.imgNum
        }
        with open(file_path, 'w') as f:
            json.dump(data, f)

    def is_complete(self):
        return self.images is not None and self.t1 is not None and self.t2 is not None

    def podrocje(self, img, msg):
        if self.t1 is None or self.t2 is None:
            pp.figure()
            pp.imshow(img)
            pp.title(msg)
            t1, t2 = pp.ginput(n=2)
            x1 = int(t1[1])
            x2 = int(t2[1])
            y1 = int(t1[0])
            y2 = int(t2[0])
            pp.close()
            self.t1 = (x1, y1)
            self.t2 = (x2, y2)

    @staticmethod
    def shift_picture(img, dx, dy):
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

    # def setResolution(self):
    #     self.camera.resolution = (self.conf.Xres, self.conf.Yres)
    #     self.camera.framerate = 80
    #     self.camera.start_preview()
    #     sleep(3)
    #     dx = 32
    #     dy = 16
    #
    #     while True:
    #         sleep(1)
    #         calibPic = np.empty((self.conf.Xres, self.conf.Yres,3),dtype=np.uint8)
    #         self.camera.capture(calibPic, 'rgb', use_video_port=True)
    #         self.podrocje(calibPic[:,:,0],'Izberi levi zgornji in desni spodnji kot dvopičja ')
    #
    #         if (self.conf.t2[0]-self.conf.t1[0])*(self.conf.t2[1]-self.conf.t1[1])< self.conf.res:
    #             print("Resolution to low : get camera closer to the screen or increase resolution !!!")
    #             sleep(10)
    #         elif (self.conf.t2[0]-self.conf.t1[0])*(self.conf.t2[1]-self.conf.t1[1]) > self.conf.res*1.5:
    #                 print("Resolution to high : Changing camera resolution ...")
    #                 self.camera.resolution = (self.conf.Xres-dx, self.conf.Yres-dy)
    #                 sleep(2)
    #         else:
    #             print("Resolution set succesfully")
    #             break
    #
    #     self.camera.stop_preview()

    def set_camera_parameters(self):
        self.camera.shutter_speed = self.camera.exposure_speed
        self.camera.exposure_mode = 'off'
        g = self.camera.awb_gains
        self.camera.awb_mode = 'off'
        self.camera.awb_gains = g
        self.camera.resolution = (self.Xres, self.Yres)
        self.camera.framerate = 40
        # self.camera.iso = 400   #could change in low light
        time.sleep(3)

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
        ind1 = img > np.max(img)*thr
        ind2 = img <= np.max(img)*thr
        oimg[ind1] = ls
        oimg[ind2] = 0
        return oimg

    def compare(self, img1, img2):
        # img1 = self.im_window(img1,230, 40)
        # img2 = self.im_window(img2, 230, 40)
        #print(33,img1)
        img1 = self.im_step(img1, 0.6)
        #print(33,img1)
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
            shiftImg = self.shift_picture(imgB, ty[i], tx[i])
            MSE[i] = self.compare_img(imgA, shiftImg)
        MSE.shape = txshape
        return MSE

    def compare_idx(self):
        # for i in range(self.)
        x = 1

    def self_test(self):
        time.sleep(1)
        slika1 = np.zeros((self.Xres, self.Yres, 3), dtype=np.uint8)
        slika2 = np.zeros((self.Xres, self.Yres, 3), dtype=np.uint8)
        self.camera.capture(slika1, 'rgb', use_video_port=True)
        logger.debug("first pic")
        time.sleep(1)
        self.camera.capture(slika2, 'rgb', use_video_port=True)
        logger.debug("second pic")
        # print("selftest", slika1,55, slika1[:, :, 1])
        # print("max from pic",np.max(slika1[:, :, 0]),np.max(slika1[:, :, 1]),np.max(slika1[:, :, 2]))
        #print("Image size",slika1.shape[0]," ",slika1.shape[1])
        perc, result = self.compare(slika1[:, :, 0], slika2[:, :, 0])
        if result:
            logger.debug('Self test done. Pictures match by : %s percent', perc)
            return True
        else:
            logger.debug('Self test failed !!!. Pictures match by %s percent', perc)
            return False

    def calibrate(self):
        tx = ty = np.arange(-4, 4 + 1)
        Tx, Ty = np.meshgrid(tx, ty, indexing='xy')

        slika1 = np.empty((self.Xres, self.Yres, 3), dtype=np.uint8)
        slika2 = np.empty((self.Xres, self.Yres, 3), dtype=np.uint8)

        time.sleep(1)
        self.camera.capture(slika1, 'rgb', use_video_port=True)
        logger.debug('Calibration in progress. Try to move camera to test, 5s sleep')
        time.sleep(5)
        self.camera.capture(slika2, 'rgb', use_video_port=True)

        matrix = self.rigid_sm(slika1[:, :, 0], slika2[:, :, 0], Tx, Ty)
        m = np.argmax(matrix)
        x = np.mod(m, np.size(tx))
        y = int(np.floor(m / np.size(ty)))
        self.dx = Tx[0, x]
        self.dy = Ty[y, 0]
        logger.debug("Calibration results. dx : %s, dy : %s ", self.dx, self.dy)

    def close(self):
        self.camera.close()

    def take_pictures(self, imNum=40):
        if imNum > self.imgNum:
            logger.error("Memory only for %s pictures. Change configuratio file",self.imgNum)
            return False
        else:
            self.imgCount = 0
            image = np.empty((self.Xres,self.Yres,3),dtype=np.uint8)
            for i in range(imNum):
                t1 = datetime.now()
                self.camera.capture(image, 'rgb', use_video_port=True)
                self.img[:,:,i] = image[:,:,0]
                t2 = datetime.now()
                dt = t2 - t1
                while (dt.microseconds < (self.interval*1000)):
                    t2 = datetime.now()
                    dt = t2 - t1
                    sleep(0.005)
                logger.debug('Took picture %s in %s us', i, dt.microseconds/1000)
                self.imgCount = self.imgCount + 1
            return True


    def get_picture(self, Idx=0):
        if Idx < 0 or Idx > self.imgCount:
            logger.error("Idx out of bounds for picture access")
            return False
        else:
            return self.img[:,:,Idx]

    def take_img(self,xres=128, yres=80, RGB=0):
        slika = np.empty([xres,yres,3], dtype=np.uint8)
        self.camera.capture(slika,'rgb')
        #print("Picture max RGB",np.max(slika[:,:,0]),np.max(slika[:,:,1]),np.max(slika[:,:,2]))
        return slika[:,:,RGB]


    def run_test(self):
        for j in range(self.imgCount):
            slika = self.get_picture(j)
            for i in range(len(self.Idx)):
                x = self.Idx[i]["x"] + self.dx
                y = self.Idx[i]["y"] + self.dy
                b1 = slika[y, x] >> 7
                if b1 != 0 and i != j:
                    logger.error("Test failed, picture : %s",j+1)
                    return False
                elif i == j and b1 == 0:
                    logger.error("Test failed, picture : %s",j+1)
                    return False
        return True





