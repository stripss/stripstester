
import time
import os
import json
import cv2
from collections import OrderedDict
from picamera.array import PiRGBArray
from picamera import PiCamera
global indices
indices = []

def show_live():

    cam = cv2.VideoCapture(0)

    data = load_points("C:/Users/marcelj/Desktop/strips_tester_project_git/strips_tester/configs/000000005e16aa11_MVC2/Mask.json")



    camera = PiCamera()
    camera.resolution = (640, 480)
    camera.framerate = 32
    rawCapture = PiRGBArray(camera, size=(640, 480))




    #print(data)
    for frame in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
        # grab the raw NumPy array representing the image, then initialize the timestamp
        # and occupied/unoccupied text
        img = frame.array

        #ret_val, img = cam.read()

        for i in range(len(data)):
            subdata = data[str(i)]

            for i in range(len(subdata)):
                x_loc = subdata[i]['x']
                y_loc = subdata[i]['y']
                R = subdata[i]['R']
                G = subdata[i]['G']
                B = subdata[i]['B']

                draw_point(img, x_loc, y_loc, 5)

        cv2.imshow('MVC Kalibracija LIVE v1.0', img)

        time.sleep(0.01)
        if cv2.waitKey(1) == 27:
            break  # esc to quit

    cv2.destroyAllWindows()


def main():
    show_live()

def draw_point(img,x,y,size,thickness= 1):

    cv2.line(img, (x - size,y), (x + size, y), (0,255,0), thickness)
    cv2.line(img, (x,y-size), (x , y + size), (0,255,0), thickness)

def load_points(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            data = json.load(f, object_pairs_hook=OrderedDict)
            meshes_dict = data['Meshes']
            Xres = data['Xres']
            Yres = data['Yres']

            return meshes_dict
    else:
        print("FILE NOT EXIST")
        time.sleep(1)


if __name__ == '__main__':
    main()