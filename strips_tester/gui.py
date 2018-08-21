# -*- coding: utf8 -*-


# !/usr/bin/python

# Kolekcija kniznjic
import tkinter as tk
import os
import FlashThread as Flash
import queue
import threading

import RPi.GPIO as GPIO
import time
import sys
import logging

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger("strips_tester.stm32_loader")
logger = logging.getLogger("strips_tester.flashthread")

logging.warning('Watch out!')  # will print a message to the console

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

# Define global variables
global DIR
global COUNT_PATHFILE
global count
global count_local
global count_local_self
global programming

programming = False
global DATA_PATHFILE

DIR = os.path.dirname(os.path.realpath(__file__))

# Define COUNT variables
COUNT_PATHFILE = DIR + "/count.txt"
count = 0
count_local = 0
count_local_self = 0

GPIO.setup(12, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(40, GPIO.IN, pull_up_down=GPIO.PUD_UP)

GPIO.setup(11, GPIO.OUT)
GPIO.setup(13, GPIO.OUT)
GPIO.setup(15, GPIO.OUT)

GPIO.output(11, GPIO.LOW)
GPIO.output(13, GPIO.LOW)
GPIO.output(15, GPIO.LOW)

class GUI:
    global variant

    def __init__(self,top):
        self.top = top
        self.create_gui()
        GPIO.output(11, GPIO.HIGH)

    def create_gui(self):

        # Inicializacija okna
        self.top.wm_title("GARO Programator")
        self.top.minsize(width=500, height=250)

        # Napis besedila
        self.label_title = tk.Label(self.top, text="Programiranje", font=("Helvetica", 16))
        self.label_title.place(x=10, y=10)

        self.label_subtitle2 = tk.Label(self.top, text="Stanje:")
        self.label_subtitle2.place(x=20, y=100)

        self.label_text1 = tk.Label(self.top, text="Priklopi modul in pritisni 'Flash GARO' oz. postavi modul na ležišče.", justify="left")
        self.label_text1.place(x=20, y=130)

        self.label_text4 = tk.Label(self.top, text="")
        self.label_text4.place(x=10, y=205)

        self.label_text5 = tk.Label(self.top, text="")
        self.label_text5.place(x=10, y=222)

        # Flash gumb
        self.button_flash = tk.Button(self.top, text="Flash GARO", command=Event_button_flash)
        self.button_flash.place(x=340, y=210, width=150, height=30)

        # Copyright
        self.copyright_text = tk.Label(self.top, text="(c) Marcel Jančar, Strip's Lab", justify="right", state="disabled")
        self.copyright_text.place(x=300, y=10)

        self.variable = tk.StringVar(self.top)
        self.variable.set(get_latest_firmware()) # default value

        self.w = tk.OptionMenu(self.top, self.variable, *get_all_firmware(), command=Event_select_firmware)
        self.w.place(x=120, y=50)

        self.label_subtitle3 = tk.Label(self.top, text="Firmware:")
        self.label_subtitle3.place(x=20, y=55)

        self.photo = tk.PhotoImage(file=DIR + "/images/strips.gif")
        self.copyright_img = tk.Label(top, image=self.photo)
        self.copyright_img.image = self.photo
        self.copyright_img.place(x=330, y=25)

def get_latest_firmware():
    latest = get_all_firmware()[0]
    return latest

def get_all_firmware():
    arr = os.listdir(DIR + "/bin")

    return arr




def Event_select_firmware(index):
    if(("mcu" in gui.variable.get())):
        gui.button_flash.config(state="normal")
    else:
        gui.button_flash.config(state="disabled")

    gui.label_text1.config(text="Izbrana '{}' datoteka".format(gui.variable.get()))

    gui.top.update()


#class MyHandlerText(logging.StreamHandler):
#    def __init__(self, textctrl):
#        logging.StreamHandler.__init__(self) # initialize parent
#        self.textctrl = textctrl
#
#    def emit(self, record):
#        msg = self.format(record)
#        self.textctrl.config(text = msg)

def UpdateCount():
    global count
    global count_local
    global count_local_self

    count_local = count_local + 1
    count_local_self = count_local_self + 1

    if os.path.isfile(COUNT_PATHFILE) and os.access(COUNT_PATHFILE, os.R_OK):
        file = open(COUNT_PATHFILE, "r")
        count = file.read()
        count = int(float(count))
        file.close()

        count = count + count_local
        count_local = 0

        file = open(COUNT_PATHFILE, "w")
        file.write(str(count))
        file.close()
    else:
        count = count + 1

        # Make file count.txt
        print("File is missing or is not readable")

    besedilo = "Narejeno: " + str(count)
    gui.label_text4.config(text=besedilo)
    besedilo = "Tvojih: " + str(count_local_self)
    gui.label_text5.config(text=besedilo)


def GetCount():
    global count

    if os.path.isfile(COUNT_PATHFILE):
        # Read existing count value
        if os.access(COUNT_PATHFILE, os.R_OK):
            file = open(COUNT_PATHFILE, "r")
            count = file.read()
            count = int(float(count))
            file.close()

            besedilo = "Narejeno: " + str(count)
            gui.label_text4.config(text=besedilo)
        else:
            print("File exists and is not readable")
    else:
        file = open(COUNT_PATHFILE, "w")
        file.write(str(count))
        file.close()

def Event_button_flash():

    GPIO.output(11, GPIO.LOW)
    GPIO.output(15, GPIO.HIGH)
    GPIO.output(13, GPIO.LOW)

    gui.button_flash.config(state="disabled")
    gui.top.update()

    que = queue.Queue()
    flasher = Flash.STM32M0Flasher(que,18, 22, 3, '/stmConfig.json', 'bin/' + gui.variable.get())

    t = threading.Thread(target=flasher.flash)
    t.Daemon = True
    t.start()

    gui.label_text1.config(text="Programiranje v teku...")
    top.update()

    #for i in range(100):
    #    gui.label_text1.config(text="Programiranje v teku... ({}%)".format(i))
    #    top.update()
    #    time.sleep(0.1)

    t.join()

    success = que.get()

    # Turn off YLED
    GPIO.output(15, GPIO.LOW)

    if success:
        gui.label_text1.config(text="Programiranje uspelo! \nNaložen '{}' program".format(gui.variable.get()))
        GPIO.output(11, GPIO.HIGH)
        UpdateCount()
    else:
        gui.label_text1.config(text="Programiranje ni uspelo. Možni razlogi: \n\n- Preveri povezavo kabla\n- Preveri napajanje modula")
        GPIO.output(13, GPIO.HIGH)
    gui.button_flash.config(state="normal")
    time.sleep(2)

top = tk.Tk()
gui = GUI(top)
GetCount()

#stderrHandler = logging.StreamHandler()  # no arguments => stderr
#logger.addHandler(stderrHandler)
#guiHandler = MyHandlerText(gui.label_text1)
#logger.addHandler(guiHandler)
#logger.setLevel(logging.DEBUG)
#
#logger.debug("sdsadand")

def check_pin():
    global programming

    state = GPIO.input(12)
    state1 = GPIO.input(40)

    #gui.label_text1.config(text="State: {}".format(state))

    if(state == False or state1 == False):
        if(state == False):
            gui.label_title.config(text="Programiranje MEL")

        if(state1 == False):
            gui.label_title.config(text="Programiranje MVC")

        top.update()

        if(programming == False):
            time.sleep(1)
            Event_button_flash()
        programming = True
    else:
        gui.label_title.config(text="Programiranje")
        programming = False


    top.after(10, check_pin)

top.after(10, check_pin)
top.mainloop()