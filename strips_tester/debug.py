import time
import datetime
import json
import threading
import numpy as np
import cv2
import os
import keyboard
import io

try:
    from picamera.array import PiRGBArray
    from picamera import PiCamera

    import pymongo
except Exception:
    pass

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

def recreate_counters():
    myclient = pymongo.MongoClient("mongodb://172.30.129.19:27017/")
    mydb = myclient["stripstester"]

    test_devices_col = mydb['test_device']
    test_info_col = mydb['test_info']
    test_count_col = mydb['test_count']

    for test_device in test_devices_col.find():
        good_count = test_info_col.find({"test_device": test_device['_id'], "result": 1}).count()
        bad_count = test_info_col.find({"test_device": test_device['_id'], "result": 0}).count()

        date_at_midnight = datetime.datetime.combine(datetime.datetime.today().date(), datetime.time(0))

        good_count_today = test_info_col.find({"test_device": test_device['_id'], "result": 1, "datetime": {"$gt": date_at_midnight}}).count()
        bad_count_today = test_info_col.find({"test_device": test_device['_id'], "result": 0, "datetime": {"$gt": date_at_midnight}}).count()

        try:  # Get date of last test
            last_test = test_info_col.find({"test_device": test_device['_id']}).sort('_id', pymongo.DESCENDING).limit(1)[0]
            last_test = last_test['datetime']
        except Exception:  # TN has no data info yet
            last_test = date_at_midnight

        last_test = datetime.datetime.combine(last_test, datetime.time(0))
        today_date = datetime.datetime.combine(last_test, datetime.time(0))

        test_count_col.update_one({'test_device': test_device['_id']},{'$set': {'good': good_count,'bad': bad_count,'good_today': good_count_today,'bad_today': bad_count_today, 'today_date': today_date, 'last_test': last_test}}, True)

    print("Counter database recreation FINISHED.")
    myclient.close()


def rpi_camera_preview():
    # import the necessary packages
    from picamera.array import PiRGBArray
    from picamera import PiCamera
    import time
    import cv2

    # initialize the camera and grab a reference to the raw camera capture
    camera = PiCamera()
    camera.resolution = (640, 480)
    camera.framerate = 32
    #camera.rotation(180)
    rawCapture = PiRGBArray(camera, size=(640, 480))

    # allow the camera to warmup
    time.sleep(0.1)

    # capture frames from the camera
    for frame in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
        # grab the raw NumPy array representing the image, then initialize the timestamp
        # and occupied/unoccupied text
        image = frame.array

        # show the frame
        cv2.imshow("Frame", image)
        key = cv2.waitKey(1) & 0xFF

        # clear the stream in preparation for the next frame
        rawCapture.truncate(0)

        # if the `q` key was pressed, break from the loop
        if key == ord("q"):
            break

def get_by_id(id):
    myclient = pymongo.MongoClient("mongodb://172.30.129.19:27017/")
    mydb = myclient["stripstester"]
    mycol = mydb['test_info']

    print(mycol.find_one({'_id': int(id)}))
    myclient.close()

def main():
    rpi =0
    #recreate_counters()
    #rpi_camera_preview()
    #insert_test_device("ASP-2", 1, 8000, "Aspoeck LED tubular light", "Marcel Jancar", "/img/logos/aspoeck.png")
    #

    visual = Visual()
    if rpi:
        visual.load_image("C:/Users/marcelj/Desktop/masks/img1.jpg")  # Load target image
        #visual.load_mask("/strips_tester_project/strips_tester/configs/00000000d1cb1b82_GAHF/mask/mask.json")  # Load target mask
        #visual.define_mask("/strips_tester_project/strips_tester/configs/00000000d1cb1b82_GAHF/mask/mask.json")
        visual.define_mask("C:/Users/marcelj/Desktop/masks/mask1.json")

        cam_device = PiCamera()
        cam_device.resolution = (640,480)
        cam_device.framerate = 32

        stream = PiRGBArray(cam_device)
        time.sleep(1)

        for frame in cam_device.capture_continuous(stream, format="bgr", use_video_port=False):
            # grab the raw NumPy array representing the image, then initialize the timestamp
            # and occupied/unoccupied text
            image = frame.array
            visual.set_image(image)
            #cv2.imshow("magic", image)
            #cv2.waitKey(1)
            # clear the stream in preparation for the next frame
            stream.truncate(0)

            print(visual.compare_mask(True))

    else:
        visual.load_image("C:/Users/marcelj/Desktop/masks/test.jpg")  # Load target image
        visual.define_mask("C:/Users/marcelj/Desktop/masks/mask8.json")


class Visual:
    def __init__(self):
        self.mask = []
        self.image = None
        self.camera = True
        self.cam_device = None
        self.selected = 0
        self.stream = None
        self.option_selected = 0
        self.option_list = ['h1','s1','v1','h2','s2','v2']
        self.option_command = 0
        self.mask_offset_x = 0
        self.mask_offset_y = 0


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

            if not len(self.mask):
                self.mask.append({'x': self.mask[self.selected]['x'], 'y': self.mask[self.selected]['y'], 'h1': self.mask[self.selected]['h1'], 's1': self.mask[self.selected]['s1'],
                                  'v1': self.mask[self.selected]['v1'], 'h2': self.mask[self.selected]['h2'], 's2': self.mask[self.selected]['s2'], 'v2': self.mask[self.selected]['v2']})  # Append new
                self.selected = len(self.mask) - 1  # Select last one

        except FileNotFoundError:
            pass

    def crop_image(self,x,y,width,height):
        self.image = self.image[y:y+height,x:x+width]

    def get_camera_image(self):
        try:
            self.cam_device.capture(self.stream, format="bgr")
            self.image = self.stream.array
            self.stream.truncate(0)

        except Exception:
            ret, self.image = self.cam_device.read()

    # This tool defines points in
    def define_mask(self, filename):
        print("Mask definition tool - made by Marcel Jancar")
        print("Use WASD to navigate selected point.")
        print("Use + and - to select different points.")
        print("Use N to create new point.")
        print("Use B to delete existing point.")
        print("Use ENTER to save mask.")

        self.load_mask(filename)

        if self.camera:
            try:
                self.cam_device = PiCamera()
                self.cam_device.resolution = (640, 480)
                self.cam_device.framerate = 32

                self.stream = PiRGBArray(self.cam_device)
                time.sleep(0.1)
                print("Found Raspberry PI camera")
            except Exception as e:

                # Override image with camera live
                self.cam_device = cv2.VideoCapture(0)

                print("Found USB camera")
                while not self.cam_device.isOpened():  # try to get the first frame of camera
                    time.sleep(0.1)

            self.get_camera_image()

        if self.image is None:
            print("Image is not defined. Please use load_image or set_image before defining mask.")
            return

        while True:
            if self.camera:
                self.get_camera_image()

            output = self.image.copy()

            mask_min = np.array([self.mask[self.selected]['h1'],self.mask[self.selected]['s1'],self.mask[self.selected]['v1']], np.uint8)
            mask_max = np.array([self.mask[self.selected]['h2'],self.mask[self.selected]['s2'],self.mask[self.selected]['v2']], np.uint8)

            hsv_img = cv2.cvtColor(self.image, cv2.COLOR_BGR2HSV)
            frame_thresh = cv2.bitwise_not(cv2.inRange(hsv_img, mask_min, mask_max))

            cv2.putText(output, str("Selected: {} ({},{},{},{},{},{},{},{}), result: {}%, option: {}" . format(self.selected,
            self.mask[self.selected]['x'],self.mask[self.selected]['y'],self.mask[self.selected]['h1'],self.mask[self.selected]['s1'],self.mask[self.selected]['v1'],
            self.mask[self.selected]['h2'],self.mask[self.selected]['s2'],self.mask[self.selected]['v2'],
            self.compare_mask(True), self.option_list[self.option_selected])), (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (20,200,20), 1, cv2.LINE_AA)

            index = 0
            for point in self.mask:
                if self.detect_point_state(index):
                    color = (0,255,0)
                else:
                    color = (0,0,255)

                if self.selected == index:
                    cv2.circle(output, (point['x'] + self.mask_offset_x, point['y'] + self.mask_offset_y), 2, color, -1)
                    cv2.circle(output, (point['x'] + self.mask_offset_x, point['y'] + self.mask_offset_y), 4, (255,0,0), 1)
                    cv2.putText(output, str(self.detect_point_state(index)), (point['x'] + 10 + self.mask_offset_x, point['y'] + self.mask_offset_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
                else:
                    cv2.circle(output, (point['x'] + self.mask_offset_x, point['y'] + self.mask_offset_y), 2, color, -1)

                index += 1
            cv2.imshow('Image Preview', output)
            cv2.imshow('Image Preview THRESHOLD', frame_thresh)
            cv2.waitKey(1)

            if keyboard.is_pressed('enter'):  # if key 'q' is pressed
                with open(filename, 'w') as outfile:
                    for point in self.mask:
                        point['x'] = point['x'] + self.mask_offset_x
                        point['y'] = point['y'] + self.mask_offset_y

                    self.mask_offset_x = 0
                    self.mask_offset_y = 0

                    json.dump(self.mask, outfile)

                while keyboard.is_pressed('enter'):
                    time.sleep(0.1)

                print("Mask saved to '{}' successfully!" . format(filename))

            if keyboard.is_pressed('w'):  # if key 'q' is pressed
                if self.option_command == 0:
                    if self.mask[self.selected]['y'] > 0:
                        self.mask[self.selected]['y'] -= 1

                if self.option_command == 1:
                    self.mask_offset_y -= 1

                time.sleep(0.01)
            if keyboard.is_pressed('s'):  # if key 'q' is pressed
                if self.option_command == 0:
                    if self.mask[self.selected]['y'] < 480:
                        self.mask[self.selected]['y'] += 1

                if self.option_command == 1:
                    self.mask_offset_y += 1

                time.sleep(0.01)
            if keyboard.is_pressed('a'):  # if key 'q' is pressed
                if self.option_command == 0:
                    if self.mask[self.selected]['x'] > 0:
                        self.mask[self.selected]['x'] -= 1

                if self.option_command == 1:
                    self.mask_offset_x -= 1

                time.sleep(0.01)
            if keyboard.is_pressed('d'):  # if key 'q' is pressed
                if self.option_command == 0:
                    if self.mask[self.selected]['x'] < 640:
                        self.mask[self.selected]['x'] += 1

                if self.option_command == 1:
                    self.mask_offset_x += 1

                time.sleep(0.01)

            if keyboard.is_pressed('k'):  # if key 'q' is pressed
                if self.option_command == 0:
                    self.option_command = 1
                else:
                    self.option_command = 0

                while keyboard.is_pressed('k'):
                    time.sleep(0.1)


            if keyboard.is_pressed('c'):  # if key 'q' is pressed
                self.option_selected += 1

                if self.option_selected == len(self.option_list):
                    self.option_selected = 0

                while keyboard.is_pressed('c'):
                    time.sleep(0.1)



            if keyboard.is_pressed('h'):  # if key 'q' is pressed
                self.mask[self.selected][self.option_list[self.option_selected]] += 1

                if self.mask[self.selected][self.option_list[self.option_selected]] > 255:
                    self.mask[self.selected][self.option_list[self.option_selected]] = 255

            if keyboard.is_pressed('j'):  # if key 'q' is pressed
                self.mask[self.selected][self.option_list[self.option_selected]] -= 1

                if self.mask[self.selected][self.option_list[self.option_selected]] < 0:
                    self.mask[self.selected][self.option_list[self.option_selected]] = 0




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
                self.mask.append({'x': self.mask[self.selected]['x'], 'y': self.mask[self.selected]['y'], 'h1': self.mask[self.selected]['h1'], 's1': self.mask[self.selected]['s1'], 'v1': self.mask[self.selected]['v1'], 'h2': self.mask[self.selected]['h2'], 's2': self.mask[self.selected]['s2'], 'v2': self.mask[self.selected]['v2']})  # Append new
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
    def compare_mask(self, return_percent=False):
        if self.image is None:
            return

        index = 0
        percent = 0
        for point in self.mask:
            if not self.detect_point_state(index):
                #print("Point with index {} at x:{} y:{} is invalid!" . format(index, point['x'] + self.mask_offset_x, point['y'] + self.mask_offset_y))
                if not return_percent:
                    return False

                percent += 1

            index += 1
        if not return_percent:
            return True
        else:
            return round(100 - (percent / len(self.mask)) * 100.0)

    # Detect Region of Interest (or point) if the background is white
    def detect_point_state(self, index):

        x = self.mask[index]['x'] + self.mask_offset_x
        y = self.mask[index]['y'] + self.mask_offset_y

        # Pick up small region of interest
        roi = self.image[y - 3:y+3, x-3:x+3]

        mask_min = np.array([self.mask[index]['h1'], self.mask[index]['s1'], self.mask[index]['v1']], np.uint8)
        mask_max = np.array([self.mask[index]['h2'], self.mask[index]['s2'], self.mask[index]['v2']], np.uint8)

        hsv_img = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        frame_thresh = cv2.bitwise_not(cv2.inRange(hsv_img, mask_min, mask_max))

        # Calculate povprecje barv v ROI
        # Primerjaj z masko in glej threshold
        # Obvezno primerjaj HSV barve!

        state = False

        black = 0
        white = 0

        for yy in range(-3, 3):
            for xx in range(-3, 3):
                pixel = frame_thresh[yy][xx] % 254

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
