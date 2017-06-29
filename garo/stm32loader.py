#!/usr/bin/env python

# -*- coding: utf-8 -*-
# vim: sw=4:ts=4:si:et:enc=utf-8

# Author: Ivan A-R <ivan@tuxotronic.org>
# Project page: http://tuxotronic.org/wiki/projects/stm32loader
#
# This file is part of stm32loader.
#
# stm32loader is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 3, or (at your option) any later
# version.
#
# stm32loader is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with stm32loader; see the file COPYING3.  If not see
# <http://www.gnu.org/licenses/>.

import sys, getopt
from functools import reduce

import logging
import serial
import time
import RPi.GPIO as GPIO
try:
    raise Exception()
    # from progressbar import *
    usepbar = 1
except:
    usepbar = 0

logger = logging.getLogger("strips_tester.garo.stm32_loader")
# Verbose level
QUIET = 20

# these come from AN2606
chip_ids = {
    0x412: "STM32 Low-density",
    0x410: "STM32 Medium-density",
    0x414: "STM32 High-density",
    0x420: "STM32 Medium-density value line",
    0x428: "STM32 High-density value line",
    0x430: "STM32 XL-density",
    0x416: "STM32 Medium-density ultralow power line",
    0x411: "STM32F2xx",
    0x413: "STM32F4xx",
}


class CmdException(Exception):
    pass

class CommandInterface:
    extended_erase = 0

    def __init__(self, config):
        self.resetPin = config.resetPin
        self.bootPin = config.bootPin

    def open(self, aport='/dev/ttyS0', abaudrate=115200) :
        self.sp = serial.Serial(
            #port=aport,
            port='/dev/ttyAMA0',
            #baudrate=abaudrate,     # baudrate
            baudrate=115200,     # baudrate
            bytesize=serial.EIGHTBITS,             # number of databits
            parity=serial.PARITY_EVEN,
            stopbits=
            serial.STOPBITS_ONE,
            xonxoff=0,              # don't enable software flow control
            rtscts=0,               # don't enable RTS/CTS flow control
            timeout=3,               # set a timeout value, None for waiting forever
            dsrdtr = 0
        )

    def _wait_for_ask(self, info=""):
        # wait for ask
        try:
            # ask = ord(a)
            ask = self.sp.read()
        except:
            raise CmdException("Can't read port or timeout")
        else:
            if ask == bytes([0x79]):
                # ACK
                return 1
            else:
                if ask == bytes([0x1F]):
                    # NACK
                    raise CmdException("NACK " + str(info))
                else:
                    # Unknown responce
                    raise CmdException("Unknown response. " + str(info) + ": " , str(ask))

    def reset(self):
        GPIO.output(self.bootPin, GPIO.HIGH)
        GPIO.output(self.resetPin, GPIO.LOW)
        time.sleep(0.2)
        GPIO.output(self.resetPin, GPIO.HIGH)
        time.sleep(0.5)
        # GPIO.output(self.bootPin, GPIO.LOW)
        time.sleep(0.5)

    def unreset(self):
        GPIO.output(self.bootPin, GPIO.LOW)
        time.sleep(0.2)
        GPIO.output(self.resetPin, GPIO.LOW)
        time.sleep(0.2)
        GPIO.output(self.resetPin, GPIO.HIGH)

    def initChip(self):
        # Set boot
        self.reset()
        w_len = self.sp.write(bytes([0x7f]))       # Syncro
        return self._wait_for_ask("Syncro")

    def releaseChip(self):
        GPIO.output(self.resetPin, GPIO.HIGH)
        self.reset()

    # def cmdGeneric(self, cmd):
    #     self.sp.write(chr(cmd))
    #     self.sp.write(chr(cmd ^ 0xFF)) # Control byte
    #     return self._wait_for_ask(hex(cmd))

    def cmdGeneric(self, cmd):
        self.sp.write(bytes([cmd]))
        self.sp.write(bytes([cmd ^ 0xFF])) # Control byte
        return self._wait_for_ask(cmd)

    # def cmdData(self, cmd):
    #     self.sp.write(chr(cmd))
    #     self.sp.write(chr(0xCE)) # Control byte
    #     return self._wait_for_ask(hex(cmd))

    def cmdData(self, cmd):
        self.sp.write(bytes([cmd]))
        self.sp.write(bytes([0xCE])) # Control byte
        return self._wait_for_ask(cmd)

    # def Erase(self, cmd):
    #     self.sp.write(chr(cmd))
    #     self.sp.write(chr((~cmd) & 0xFF))
    #     return self._wait_for_ask(hex(cmd))

    def Erase(self, cmd):
        self.sp.write(bytes([cmd]))
        self.sp.write(bytes([(~cmd) & 0xFF]))
        return self._wait_for_ask(cmd)

    def close(self):
        self.sp.flush()
        self.sp.close()

    def cmdGet(self):
        if self.cmdGeneric(0x00):
            logger.debug("*** Get command")
            len = ord(self.sp.read())
            version = ord(self.sp.read())
            logger.debug("    Bootloader version: %s" , hex(version))
            dat = map(lambda c: hex(c), self.sp.read(len))
            if '0x44' in dat:
                self.extended_erase = 1
                logger.debug( "    Available commands: %s" ,", ".join(dat))
            self._wait_for_ask("0x00 end")
            return version
        else:
            raise CmdException("Get (0x00) failed")

    def cmdGetVersion(self):
        if self.cmdGeneric(0x01):
            logger.debug("*** GetVersion command")
            version = ord(self.sp.read())
            self.sp.read(2)
            self._wait_for_ask("0x01 end")
            logger.debug("    Bootloader version: %s",hex(version))
            return version
        else:
            raise CmdException("GetVersion (0x01) failed")

    def cmdGetID(self):
        if self.cmdGeneric(0x02):
            logger.debug("*** GetID command")
            len = ord(self.sp.read())
            id = self.sp.read(len+1)
            self._wait_for_ask("0x02 end")
            return reduce(lambda x, y: x*0x100+y, id)
        else:
            raise CmdException("GetID (0x02) failed")

    def _encode_addr(self, addr):
        # self.sp.reset_output_buffer()
        byte3 = (addr >> 0) & 0xFF
        byte2 = (addr >> 8) & 0xFF
        byte1 = (addr >> 16) & 0xFF
        byte0 = (addr >> 24) & 0xFF
        crc = 0x00
        crc = byte0 ^ byte1 ^ byte2 ^ byte3
        crc &= 0xFF
        self.sp.write(bytes([byte0]))
        self.sp.write(bytes([byte1]))
        self.sp.write(bytes([byte2]))
        self.sp.write(bytes([byte3]))
        self.sp.write(bytes([crc]))
        #return (chr(byte0) + chr(byte1) + chr(byte2) + chr(byte3) + chr(crc))


    def cmdReadMemory(self, addr, lng):
        assert(lng <= 256)
        if self.cmdGeneric(0x11):
            logger.debug("*** ReadMemory command")
            self.sp.write(self._encode_addr(addr))
            self._wait_for_ask("0x11 address failed")
            N = (lng - 1) & 0xFF
            crc = N ^ 0xFF
            self.sp.write(chr(N) + chr(crc))
            self._wait_for_ask("0x11 length failed")
            return map(lambda c: ord(c), self.sp.read(lng))
        else:
            raise CmdException("ReadMemory (0x11) failed")


    def cmdGo(self, addr):
        if self.cmdGeneric(0x21):
            logger.debug( "*** Go command")
            self.sp.write(self._encode_addr(addr))
            self._wait_for_ask("0x21 go failed")
        else:
            raise CmdException("Go (0x21) failed")


    def cmdWriteMemory(self, addr, data):

        assert(len(data) <= 256)
        if self.cmdData(0x31):
            #mdebug(10, "*** Write memory command")
            self._encode_addr(addr)
            #self.sp.write(self._encode_addr(addr))
            self._wait_for_ask("0x31 address failed")
            self.sp.reset_output_buffer()
            lng = (len(data)-1) & 0xFF
            #mdebug(10, "    %s bytes to write" % [lng+1]);
            self.sp.write(bytes([lng])) # len really
            crc = 0x00
            crc ^= lng
            for c in data:
                if type(c) is int:  # python 2/3 compat
                    crc ^= c
                    d =bytes([c])
                    self.sp.write(d)
                else:
                    crc ^= c
                    self.sp.write(bytes([c]))
            if crc^crc == 0x00:
                pass
            else:
                print("Crc no ok")

            # ch_crc = chr(crc)
            self.sp.write(bytes([crc]))
            self._wait_for_ask("0x31 programming failed")
            logger.debug( "    Write memory done")
        else:
            raise CmdException("Write memory (0x31) failed")


    def cmdEraseMemory(self, sectors = None):
        #if self.extended_erase:
            #return cmd.cmdExtendedEraseMemory()

        if self.Erase(0x44):
            logger.debug( "*** Erase memory command")
            if sectors is None:
                # Global erase
                self.sp.write(bytes([0xFF]))
                self.sp.write(bytes([0xFF]))
                self.sp.write(bytes([0x00]))
            else:
                # Sectors erase
                self.sp.write(bytes([(len(sectors)-1) & 0xFF]))
                crc = 0xFF
                for c in sectors:
                    crc = crc ^ c
                    self.sp.write(bytes([c]))
                self.sp.write(bytes([crc]))

            self._wait_for_ask("0x44 erasing failed")
            logger.debug( "    Erase memory done")
        else:
            raise CmdException("Erase memory (0x43) failed")

    def cmdExtendedEraseMemory(self):
        if self.cmdGeneric(0x44):
            logger.debug( "*** Extended Erase memory command")
            # Global mass erase
            self.sp.write(chr(0xFF))
            self.sp.write(chr(0xFF))
            # Checksum
            self.sp.write(chr(0x00))
            tmp = self.sp.timeout
            self.sp.timeout = 30
            # print "Extended erase (0x44), this can take ten seconds or more"
            self._wait_for_ask("0x44 erasing failed")
            self.sp.timeout = tmp
            logger.debug( "    Extended Erase memory done")
        else:
            raise CmdException("Extended Erase memory (0x44) failed")

    def cmdWriteProtect(self, sectors):
        if self.cmdGeneric(0x63):
            logger.debug( "*** Write protect command")
            self.sp.write(chr((len(sectors)-1) & 0xFF))
            crc = 0xFF
            for c in sectors:
                crc = crc ^ c
                self.sp.write(chr(c))
            self.sp.write(chr(crc))
            self._wait_for_ask("0x63 write protect failed")
            logger.debug( "    Write protect done")
        else:
            raise CmdException("Write Protect memory (0x63) failed")

    def cmdWriteUnprotect(self):
        if self.cmdGeneric(0x73):
            logger.debug( "*** Write Unprotect command")
            self._wait_for_ask("0x73 write unprotect failed")
            self._wait_for_ask("0x73 write unprotect 2 failed")
            logger.debug( "    Write Unprotect done")
        else:
            raise CmdException("Write Unprotect (0x73) failed")

    def cmdReadoutProtect(self):
        if self.cmdGeneric(0x82):
            logger.debug( "*** Readout protect command")
            self._wait_for_ask("0x82 readout protect failed")
            self._wait_for_ask("0x82 readout protect 2 failed")
            logger.debug( "    Read protect done")
        else:
            raise CmdException("Readout protect (0x82) failed")

    def cmdReadoutUnprotect(self):
        if self.cmdGeneric(0x92):
            logger.debug( "*** Readout Unprotect command")
            self._wait_for_ask("0x92 readout unprotect failed")
            self._wait_for_ask("0x92 readout unprotect 2 failed")
            logger.debug( "    Read Unprotect done")
        else:
            raise CmdException("Readout unprotect (0x92) failed")


# Complex commands section

    # def readMemory(self, addr, lng):
    #     data = []
    #     if usepbar:
    #         widgets = ['Reading: ', Percentage(),', ', ETA(), ' ', Bar()]
    #         pbar = ProgressBar(widgets=widgets,maxval=lng, term_width=79).start()
    #
    #     while lng > 256:
    #         if usepbar:
    #             pbar.update(pbar.maxval-lng)
    #         else:
    #             mdebug(5, "Read %(len)d bytes at 0x%(addr)X" % {'addr': addr, 'len': 256})
    #         data = data + self.cmdReadMemory(addr, 256)
    #         addr = addr + 256
    #         lng = lng - 256
    #     if usepbar:
    #         pbar.update(pbar.maxval-lng)
    #         pbar.finish()
    #     else:
    #         mdebug(5, "Read %(len)d bytes at 0x%(addr)X" % {'addr': addr, 'len': 256})
    #     data = data + self.cmdReadMemory(addr, lng)
    #     return data

    def writeMemory(self, addr, data):
        usepbar = False
        lng = len(data)
        if usepbar:
            widgets = None # ['Writing: ', Percentage(),' ', ETA(), ' ', Bar()]
            pbar = None #  ProgressBar(widgets=widgets, maxval=lng, term_width=79).start()

        offs = 0
        chunk_size = 256
        while lng > chunk_size:
            if usepbar:
                pbar.update(pbar.maxval-lng)
            else:
                logger.debug("Write %s bytes at %s", chunk_size, hex(addr))
            self.cmdWriteMemory(addr, data[offs:offs+chunk_size])
            offs = offs + chunk_size
            addr = addr + chunk_size
            lng = lng - chunk_size
        if usepbar:
            pbar.update(pbar.maxval-lng)
            pbar.finish()
        else:
            logger.debug( "Write %s bytes at %s" , chunk_size, hex(addr))
        self.cmdWriteMemory(addr, data[offs:offs+lng] + bytes([0xFF] * (chunk_size-lng)) )
        logger.info("Writing flash complete")


def usage():
    print("""Usage: %s [-hqVewvr] [-l length] [-p port] [-b baud] [-a addr] [-g addr] [file.bin]
    -h          This help
    -q          Quiet
    -V          Verbose
    -e          Erase
    -w          Write
    -v          Verify
    -r          Read
    -l length   Length of read
    -p port     Serial port (default: /dev/tty.usbserial-ftCYPMYJ)
    -b baud     Baud speed (default: 115200)
    -a addr     Target address
    -g addr     Address to start running at (0x08000000, usually)

    ./stm32loader.py -e -w -v example/main.bin

    """ % sys.argv[0])


if __name__ == "__main__":
    
    # Import Psyco if available
    try:
        import psyco
        psyco.full()
        print ("Using Psyco...")
    except ImportError:
        pass

    conf = {
            'port': '/dev/ttyS0',
            'baud': 115200,
            'address': 0x08000000,
            'erase': 0,
            'write': 0,
            'verify': 0,
            'read': 0,
            'go_addr':-1,
        }

# http://www.python.org/doc/2.5.2/lib/module-getopt.html

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hqVewvrp:b:a:l:g:")
    except getopt.GetoptError as err:
        # print help information and exit:
        print(str(err)) # will print something like "option -a not recognized"
        usage()
        sys.exit(2)

    QUIET = 5

    for o, a in opts:
        if o == '-V':
            QUIET = 10
        elif o == '-q':
            QUIET = 0
        elif o == '-h':
            usage()
            sys.exit(0)
        elif o == '-e':
            conf['erase'] = 1
        elif o == '-w':
            conf['write'] = 1
        elif o == '-v':
            conf['verify'] = 1
        elif o == '-r':
            conf['read'] = 1
        elif o == '-p':
            conf['port'] = a
        elif o == '-b':
            conf['baud'] = eval(a)
        elif o == '-a':
            conf['address'] = eval(a)
        elif o == '-g':
            conf['go_addr'] = eval(a)
        elif o == '-l':
            conf['len'] = eval(a)
        else:
            assert False, "unhandled option"

    cmd = CommandInterface()
    cmd.open(conf['port'], conf['baud'])
    logger.debug( "Open port %s, baud %s" ,conf['port'], conf['baud'])
    try:
        try:
            cmd.initChip()
        except:
            logger.debug ("Can't init. Ensure that BOOT0 is enabled and reset device")


        bootversion = cmd.cmdGet()
        logger.debug( "Bootloader version %s" , bootversion)
        id = cmd.cmdGetID()
        logger.debug( "Chip id: 0x%s (%s)" , id, chip_ids.get(id, "Unknown"))
#    cmd.cmdGetVersion()
#    cmd.cmdGetID()
#    cmd.cmdReadoutUnprotect()
#    cmd.cmdWriteUnprotect()
#    cmd.cmdWriteProtect([0, 1])

        if (conf['write'] or conf['verify']):
            data = map(lambda c: ord(c), file(args[0], 'relay_board').read())

        if conf['erase']:
            cmd.cmdEraseMemory()

        if conf['write']:
            cmd.writeMemory(conf['address'], data)

        if conf['verify']:
            verify = cmd.readMemory(conf['address'], len(data))
            if(data == verify):
                print ("Verification OK")
            else:
                print ("Verification FAILED")
                print (str(len(data)) + ' vs ' + str(len(verify)))
                for i in xrange(0, len(data)):
                    if data[i] != verify[i]:
                        print (hex(i) + ': ' + hex(data[i]) + ' vs ' + hex(verify[i]))

        if not conf['write'] and conf['read']:
            rdata = cmd.readMemory(conf['address'], conf['len'])
            file(args[0], 'wb').write(''.join(map(chr,rdata)))

        if conf['go_addr'] != -1:
            cmd.cmdGo(conf['go_addr'])

    finally:
        cmd.releaseChip()

