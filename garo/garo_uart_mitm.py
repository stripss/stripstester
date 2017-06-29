import serial


#  def calc_crc(crc, byte_=0x11021): # CCITT CRC - 16, polynom = X ^ 16 + X ^ 12 + X ^ 5 + 1
#     crc = (crc >> 8) | (crc << 8)
#     crc ^= byte_
#     crc ^= (crc & 0xFF) >> 4
#     crc ^= (crc << 8) << 4
#     crc ^= ((crc & 0xFF) << 4) << 1
#     return crc


def crc16_ccitt(data: bytes, crc: int = 0x11021):
    msb = crc >> 8
    lsb = crc & 255
    for c in data:
        x = c ^ msb
        x ^= (x >> 4)
        msb = (lsb ^ (x >> 3) ^ (x << 4)) & 255
        lsb = (x ^ (x << 5)) & 255
    return (msb << 8) + lsb


def open_mitm(aport="/dev/ttyAMA0", abaudrate=115200):
    sp = serial.Serial(
        port=aport,
        baudrate=abaudrate,     # baudrate
        bytesize=serial.EIGHTBITS,  # number of databits
        parity=serial.PARITY_EVEN,
        stopbits=serial.STOPBITS_ONE,
        xonxoff=0,  # don't enable software flow control
        rtscts=0,  # don't enable RTS/CTS flow control
        timeout=10,  # set a timeout value, None for waiting forever
        dsrdtr=0
    )
    return sp


