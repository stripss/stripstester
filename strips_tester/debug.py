import time
import datetime
import json
import threading
import numpy as np
import cv2
import os
import keyboard
import io

def insert_test_device(name, nests, address, description, author, image_link):
    date_of_creation = datetime.datetime.utcnow()
    myclient = pymongo.MongoClient("mongodb://172.30.129.19:27017/")
    mydb = myclient["stripstester"]
    mycol = mydb['test_device']

    if mycol.find_one({'name': name}) is None:  # Test device does not exist
        data = {'name': name,
                'nests': nests,
                'address': address,
                'description': description,
                'author': author,
                'date_of_creation': date_of_creation,
                'worker_id': 1,
                'worker_type': 0,
                'worker_comment': "",
                'status': date_of_creation,
                'client': image_link}
        print("Test device {} is not found in database, so we create one.".format(name))

        mycol.insert_one(data)
    else:
        print("Test device {} is already in database.".format(name))
def get_by_id(id):
    myclient = pymongo.MongoClient("mongodb://172.30.129.19:27017/")
    mydb = myclient["stripstester"]
    mycol = mydb['test_info']

    print(mycol.find_one({'_id': int(id)}))
    myclient.close()

def main():
    # insert_test_device("GAHF", 2, 8000, "GARO Heater fan", "Marcel Jancar", "link_to_img")

    visual = Visual()
    visual.load_image("C:/Users/marcelj/Desktop/StripsTesterProject/strips_tester/test/test2.jpg")  # Load target image
    #visual.load_mask("/strips_tester_project/strips_tester/configs/00000000d1cb1b82_GAHF/mask/mask.json")  # Load target mask
    visual.define_mask("/strips_tester_project/strips_tester/configs/00000000d1cb1b82_GAHF/mask/mask.json", 50)
    #print(visual.compare(50, True))


class Visual:
    def __init__(self):
        self.mask = []
        self.image = None
        self.camera = True
        self.cam_device = None
        self.selected = 0

    def load_image(self, filename):
        if os.path.isfile(filename):
            self.image = cv2.imread(filename)
            self.camera = False
        else:
            print("File '{}' does not exist" . format(filename))

    def set_image(self, image):
        self.image = image

    def load_mask(self, filename):
        self.mask = []

        try:
            input_file = open(filename)
            json_array = json.load(input_file)

            for point in json_array:
                self.mask.append(point)

        except FileNotFoundError:
            pass

    # This tool defines points in
    def define_mask(self, filename, threshold=100):
        print("Mask definition tool - made by Marcel Jancar")
        print("Use WASD to navigate selected point.")
        print("Use + and - to select different points.")
        print("Use N to create new point.")
        print("Use B to delete existing point.")
        print("Use ENTER to save mask.")

        self.load_mask(filename)

        if self.camera:
            # Override image with camera live
            self.cam_device = cv2.VideoCapture(0)

            while not self.cam_device.isOpened():  # try to get the first frame of camera
                time.sleep(0.1)

            ret, self.image = self.cam_device.read()

        if self.image is None:
            print("Image is not defined. Please use load_image or set_image before defining mask.")
            return



        #grayscale = cv2.cvtColor(self.image, cv2.COLOR_RGB2GRAY)  # Grayscale ROI
        #th, dst = cv2.threshold(grayscale, threshold, 255, cv2.THRESH_BINARY)  # Threshold ROI

        while True:
            if self.camera:
                ret, self.image = self.cam_device.read()
                #grayscale = cv2.cvtColor(self.image, cv2.COLOR_RGB2GRAY)  # Grayscale ROI
                #th, dst = cv2.threshold(grayscale, threshold, 255, cv2.THRESH_BINARY)  # Threshold ROI

                ORANGE_MIN = np.array([5, 50, 50], np.uint8)
                ORANGE_MAX = np.array([15, 255, 255], np.uint8)

                hsv_img = cv2.cvtColor(self.image, cv2.COLOR_BGR2HSV)
                dst = cv2.inRange(hsv_img, ORANGE_MIN, ORANGE_MAX)

            output = self.image.copy()

            index = 0
            for point in self.mask:
                if self.detect_point_state(dst, point['x'], point['y']):
                    color = (0,255,0)
                else:
                    color = (0,0,255)

                if self.selected == index:
                    cv2.circle(output, (point['x'], point['y']), 2, color, -1)
                    cv2.circle(output, (point['x'], point['y']), 4, (255,0,0), 1)
                    cv2.putText(output, str(self.detect_point_state(dst, point['x'], point['y'])), (point['x'] + 10, point['y']), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
                else:
                    cv2.circle(output, (point['x'], point['y']), 2, color, -1)

                index += 1

            cv2.putText(output, str("Selected: {}, result: {}%" . format(self.selected, self.compare(threshold, True))), (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200,200,200), 1, cv2.LINE_AA)

            cv2.imshow('Image Preview', output)

            ORANGE_MIN = np.array([5, 50, 50], np.uint8)
            ORANGE_MAX = np.array([15, 255, 255], np.uint8)

            hsv_img = cv2.cvtColor(self.image, cv2.COLOR_BGR2HSV)
            frame_threshed = cv2.inRange(hsv_img, ORANGE_MIN, ORANGE_MAX)
            cv2.imshow('Image Preview THRESHOLD', frame_threshed)
            cv2.waitKey(1)

            if keyboard.is_pressed('enter'):  # if key 'q' is pressed
                with open(filename, 'w') as outfile:
                    json.dump(self.mask, outfile)

                while keyboard.is_pressed('enter'):
                    time.sleep(0.1)

                print("Mask saved to '{}' successfully!" . format(filename))

            if keyboard.is_pressed('w'):  # if key 'q' is pressed
                if self.mask[self.selected]['y'] > 0:
                    self.mask[self.selected]['y'] -= 1

            if keyboard.is_pressed('s'):  # if key 'q' is pressed
                if self.mask[self.selected]['y'] < 480:
                    self.mask[self.selected]['y'] += 1

            if keyboard.is_pressed('a'):  # if key 'q' is pressed
                if self.mask[self.selected]['x'] > 0:
                    self.mask[self.selected]['x'] -= 1

            if keyboard.is_pressed('d'):  # if key 'q' is pressed
                if self.mask[self.selected]['x'] < 640:
                    self.mask[self.selected]['x'] += 1

            if keyboard.is_pressed('+'):  # if key 'q' is pressed
                if self.selected < len(self.mask) - 1:
                    self.selected += 1

                while keyboard.is_pressed('+'):
                    time.sleep(0.1)

            if keyboard.is_pressed('-'):  # if key 'q' is pressed
                if self.selected > 0:
                    self.selected -= 1

                while keyboard.is_pressed('-'):
                    time.sleep(0.1)

            if keyboard.is_pressed('n'):  # if key 'q' is pressed
                self.mask.append({'x': self.mask[self.selected]['x'], 'y': self.mask[self.selected]['y'], 'r': 0, 'g': 0, 'b': 0})  # Append new
                self.selected = len(self.mask) - 1  # Select last one
                print("Point at index {} successfully created." . format(self.selected))

                while keyboard.is_pressed('n'):
                    time.sleep(0.1)

            if keyboard.is_pressed('b'):  # if key 'q' is pressed
                if len(self.mask) > 1:
                    del(self.mask[self.selected])
                    print("Point at index {} successfully deleted." . format(self.selected))
                    self.selected = len(self.mask) - 1  # Select last one

                while keyboard.is_pressed('b'):
                    time.sleep(0.1)

            if keyboard.is_pressed('esc'):  # if key 'q' is pressed
                if self.camera:
                    self.cam_device.release()

                cv2.destroyAllWindows()
                break

    # Use this function if you want to check every point defined in mask. This function returns bool or matching percent
    def compare(self, threshold_value, return_percent=False):
        if self.image is None:
            return

        #grayscale = cv2.cvtColor(self.image, cv2.COLOR_RGB2GRAY)  # Grayscale ROI
        #th, dst = cv2.threshold(grayscale, threshold_value, 255, cv2.THRESH_BINARY)  # Threshold ROI

        ORANGE_MIN = np.array([5, 50, 50], np.uint8)
        ORANGE_MAX = np.array([15, 255, 255], np.uint8)

        hsv_img = cv2.cvtColor(self.image, cv2.COLOR_BGR2HSV)
        dst = cv2.inRange(hsv_img, ORANGE_MIN, ORANGE_MAX)

        index = 0
        percent = 0
        for point in self.mask:
            index += 1

            if not self.detect_point_state(dst, point['x'], point['y']):
                #print("Point with index {} at x:{} y:{} is invalid!" . format(index, point['x'], point['y']))
                if not return_percent:
                    return False

                percent += 1

        if not return_percent:
            return True
        else:
            return round(100 - (percent / len(self.mask)) * 100.0)

    # Detect Region of Interest (or point) if the background is white
    def detect_point_state(self, threshold_img, x, y):

        # Calculate povprecje barv v ROI
        # Primerjaj z masko in glej threshold
        # Obvezno primerjaj HSV barve!

        state = False

        black = 0
        white = 0

        for yy in range(-3, 3):
            for xx in range(-3, 3):
                pixel = threshold_img[y + yy][x + xx] % 254

                if pixel:
                    white += 1
                else:
                    black += 1

        # Return True if there is more white than black
        if white > black:
            state = True

        return state

def print_sticker(test_status, printer):
    program = "S001"

    code = {}
    code['S001'] = 435545
    code['S002'] = 552943
    qc_id = -1

    date = datetime.datetime.now().strftime("%d.%m.%Y")

    if test_status == 1:  # Test OK
        inverse = '^L\n'
        darkness = '^H15\n'
    else:  # Test FAIL
        inverse = '^LI\n'
        darkness = '^H4\n'

    if qc_id != -1:
        qc = "QC {}".format(qc_id)
    else:
        qc = ""

    label = ('^Q9,3\n'
             '^W21\n'
             '{}'
             '^P1\n'
             '^S2\n'
             '^AD\n'
             '^C1\n'
             '^R12\n'
             '~Q+0\n'
             '^O0\n'
             '^D0\n'
             '^E12\n'
             '~R200\n'
             '^XSET,ROTATION,0\n'
             '{}'
             'Dy2-me-dd\n'
             'Th:m:s\n'
             'AA,8,10,1,1,0,0E,ID:{}     {}\n'
             'AA,8,29,1,1,0,0E,C-19_PL_UF_{}\n'
             'AA,8,48,1,1,0,0E,{}  {}\n'
             'E\n').format(darkness, inverse, code[program], " ", program, date, qc)

    print("a")
    printer.send_to_printer(label)
    time.sleep(1)

    # insert_test_device("Photointerrupter", 3, "192.168.88.227", "Interrupt switch", "Marcel Jancar", datetime.datetime.now())

    # arduino = devices.ArduinoSerial('/dev/arduino', baudrate=115200)
    # arduino.write("calibrate")
    # arduino.write("move 20")
    # while True:
    #    time.sleep(1)
    ##arduino.write("servo 3 0")
    # for i in range(10):
    #    arduino.write("servo 3 100")
    #    arduino.write("move 20")
    #    arduino.write("servo 3 0")
    #    arduino.write("move 0")
    #    arduino.write("move 20")
    #    arduino.write("servo 3 100")
    #    arduino.write("move 0")
    # arduino.write("move 20")
    # arduino.write("servo 3 100")
    # arduino.write("move 0")
    # arduino.close()
    '''
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    GPIO.setup(8, GPIO.OUT)
    GPIO.output(8, GPIO.HIGH)
    time.sleep(0.2)
    GPIO.output(8, GPIO.LOW)

    shifter = devices.HEF4094BT(24, 31, 26, 29)
    shifter.reset()

    which = 0
    shifter.set("K10", which)  # Segger SWIM Left
    shifter.set("K12", which)  # Segger RESET Left
    shifter.set("K13", which)  # Segger VCC Left
    shifter.set("K14", which)  # Segger GND Left
    shifter.set("K11", True)  # Segger RESET disable
    shifter.invertShiftOut()

    segger = devices.Segger("/dev/segger")
    segger.select_file("S001")
    print(segger.download())
    GPIO.output(7,GPIO.HIGH)
    segger.close()
    '''
    # insert_test_device("GO-HA-1",2,"127.0.0.1:8000","Gorenje Hall sensor","Marcel Jancar",datetime.datetime.now())
    '''
    a = [2,3,4]
    b = [5,6,7]
    trace1 = Bar(
        x=a,
        y=b,
        name="too")

    trace2 = Bar(
        x=b,
        y=a,
        name="tsd")

    data = [trace1,trace2]

    layout = Layout(
        barmode='group'
    )

    fig = Figure(data=data, layout=layout)

    plot = plotly.offline.plot(fig,filename='grouped-bar.html')
    '''


'''
myclient = pymongo.MongoClient("mongodb://172.30.129.19:27017/")
mydb = myclient["stripstester"]
#print(mydb.list_collection_names())
mycol = mydb['test_info']
mydata = mydb['test_data']

for x in mycol.find():
    print("Found new test: {}" . format(x))

    for y in mydata.find({"test_info": x['_id']}):
        print("  Its data: {}" . format(y))

led_gpio = [40, 37, 38, 35, 36, 33]
GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

# Prepare GPIO list for visual test (left leds, right leds)
for current in led_gpio:
    GPIO.setup(current, GPIO.IN)
while True:
    state_list = []

    for current in range(len(led_gpio)):
        state_list.append(GPIO.input(led_gpio[current]))

        #print("{} -> [{}] {}".format(current, mask[current], state_list[-1]))

    print(state_list)
    time.sleep(0.1)
'''
if __name__ == '__main__':
    main()
