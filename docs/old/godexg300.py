import serial


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

    def generate(self, article_type: str, release: str, wifi: str, mac_address: str, test_result: str):
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

    def send_to_printer(self, label_str:str):
        w = self.ser.write(label_str)

    def close(self):
        """Close the serial port connection."""
        self.ser.close()