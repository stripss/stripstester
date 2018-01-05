#import utils
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
# while True:
#     temp = IRTemperatureSensor().get_value()
#     print(temp)




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

#import hid
import time




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

# import picamera
# import numpy as np
#
# class CameraDevice:
#     def __init__(self, Xres: int, Yres: int):
#         self.Xres = Xres
#         self.Yres = Yres
#         self.img_count = 0
#         #max 20 pictures
#         self.img = np.empty((20, self.Yres, self.Xres, 3), dtype=np.uint8)
#
#         self.camera = picamera.PiCamera()
#         self.set_camera_parameters(flag=False)
#         try:
#             # logger.debug("Starting self test")
#             # self.self_test()
#             pass
#         except:
#             print("Failed to init Camera")
#
#     def close(self):
#         self.camera.close()
#
#     def set_camera_parameters(self, flag=False):
#         if flag:
#             print("Set parameters. Setting iso and exposure time. Wait 2.5 s")
#             self.camera.resolution = (self.Xres, self.Yres)
#             self.camera.framerate = 80
#             self.camera.brightness = 30
#             time.sleep(2)
#             self.camera.iso = 1 # change accordingly
#             time.sleep(1)
#             self.camera.shutter_speed = self.camera.exposure_speed * 3
#             self.camera.exposure_mode = 'off'
#             g = self.camera.awb_gains
#             self.camera.awb_mode = 'off'
#             self.camera.awb_gains = g
#             time.sleep(0.5)
#         else:
#             #self.camera.resolution = (self.Xres, self.Yres)
#             self.camera.framerate = 20
#             self.camera.exposure_mode = 'off'
#             self.camera.shutter_speed = 50000
#             time.sleep(1)
#
#     def take_picture(self):
#         self.camera.capture(self.img[self.img_count,::,::,::], 'rgb', use_video_port=True)
#         self.img_count += 1
#
#     def take_one_picture(self):
#         self.take_picture()
#         return self.img[self.img_count-1,::,::,::]
#
#     def get_picture(self, Idx=0):
#         return self.img[Idx,::,::,::]
#
#     def take_img_to_array_RGB(self, xres=128, yres=80, RGB=0):
#         slika = np.empty([xres, yres, 3], dtype=np.uint8)
#         self.camera.capture(slika, 'rgb')
#         return slika[:, :, RGB]
#
#     def take_img_to_file(self, file_path):
#         time.sleep(1)
#         self.camera.capture(file_path)
#
#     def save_all_imgs_to_file(self):
#         for i in range(self.img_count):
#             self.imSaveRaw3d('/home/pi/Desktop/Picture{}.jpg'.format(i), self.img[i,::,::,::])


import Wifi
import urllib3
import os
import json

if __name__ == '__main__':

    # my_cell = Wifi.Scheme.find_from_wifi_list('GARO-MELN-8e6e')
    # print(my_cell.ssid)
    # print(os.system('sudo ifdown wlan0'))
    # time.sleep(0.5)
    # my_scheme = Wifi.Scheme(my_cell.ssid, '')
    # #my_scheme = WifiScheme('STRIPS_TESTING', 'Kandrse07')
    # print(my_scheme)
    # my_scheme.save()
    # my_scheme.activate()
    # time.sleep(0.5)
    # http = urllib3.PoolManager()
    # r = http.request('GET', '192.168.2.1/v1/info', timeout=3.0)
    # json_response = json.loads(r.data.decode('utf-8'))
    # print(json_response['mac'])

    # import pygame
    # import pygame.camera
    # from pygame.locals import *
    #
    # pygame.init()
    # pygame.camera.init()
    #
    # cam = pygame.camera.Camera("/dev/video0", (1280, 720))
    # #cam.stop()
    # cam.start()
    # image = cam.get_image()
    # pygame.image.save(image,"/home/pi/Desktop/qr.jpg")
    # img = pygame.surfarray.array2d(image)
    # cam.stop()
    # pygame.quit()


    import picamera
    import numpy as np

    camera = picamera.PiCamera()
    print("Prewiev running")
    camera.start_preview()
    time.sleep(1000)
    camera.stop_preview()



# print('start')
# my_camera = CameraDevice(640,480)
# my_camera.camera.start_preview()
# time.sleep(1000)
# my_camera.camera.stop_preview()
# my_camera.close()