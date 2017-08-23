from __future__ import print_function

import hid
import time


'''
# enumerate USB devices
for d in hid.enumerate():
    keys = list(d.keys())
    keys.sort()
    for key in keys:
        print("%s : %s" % (key, d[key]))
    print()

# try opening a device, then perform write and read

try:
    print("Opening the device")

    h = hid.device()
    vid = 0x0416
    pid = 0x5020
    h.open(0x0416, 0x5020) # TREZOR VendorID/ProductID

    print("Manufacturer: %s" % h.get_manufacturer_string())
    print("Product: %s" % h.get_product_string())
    print("Serial No: %s" % h.get_serial_number_string())

    # enable non-blocking mode
    h.set_nonblocking(1)

    # write some data to the device
    print("Write the data")
    h.write([0, 63, 35, 35] + [0] * 61)

    # wait
    time.sleep(0.05)

    # read back the answer
    print("Read the data")
    while True:
        d = h.read(64)
        if d:
            print(d)
        else:
            break

    print("Closing the device")
    h.close()

except IOError as ex:
    print(ex)
    print("You probably don't have the hard coded device. Update the hid.device line")
    print("in this script with one from the enumeration list output above and try again.")

print("Done")
'''

import picamera
from time import sleep

class Camera:
    def __init__(self):
        self.Xres = 128
        self.Yres = 80
        self.thr = 0.8
        self.Idx = None
        self.interval = 80
        self.imgNum = 20

        self.dx = None
        self.dy = None
        self.imgCount = 0

        self.camera = picamera.PiCamera()

    def start_p(self):
        self.camera.start_preview()

    def stop_p(self):
        self.camera.stop_preview()

    def change_brightness(self, br):
        self.camera.brightness = br

    def set_camera_parameters(self, flag=False):
        if flag:
            #module_logger.debug("Set parameters. Setting iso and exposure time. Wait 2.5 s")
            self.camera.resolution = (self.Xres, self.Yres)
            #self.camera.color_effects = (128, 128)
            self.camera.framerate = 80
            time.sleep(1)
            self.camera.iso = 1 # change accordingly
            time.sleep(1)
            self.camera.shutter_speed = self.camera.exposure_speed * 5
            self.camera.exposure_mode = 'off'
            g = self.camera.awb_gains
            self.camera.awb_mode = 'off'
            self.camera.awb_gains = g
            time.sleep(0.5)
        else:
            self.camera.resolution = (self.Xres, self.Yres)
            self.camera.framerate = 80
            time.sleep(3)



# my_camera = Camera()
#
# my_camera.set_camera_parameters(True)
# my_camera.start_p()
#
#
# my_camera.change_brightness(30)
# sleep(1000)
# my_camera.stop_p()




try:
    print("Opening the device")

    h = hid.device()
    vid = 0x05f9
    pid = 0x2216
    h.open(vid, pid) # TREZOR VendorID/ProductID

    print("Manufacturer: %s" % h.get_manufacturer_string())
    print("Product: %s" % h.get_product_string())
    print("Serial No: %s" % h.get_serial_number_string())

    # enable non-blocking mode
    h.set_nonblocking(1)

    # write some data to the device
    print("Write the data")
    h.write([0, 63, 35, 35] + [0] * 61)

    # wait
    time.sleep(0.05)

    # read back the answer
    print("Read the data")
    while True:
        d = h.read(64)
        if d:
            print(d)
        else:
            print("No data")

        sleep(0.2)

    print("Closing the device")
    h.close()

except IOError as ex:
    print(ex)
    print("You probably don't have the hard coded device. Update the hid.device line")
    print("in this script with one from the enumeration list output above and try again.")

print("Done")
