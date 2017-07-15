import pyserial
import time


class FS9721_Error(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class FS9721_Error_PORT_NOT_OPENED(FS9721_Error):
    pass


class FS9721:
    def __init__(self, portname):
        self.port = pyserial.serial_for_url(portname, do_not_open=True)
        self.port.setBaudrate(2400)
        self.port.setParity('N')
        self.port.setByteSize(8)
        self.port.setStopbits(1)
        self.port.setDsrDtr(False)
        self.port.setRtsCts(False)
        self.port.setXonXoff(False)
        try:
            self.port.open()
            self.port.setDTR(1)
            self.port.setRTS(0)
            self.port.flushInput()
            self.port.flushOutput()
        except:
            raise FS9721_Error_PORT_NOT_OPENED("Ne morem odpreti serijskih vrat")
        self.measureTIMESTAMP = time.time()
        self.measureVALID = False
        self.rx = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
        self.rxptr = 0

    def __del__(self):
        if self.port.isOpen():
            self.port.close()

    @staticmethod
    def decode7seg(byte1, byte2):
        value = ((byte1 & 0b00000111) << 4) | (byte2 & 0b00001111)
        if value == 0b01111101:
            return '0'
        elif value == 0b00000101:
            return '1'
        elif value == 0b01011011:
            return '2'
        elif value == 0b00011111:
            return '3'
        elif value == 0b00100111:
            return '4'
        elif value == 0b00111110:
            return '5'
        elif value == 0b01111110:
            return '6'
        elif value == 0b00010101:
            return '7'
        elif value == 0b01111111:
            return '8'
        elif value == 0b00111111:
            return '9'
        elif value == 0b01101000:
            return 'L'
        elif value == 0b00000000:
            return ' '
        else:
            raise FS9721_Error("Neznan znak na prikazovalniku")

    modeVOLTAGE = 0
    modeRESISTANCE = 1
    modeDIODE = 2
    modeCONDUCT = 3
    modeCAPACITANCE = 4
    modeFREQUENCY = 5
    modeDUTYCYCLE = 6
    modeCURRENT = 7

    def refresh(self):
        while self.port.inWaiting() != 0:
            self.rx[self.rxptr] = self.port.read(1)[0]
            self.rxptr += 1
            if self.rxptr != ((self.rx[self.rxptr - 1]) >> 4):
                self.rxptr = 0
            else:
                if self.rxptr >= 14:
                    self.rxptr = 0
                    self.measureDIGITS = FS9721.decode7seg(self.rx[1], self.rx[2]) + \
                                         FS9721.decode7seg(self.rx[3], self.rx[4]) + \
                                         FS9721.decode7seg(self.rx[5], self.rx[6]) + \
                                         FS9721.decode7seg(self.rx[7], self.rx[8])
                    if (self.rx[9] & 0b00000001) != 0:
                        if (self.rx[12] & 0b00000100) != 0:
                            self.measureMODE = FS9721.modeDIODE
                        else:
                            raise FS9721_Error("Neznan način meritve")
                    elif (self.rx[10] & 0b00000001) != 0:
                        if (self.rx[11] & 0b00000100) != 0:
                            self.measureMODE = FS9721.modeCONDUCT
                        else:
                            raise FS9721_Error("Neznan način meritve")
                    elif (self.rx[12] & 0b00000100) != 0:
                        self.measureMODE = FS9721.modeVOLTAGE
                    elif (self.rx[11] & 0b00000100) != 0:
                        self.measureMODE = FS9721.modeRESISTANCE
                    elif (self.rx[11] & 0b00001000) != 0:
                        self.measureMODE = FS9721.modeCAPACITANCE
                    elif (self.rx[12] & 0b00000010) != 0:
                        self.measureMODE = FS9721.modeFREQUENCY
                    elif (self.rx[10] & 0b00000100) != 0:
                        self.measureMODE = FS9721.modeDUTYCYCLE
                    elif (self.rx[12] & 0b00001000) != 0:
                        self.measureMODE = FS9721.modeCURRENT
                    else:
                        raise FS9721_Error("Neznan način meritve")
                    if (self.rx[11] & 0b00000001) != 0:
                        self.measureHOLD = True
                    else:
                        self.measureHOLD = False
                    if (self.rx[11] & 0b00000010) != 0:
                        self.measureDELTA = True
                    else:
                        self.measureDELTA = False
                    if (self.rx[12] & 0b00000001) != 0:
                        self.measureLOWBATTERY = True
                    else:
                        self.measureLOWBATTERY = False
                    if (self.rx[0] & 0b00000001) != 0:
                        self.measureRS232 = True
                    else:
                        self.measureRS232 = False
                    if (self.rx[0] & 0b00000010) != 0:
                        self.measureAUTO = True
                    else:
                        self.measureAUTO = False
                    if (self.rx[0] & 0b00000100) != 0:
                        self.measureDC = True
                    else:
                        self.measureDC = False
                    if (self.rx[0] & 0b00001000) != 0:
                        self.measureAC = True
                    else:
                        self.measureAC = False
                    if self.measureDIGITS == " 0L ":
                        self.measureOUTOFLIMIT = True
                        self.measureREADING = float("inf")
                    else:
                        self.measureOUTOFLIMIT = False
                        self.measureREADING = float(self.measureDIGITS)
                    self.measureNANO = False
                    self.measureMICRO = False
                    self.measureMILLI = False
                    self.measureKILO = False
                    self.measureMEGA = False
                    if (self.rx[3] & 0b00001000) != 0:
                        self.measureREADING = self.measureREADING / 1000.0
                    elif (self.rx[5] & 0b00001000) != 0:
                        self.measureREADING = self.measureREADING / 100.0
                    elif (self.rx[7] & 0b00001000) != 0:
                        self.measureREADING = self.measureREADING / 10.0
                    if (self.rx[1] & 0b00001000) != 0:
                        self.measureREADING = -self.measureREADING
                    if (self.rx[9] & 0b00000100) != 0:
                        self.measureNANO = True
                        self.measureREADING = self.measureREADING / 1000000000.0
                    elif (self.rx[9] & 0b00001000) != 0:
                        self.measureMICRO = True
                        self.measureREADING = self.measureREADING / 1000000.0
                    elif (self.rx[10] & 0b00001000) != 0:
                        self.measureMILLI = True
                        self.measureREADING = self.measureREADING / 1000.0
                    elif (self.rx[9] & 0b00000010) != 0:
                        self.measureKILO = True
                        self.measureREADING = self.measureREADING * 1000.0
                    elif (self.rx[10] & 0b00000010) != 0:
                        self.measureMEGA = True
                        self.measureREADING = self.measureREADING * 1000000.0
                    self.measureTIMESTAMP = time.time()
                    self.measureVALID = True
