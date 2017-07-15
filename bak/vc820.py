import serial
import time


class VC820:
    bytes_per_read = 14

    def __init__(self, portname: str = "/dev/ttyUSB0"):
        self.serial = serial.serial_for_url(portname, do_not_open=True)
        self.serial.baudrate = 2400
        self.serial.parity = 'N'
        self.serial.bytesize = 8
        self.serial.stopbits = 1
        self.serial.dsrdtr = False
        self.serial.rtscts = False
        self.serial.xonxoff = False
        self.open()

    def open(self):
        try:
            self.serial.open()
            self.serial.dtr = 1
            self.serial.rts = 0
            self.serial.flushInput()
            self.serial.flushOutput()
        except:
            print("Ne morem odpreti serijskih vrat")

    def synchronize(self, retries: int= 4):
        for retry in range(retries):
            v = self.serial.read(1)
            if len(v) != 1:
                print("failed read - sync")
                continue
            pos = ord(v) // 16
            if pos == 0 or pos == 15:
                print("failed pos - sync")
                continue
            bytes_needed = VC820.bytes_per_read - pos
            if bytes_needed:
                self.serial.read(bytes_needed)
                break

    def read_voltage(self) -> float:
        self.synchronize()
        line = self.serial.read(14)
        print(line)



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
            print("Neznan znak na prikazovalniku")

    modeVOLTAGE = 0
    modeRESISTANCE = 1
    modeDIODE = 2
    modeCONDUCT = 3
    modeCAPACITANCE = 4
    modeFREQUENCY = 5
    modeDUTYCYCLE = 6
    modeCURRENT = 7

    def refresh(self):
        while self.serial.inWaiting() != 0:
            self.rx[self.rxptr] = self.serial.read(1)[0]
            self.rxptr += 1
            if self.rxptr != ((self.rx[self.rxptr - 1]) >> 4):
                self.rxptr = 0
            else:
                if self.rxptr >= 14:
                    self.rxptr = 0
                    self.measureDIGITS = VC820.decode7seg(self.rx[1], self.rx[2]) + \
                                         VC820.decode7seg(self.rx[3], self.rx[4]) + \
                                         VC820.decode7seg(self.rx[5], self.rx[6]) + \
                                         VC820.decode7seg(self.rx[7], self.rx[8])
                    if (self.rx[9] & 0b00000001) != 0:
                        if (self.rx[12] & 0b00000100) != 0:
                            self.measureMODE = VC820.modeDIODE
                        else:
                            print("Neznan način meritve")
                    elif (self.rx[10] & 0b00000001) != 0:
                        if (self.rx[11] & 0b00000100) != 0:
                            self.measureMODE = VC820.modeCONDUCT
                        else:
                            print("Neznan način meritve")
                    elif (self.rx[12] & 0b00000100) != 0:
                        self.measureMODE = VC820.modeVOLTAGE
                    elif (self.rx[11] & 0b00000100) != 0:
                        self.measureMODE = VC820.modeRESISTANCE
                    elif (self.rx[11] & 0b00001000) != 0:
                        self.measureMODE = VC820.modeCAPACITANCE
                    elif (self.rx[12] & 0b00000010) != 0:
                        self.measureMODE = VC820.modeFREQUENCY
                    elif (self.rx[10] & 0b00000100) != 0:
                        self.measureMODE = VC820.modeDUTYCYCLE
                    elif (self.rx[12] & 0b00001000) != 0:
                        self.measureMODE = VC820.modeCURRENT
                    else:
                        print("Neznan način meritve")
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
                    self.measure_timestamp = time.time()
                    self.measure_valid = True
