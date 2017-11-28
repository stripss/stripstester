import utils
import time
# from smbus2 import SMBusWrapper
#
# class IRTemperatureSensor():
#     MLX90615_I2C_ADDR = 0x5B
#     MLX90615_REG_TEMP_AMBIENT = 0x26
#     MLX90615_REG_TEMP_OBJECT = 0x27
#
#     def __init__(self, delay: int = 1):
#         pass
#         #self.bus = SMBus(1)
#
#     def get_value(self):
#         with SMBusWrapper(1) as bus:
#             block = bus.read_i2c_block_data(IRTemperatureSensor.MLX90615_I2C_ADDR,
#                                                  IRTemperatureSensor.MLX90615_REG_TEMP_OBJECT,
#                                                  2)
#         temperature = (block[0] | block[1] << 8) * 0.02 - 273.15
#         return temperature
#
#     def close(self):
#         #self.bus.close()
#         pass
#
# # my_camera = utils.Camera()
# # my_camera.start_preview()
# # time.sleep(1000)
# while True:
#     temp = IRTemperatureSensor().get_value()
#     print(temp)

# my_camera = utils.Camera()
# my_camera.start_preview()
# time.sleep(1000)



# import os
#
# while True:
#     print(time.time())
#     os.system('sudo /home/pi/Desktop/YVoltage VOLTAGE1-A953A.voltage1 get_currentValue')
#     print(time.time())

# from pytz import timezone
# import datetime
# import pytz
#
# utc = pytz.utc
# #tz = utils.get_time_zone()
# lj_tz = timezone('Europe/Ljubljana')
# my_time = lj_tz.localize(datetime.datetime.now()).astimezone(utc)
# print(my_time)
# print(my_time.tzinfo)
# print(my_time.astimezone(lj_tz))


# import hid
# hid.enumerate()
# print('finish')

import hid
import time

class AbstractBarCodeScanner:
    def __init__(self, name):
        self.name = name
        #self.open()

    def get_decoded_data(self):
        return self.get_dec_data()

    def get_raw_data(self):
        return self.read_raw()

    def open(self):
        self.open_scanner()
        #module_logger.debug("%s opened", self.name)

    def close(self):
        self.close_scanner()
        #module_logger.debug("%s closed", self.name)


class Honeywell1400g(AbstractBarCodeScanner):
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

# # enumerate USB devices
#
# for d in hid.enumerate():
#     keys = list(d.keys())
#     keys.sort()
#     for key in keys:
#         print("%s : %s" % (key, d[key]))
#     print()
#
# # try opening a device, then perform write and read
#
# try:
#     print("Opening the device")
#
#     h = hid.device()
#     h.open(0x0c2e, 0x0b87) # TREZOR VendorID/ProductID
#
#     print("Manufacturer: %s" % h.get_manufacturer_string())
#     print("Product: %s" % h.get_product_string())
#     print("Serial No: %s" % h.get_serial_number_string())
#     #print("Descriptor %s" % h.get_feature_report())
#
#     # enable non-blocking mode
#     h.set_nonblocking(1)
#
#     # write some data to the device
#     # print("Write the data")
#     # h.write([0, 63, 35, 35] + [0] * 61)
#
#     # wait
#     time.sleep(0.05)
#
#     # read back the answer
#     print("Read the data")
#     str = None
#     while True:
#         d = h.read(256)
#         if d:
#             for i in range(len(d)):
#                 print(hex(d[i]))
#                 print(chr(d[i]))
#
#             #print(str(d))
#             break
#
#     print("Closing the device")
#     h.close()
#
# except IOError as ex:
#     print(ex)
#     print("You probably don't have the hard coded device. Update the hid.device line")
#     print("in this script with one from the enumeration list output above and try again.")
#
# print("Done")


# my_scanner = Honeywell1400g(0x0c2e, 0x0b87)
# #raw_data = my_scanner.get_raw_data()
# decoded_string = my_scanner.get_decoded_data()
# print(decoded_string)


# import multiprocessing
#
# print("Number of cpu : ", multiprocessing.cpu_count())
# import glob
# import os
#
# def get_latest_file(path_to_search):
#     list_of_files = glob.glob(path_to_search)  # * means all if need specific format then *.csv
#     latest_file = max(list_of_files, key=os.path.getctime)
#     return latest_file
#
#
# last = get_latest_file('/strips_tester_project/strips_tester/configs/000000005e16aa11_MVC2/garo/bin/mcu*')
# print(last)


# -*- coding: utf-8 -*-

import wifi


def Search():
    wifilist = []

    cells = wifi.Cell.all('wlan0')

    for cell in cells:
        wifilist.append(cell)

    return wifilist


def FindFromSearchList(ssid):
    wifilist = Search()

    for cell in wifilist:
        if cell.ssid == ssid:
            return cell

    return False


def FindFromSavedList(ssid):
    cell = wifi.Scheme.find('wlan0', ssid)

    if cell:
        return cell

    return False


def Connect(ssid, password=None):
    cell = FindFromSearchList(ssid)

    if cell:
        savedcell = FindFromSavedList(cell.ssid)

        # Already Saved from Setting
        if savedcell:
            savedcell.activate()
            return cell

        # First time to conenct
        else:
            if cell.encrypted:
                if password:
                    scheme = Add(cell, password)

                    try:
                        scheme.activate()

                    # Wrong Password
                    except wifi.exceptions.ConnectionError:
                        Delete(ssid)
                        return False

                    return cell
                else:
                    return False
            else:
                scheme = Add(cell)

                try:
                    scheme.activate()
                except wifi.exceptions.ConnectionError:
                    Delete(ssid)
                    return False

                return cell

    return False


def Add(cell, password=None):
    if not cell:
        return False

    scheme = wifi.Scheme.for_cell('wlan0', cell.ssid, cell, password)
    scheme.save()
    return scheme


def Delete(ssid):
    if not ssid:
        return False

    cell = FindFromSavedList(ssid)

    if cell:
        cell.delete()
        return True

    return False


if __name__ == '__main__':
    # Search WiFi and return WiFi list
    print(Search())
    #
    # # Connect WiFi with password & without password
    # print
    Connect('OpenWiFi')
    cell = FindFromSearchList('Xperia')
    #Add(cell, 'jurejure123')
    #print(Connect('Xperia', 'jurejure123'))
    #
    # # Delete WiFi from auto connect list
    # print
    Delete('Xperia')