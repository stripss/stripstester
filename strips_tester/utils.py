#!/usr/bin/python
import logging
import os
import smtplib
import datetime
import pylibdmtx.pylibdmtx as qrlib
import picamera
import time
import hid

module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

def send_email(subject: str='subject', emailText: str='content of email'):
    #module_logger.info(emailText)
    pass
    # SMTP_SERVER = 'smtp.gmail.com'
    # SMTP_PORT = 587
    # GMAIL_USERNAME = 'stripsdomzale.notification@gmail.com'
    # GMAIL_PASSWORD = 'testdevice07' #CAUTION: This is stored in plain text!
    #
    # recipients = []
    # recipients.append('jure.macerll@gmail.com')
    # recipients.append('peterlive@gmail.com')
    # subject = subject
    #
    # emailText = emailText
    # emailText = "" + emailText + ""
    #
    #
    #
    # session = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    # session.ehlo()
    # session.starttls()
    # session.ehlo
    # session.login(GMAIL_USERNAME, GMAIL_PASSWORD)
    #
    # for recipient in recipients:
    #     headers = ["From: " + GMAIL_USERNAME,
    #                "Subject: " + subject,
    #                "To: " + recipient,
    #                "MIME-Version: 1.0",
    #                "Content-Type: text/html"]
    #     headers = "\r\n".join(headers)
    #
    #     session.sendmail(GMAIL_USERNAME, recipient, headers + "\r\n\r\n" + emailText)
    #
    # session.quit()

def get_cpu_serial() -> str:
    # Extract serial from cpuinfo file
    cpuserial = "0000000000000000"
    try:
        f = open('/proc/cpuinfo', 'r')
        for line in f:
            if line[0:6] == 'Serial':
                cpuserial = line[10:26]
        f.close()
    except:
        cpuserial = "ERROR000000000"
    return cpuserial


def decode_qr(img):
    '''
    :param img: for fast decoding, img should only contain area of interest
    :return: decoded serial
    '''
    decoded_data = qrlib.decode(img)
    Decoded =  decoded_data[0] # we only have one data matrix, so we take the first one
    return str(Decoded.data.decode("ascii")) # encoded as ascii


class Camera:
    def __init__(self):
        self.Xres = 640
        self.Yres = 480

        self.camera = picamera.PiCamera()
        self.camera.resolution = (self.Xres, self.Yres)
        self.camera.framerate = 20
        self.camera.exposure_mode = 'off'
        self.camera.shutter_speed = 50000
        time.sleep(1)

    def start_preview(self):
        self.camera.start_preview()

    def stop_preview(self):
        self.camera.stop_preview()

    def change_brightness(self, br):
        self.camera.brightness = br

    def take_img_to_file(self, file_path, video_port):
        time.sleep(1)
        self.camera.capture(file_path, use_video_port=video_port)


#enumerate USB devices
def hid_enumerate(vid=None, pid=None):
    for d in hid.enumerate():
        keys = list(d.keys())
        keys.sort()
        for key in keys:
            print("%s : %s" % (key, d[key]))
        print()

    #enumerate only
    if vid==None or pid==None:
        return

    # try opening a device, then perform write and read
    try:
        print("Opening the device")
        h = hid.device()
        h.open(vid, pid)
        print("Manufacturer: %s", h.get_manufacturer_string())
        print("Product: %s", h.get_product_string())
        print("Serial No: %s", h.get_serial_number_string())
    except:
        print("Faild to open device")
