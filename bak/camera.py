

import picamera
from time import sleep
from datetime import datetime
import picamera.array
import numpy as np
from matplotlib import pyplot as pp
import time
import json
import os
import picamera
from picamera import PiCamera





# class CameraConfig:
#     def __init__(self):
#         self.res = 50
#         self.Xres = 128
#         self.Yres = 80
#         self.t1 = None
#         self.t2 = None
#         self.thr = 0.8
#         self.Idx = None
#         self.images = None
#         self.dx = None
#         self.dy = None
#         self.interval = 80
#         self.imgNum = 40
#
#     @classmethod
#     def load(cls, file_path):
#         conf = cls()
#         if os.path.exists(file_path):
#             with open(file_path, 'r') as f:
#                 data = json.load(f)
#             conf.res = data['res']
#             conf.Xres = data['Xres']
#             conf.Yres = data['Yres']
#             conf.t1 = data['t1']
#             conf.t1 = data['t2']
#             conf.thr = data['threshold']
#             conf.Idx = data['Idx']
#             conf.images = data['images']
#             conf.interval = data['interval']
#             conf.imgNum = data['image number']
#         return conf
#
#     def save(self, file_path):
#         data = {
#             'res': self.res,
#             'Xres': self.Xres,
#             'Yres': self.Yres,
#             't1': self.t1,
#             't2': self.t2,
#             'threshold': self.thr,
#             'Idx':self.Idx,
#             'images': self.images,
#             'interval': self.interval,
#             'image number':self.imgNum
#         }
#         with open(file_path, 'w') as f:
#             json.dump(data, f)
#
#     def is_complete(self):
#         return self.images is not None and self.t1 is not None and self.t2 is not None
#

class CameraDevice:
    def __init__(self, configFile):
        self.res = 50
        self.Xres = 128
        self.Yres = 80
        self.thr = 0.8
        self.Idx = None
        #self.images = None
        self.dx = None
        self.dy = None
        self.interval = 80
        self.imgNum = 40
        self.load(configFile)
        self.camera = picamera.PiCamera()
        self.set_camera_parameters()
        try:
           self.self_test()
        except:
            print("Failed to init Camera")

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
            self.res = data['res']
            self.Xres = data['Xres']
            self.Yres = data['Yres']
            self.thr = data['threshold']
            self.Idx = data['Idx']
            self.interval = data['interval']
            self.imgNum = data['image number']

    def save(self, file_path):
        data = {
            'res': self.res,
            'Xres': self.Xres,
            'Yres': self.Yres,
            'threshold': self.thr,
            'Idx': self.Idx,
            #'images': self.images,
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

    def set_camera_parameters(self, flag = False):
        if flag:
            self.camera.shutter_speed = self.camera.exposure_speed
            self.camera.exposure_mode = 'off'
            g = self.camera.awb_gains
            self.camera.awb_mode = 'off'
            self.camera.awb_gains = g
            self.camera.resolution = (self.Xres, self.Yres)
            self.camera.framerate = 20
            time.sleep(2)
        else:
            self.camera.resolution = (self.Xres, self.Yres)
            self.camera.framerate = 20
            time.sleep(2)
        # self.camera.iso = 400   #could change in low light

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
        # print(33,img1)
        img1 = self.im_step(img1, 0.6)
        # print(33,img1)
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
        print("first pic")
        time.sleep(1)
        self.camera.capture(slika2, 'rgb', use_video_port=True)
        print("second pic")
        perc, result = self.compare(slika1[:, :, 0], slika2[:, :, 0])
        if result:
            print('Self test done. Pictures match by : %s percent', perc)
            return True
        else:
            print('Self test failed !!!. Pictures match by %s percent', perc)
            return False

    def calibrate(self):
        tx = ty = np.arange(-4, 4 + 1)
        Tx, Ty = np.meshgrid(tx, ty, indexing='xy')

        slika1 = np.empty((self.Xres, self.Yres, 3), dtype=np.uint8)
        slika2 = np.empty((self.Xres, self.Yres, 3), dtype=np.uint8)

        time.sleep(1)
        self.camera.capture(slika1, 'rgb', use_video_port=True)
        print('Calibration in progress. Try to move camera to test, 5s sleep')
        time.sleep(5)
        self.camera.capture(slika2, 'rgb', use_video_port=True)

        matrix = self.rigid_sm(slika1[:, :, 0], slika2[:, :, 0], Tx, Ty)
        m = np.argmax(matrix)
        x = np.mod(m, np.size(tx))
        y = int(np.floor(m / np.size(ty)))
        self.dx = Tx[0, x]
        self.dy = Ty[y, 0]
        print("Calibration done")

    def close(self):
        self.camera.close()

    def take_pictures(self, imgNum=40):
        for i in range(imgNum):
            t1 = datetime.now()
            self.camera.capture(self.img[:, :, :, i], 'rgb', use_video_port=True)
            t2 = datetime.now()
            dt = t2 - t1
            while (dt.microseconds < self.interval):
                t2 = datetime.now()
                dt = t2 - t1
                sleep(0.005)

    def get_pictures(self, Idx=0):
        return

    def run_test(self):
        failed = 0
        for j in range(len(self.Idx)):
            slika1 = np.empty((self.Xres, self.Yres, 3), dtype=np.uint8)
            self.camera.capture(slika1, 'rgb', use_video_port=True)
            pix = 0
            failed = failed + 1
            for i in range(len(self.Idx)):
                x = self.Idx[i]["x"] + self.dx
                y = self.Idx[i]["y"] + self.dy
                b1 = slika1[y, x, 0] >> 7
                if b1 != 0 and i != j:
                    print("Test failed, sequence : %d".format(failed))
                    return False
                elif i == j and b1 == 0:
                    print("Test failed, sequence : %d".format(failed))
                    return False
        return True


    def take_img(self, file_path):
        time.sleep(1)
        self.camera.capture(file_path)





print("Starting ")
mycamera = CameraDevice("/strips_tester_project/garo/cameraConfig.json")
mycamera.calibrate()
mycamera.take_img('/home/pi/Desktop/IdxPictureMesh.jpg')
time.sleep(2)
mycamera.close()
print("Done")

