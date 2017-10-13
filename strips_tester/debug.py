

# def getserial():
#   # Extract serial from cpuinfo file
#   cpuserial = "0000000000000000"
#   try:
#     f = open('/proc/cpuinfo','r')
#     for line in f:
#       if line[0:6]=='Serial':
#         cpuserial = line[10:26]
#     f.close()
#   except:
#     cpuserial = "ERROR000000000"
#
#   return cpuserial


# from __future__ import print_function
#
# import hid
# import time
#

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

# import picamera
# import time
# from fractions import Fraction
#
# class Camera:
#     def __init__(self):
#         self.Xres = 128
#         self.Yres = 80
#         self.thr = 0.8
#         self.Idx = None
#         self.interval = 80
#         self.imgNum = 20
#
#         self.dx = None
#         self.dy = None
#         self.imgCount = 0
#
#         self.camera = picamera.PiCamera()
#
#     def start_preview(self):
#         self.camera.start_preview()
#
#     def stop_preview(self):
#         self.camera.stop_preview()
#
#     def change_brightness(self, br):
#         self.camera.brightness = br
#
#     def take_img_to_file(self, file_path, video_port):
#         time.sleep(1)
#         self.camera.capture(file_path, use_video_port=video_port)
#
#     def set_camera_parameters(self, flag=False):
#         if flag:
#             #module_logger.debug("Set parameters. Setting iso and exposure time. Wait 2.5 s")
#             self.camera.resolution = (self.Xres, self.Yres)
#             #self.camera.color_effects = (128, 128)
#             self.camera.framerate = 80
#             time.sleep(1)
#             self.camera.iso = 1 # change accordingly
#             time.sleep(1)
#             self.camera.shutter_speed = self.camera.exposure_speed * 5
#             self.camera.exposure_mode = 'off'
#             g = self.camera.awb_gains
#             self.camera.awb_mode = 'off'
#             self.camera.awb_gains = g
#             time.sleep(0.5)
#         else:
#             self.camera.resolution = (self.Xres, self.Yres)
#             self.camera.framerate = 80
#             time.sleep(3)
#
#
#
# my_camera = Camera()
#
# #my_camera.set_camera_parameters(True)
# my_camera.start_preview()
# #my_camera.camera.resolution = (640, 480)
# my_camera.camera.exposure_mode = 'off'
# my_camera.camera.framerate = 16
# i = 0
# pic = 0
# time.sleep(2)
# #my_camera.change_brightness(30)
# # my_camera.awb_mode = 'off'
# #my_camera.camera.awb_gains = (Fraction(50, 50), Fraction(50, 50))
# # my_camera.camera.iso = 100
# my_camera.camera.shutter_speed = 50000
# my_camera.camera.exposure_mode = 'off'
# #time.sleep(2)
#
# while True:
#     if i==1:
#         print("exposure speed :", my_camera.camera.exposure_speed)
#         #print("abw_gains ", my_camera.camera.awb_gains)
#         print("iso ", my_camera.camera.iso)
#         print("analog gain",float(my_camera.camera.analog_gain))
#         print("digital gain",float(my_camera.camera.digital_gain))
#         i = 0
#     time.sleep(1)
#     #my_camera.take_img_to_file("/home/pi/Desktop/pic{}.jpg".format(pic), True)
#     i = i + 1
#     pic = pic + 1
# i=0
# for filename in my_camera.camera.capture_continuous('/home/pi/Desktop/img{counter:03d}.jpg', use_video_port=True):
#     print('Captured %s at %s', filename, time.time())
#     if i==10:
#         break;
#     i = i + 1;
#     #time.sleep(0) # wait 5 minutes
# #my_camera.take_img_to_file("/home/pi/Desktop/pic1.jpg")
# #my_camera.change_brightness(30)
# time.sleep(1000)
# my_camera.stop_preview()

# import picamera
#
# camera = picamera.PiCamera()
# camera.resolution = (640, 480)
# camera.start_recording('/home/pi/Desktop/my_video.h264')
# camera.wait_recording(15)
# camera.stop_recording()


# try:
#     print("Opening the device")
#
#     h = hid.device()
#     vid = 0x05f9
#     pid = 0x2216
#     h.open(vid, pid) # TREZOR VendorID/ProductID
#
#     print("Manufacturer: %s" % h.get_manufacturer_string())
#     print("Product: %s" % h.get_product_string())
#     print("Serial No: %s" % h.get_serial_number_string())
#
#     # enable non-blocking mode
#     h.set_nonblocking(1)
#
#     # write some data to the device
#     print("Write the data")
#     h.write([0, 63, 35, 35] + [0] * 61)
#
#     # wait
#     time.sleep(0.05)
#
#     # read back the answer
#     print("Read the data")
#     while True:
#         d = h.read(64)
#         if d:
#             print(d)
#         else:
#             print("No data")
#
#         sleep(0.2)
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


import utils
utils.send_email(subject='success', emailText='first email from test device')
