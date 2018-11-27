


'''

CE JE CONNECTAN in gre nato na LoginPage in se še enkrat prijavi, window freezes
delete tasks when reconnect



'''


from tkinter import *
from tkinter.ttk import *
from tkinter import filedialog

from multiprocessing import Queue

import threading
import socket
import json
import os
import struct
import random
import time
#import utils
import datetime
import platform
import webbrowser
import tkinter.font as tkFont
import pytz
from dateutil import parser

class LoginPage(Frame):
    def __init__(self, parent, controller):
        Frame.__init__(self, parent)

        self.columnconfigure(1, weight=1)
        self.rowconfigure(5, weight=1)
        self.grid(row=0,column=0,sticky="news",padx=20,pady=20)

        self.parent = parent
        self.controller = controller

        self.queue = self.controller.userdata.login_queue
        self.controller.current_frame = "LoginPage"

        self.menu = Menu(self)
        self.controller.config(menu=self.menu)

        self.menu.add_command(label="Vpis",command=lambda: self.controller.switch_frame(LoginPage))
        self.menu.add_command(label="Tester",command=lambda: self.controller.switch_frame(TesterPage))
        self.menu.add_command(label="Nastavitve",command=lambda: self.controller.switch_frame(PropertiesPage))

        self.title = Label(self, text="Prijava v sistem",font=("Calibri", 15,'bold'), padding=(0,0,0,20))
        self.title.grid(row=0, column=0, sticky="news",columnspan=3)

        self.logo = PhotoImage(file=self.controller.userdata.directory + "/images/strips.gif")
        self.copyright_img = Label(self, image=self.logo)
        self.copyright_img.grid(row=0, column=2, sticky=NE)

        self.test_device_label = Label(self, text="Testna naprava:")
        self.test_device_label.grid(row=1, column=0, sticky=W, pady=5)

        variable = StringVar(self)

        test_device_names = []

        for i in range(len(self.controller.userdata.test_devices)):
            test_device_names.append(self.controller.userdata.test_devices[i]['name'])

        self.test_device_option = OptionMenu(self, variable,test_device_names[self.controller.userdata.test_device],*test_device_names,command=self.set_test_device)
        self.test_device_option.grid(row=1, column=1, sticky=W,columnspan=2,padx=20)




        self.test_label = Label(self, text="Tip testiranja:")
        self.test_label.grid(row=2, column=0, sticky=W, pady=5)

        self.variable2 = StringVar(self)

        self.test_type_list = ["Redna proizvodnja", "Kosi iz popravila", "Analiza reklamacije", "Ostalo"]

        self.test_type_option = OptionMenu(self, self.variable2, self.test_type_list[self.controller.userdata.test_num],*self.test_type_list)
        self.test_type_option.grid(row=2, column=1, sticky=W, columnspan=2,padx=20)
        # variable.set(self.controller.userdata.test_devices[0]['name'])  # default value

        self.user_label = Label(self, text="Številka operaterja:")
        self.user_label.grid(row=3, column=0, sticky=W, pady=5)

        self.user_entry = Entry(self, width=10,font=("Calibri", 14))
        self.user_entry.insert(END, self.controller.userdata.id_num)
        self.user_entry.grid(row=3, column=1, sticky=W,padx=20)

        self.user_info = Label(self, text="",foreground="red")
        self.user_info.grid(row=3, column=2, sticky=W, pady=5, padx=20)

        self.login_button = Button(self, text="Prijava",  command=self.userLogin)
        self.login_button.grid(row=4, column=0, pady=20, sticky="nw")

        self.status_label = Label(self, text="")
        self.status_label.grid(row=5, column=0, sticky="nw",columnspan=3)

        self.after(10,self.check_after)

    def set_test_device(self,value):
        i = 0
        for i in range(len(self.controller.userdata.test_devices)):
            if self.controller.userdata.test_devices[i]['name'] == value:
                self.controller.userdata.test_device = i
                break

        if i == len(self.controller.userdata.test_devices):
            print("Invalid TN number")



    def userLogin(self):
        for i in range(len(self.test_type_list)):
            if self.variable2.get() == self.test_type_list[i]:
                self.controller.userdata.test_num = i

        #self.controller.userdata.test_num = self.test_entry.get()
        self.controller.userdata.id_num = self.user_entry.get()

        ok = True

        self.user_info.config(text="")

        if(int(self.controller.userdata.id_num) not in range(0,100)):
            self.user_info.config(text="Napačna identifikacija")
            ok = False

        if ok:
            self.status_label.config(text="Povezujem na {}..." . format(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']),foreground="black")
            self.controller.update()

            try:
                result = self.controller.client.start()

                if not result:
                    self.status_label.config(text="Testna naprava {} ni dosegljiva.".format(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']),foreground="red")
            except Exception as err:
                self.status_label.config(text="Napaka pri povezovanju! ({}).".format(err), foreground="red")

    # Check after je uporabljen za posodobitev LoginPage
    def check_after(self):
        self.after(10,self.check_after)

        if not self.queue.empty(): # something is in the queue
            msg = self.queue.get()
            print("Login: {}" . format(msg))

            if "tester_init" in msg:
                if msg['tester_init']['id'] == -1:
                    self.status_label.config(text="Uporabnik z identifikacijo '{}' že obstaja na trenutni testni napravi!".format(self.controller.userdata.id_num),foreground="red")
                else:
                    self.controller.switch_frame(TesterPage)

            if "disconnect" in msg:
                self.status_label.config(text="Povezava s testno napravo prekinjena! ({})".format(msg['disconnect']), foreground="red")


class TesterPage(Frame):
    def __init__(self, parent, controller):
        Frame.__init__(self, parent)

        self.parent = parent
        self.controller = controller

        self.queue = self.controller.userdata.tester_queue
        self.controller.current_frame = "TesterPage"

        self.columnconfigure(1, weight=1)
        self.rowconfigure(3, weight=1)
        self.grid(row=0,column=0,sticky="news",padx=20,pady=20)

        self.menu = Menu(self)
        self.controller.config(menu=self.menu)

        self.menu.add_command(label="Vpis",command=lambda: self.controller.switch_frame(LoginPage))
        self.menu.add_command(label="Tester")
        self.menu.add_command(label="Nastavitve",command=lambda: self.controller.switch_frame(PropertiesPage))

        self.lbl0 = Label(self, text="Operativni uporabniški vmesnik",font=("Calibri", 16,'bold'), padding=(0,0,0,20))
        self.lbl0.grid(row=0, column=0, sticky="nw",columnspan=2)

        self.logo = PhotoImage(file=self.controller.userdata.directory + "/images/strips.gif")
        self.copyright_img = Label(self, image=self.logo)
        self.copyright_img.grid(row=0, column=3, sticky=NE)

        self.after(10,self.check_after)


        if self.controller.userdata.tester_init:
            self.show_gui()
        else:
            self.error = Label(self, text="Ni povezave s testno napravo.", padding=(0,0,0,20))
            self.error.grid(row=1,column=0,sticky="news")

    def show_gui(self):
        self.sep = []

        # Display information frame (ID, type of test, TN information)
        self.display_info_frame()

        self.lbl2 = Label(self, text="FAZA TESTIRANJA",font=("Calibri", 15,'bold'))
        self.lbl2.grid(row=2,column=0,sticky="w",pady=10)

        self.task_frame = Frame(self)
        self.task_frame.grid(row=3,column=0,sticky="news")
        #self.task_frame.config(borderwidth=2, relief="groove")
        self.show_tasks()

        self.lbl3 = Label(self, text="INFORMACIJE",font=("Calibri", 15,'bold'))
        self.lbl3.grid(row=2,column=1,sticky="w",pady=10)

        self.messager_frame = Frame(self)
        self.messager_frame.grid(row=3, column=1, sticky="news", padx=5, rowspan=4)
        self.messager_frame.columnconfigure(0, weight=1)
        self.messager_frame.rowconfigure(0, weight=1)

        self.txt = Text(self.messager_frame)
        self.txt.tag_config('red', foreground="red")
        self.txt.tag_config('green', foreground="green")
        self.txt.tag_config('yellow', foreground="#c99c22")
        self.txt.tag_config('blue', foreground="blue")
        self.txt.tag_config('purple', foreground="magenta")
        self.txt.tag_config('black', foreground="black")
        self.txt.tag_config('grey', foreground="grey")
        self.txt.grid(row=0,column=0,sticky="news")
        self.txt.config(state="disabled")

        self.scrollbar = Scrollbar(self.messager_frame,command=self.txt.yview)
        self.scrollbar.grid(row=0,column=1,sticky="ns")
        self.txt['yscrollcommand'] = self.scrollbar.set

        self.show_messages()

        self.lbl4 = Label(self, text="DODATNO",font=("Calibri", 15,'bold'),anchor="w")
        self.lbl4.grid(row=2,column=3,sticky="w",pady=10)

        if self.controller.userdata.result == "ok":
            self.task_result = Label(self, text="TEST OK", borderwidth=2, relief="groove", justify="center", padding=(20, 10, 20, 10),background="#00ba06")
        elif self.controller.userdata.result == "fail":
            self.task_result = Label(self, text="TEST FAIL", borderwidth=2, relief="groove", justify="center", padding=(20, 10, 20, 10),background="#e01a00")
        elif self.controller.userdata.result == "work":
            self.task_result = Label(self, text="TESTIRANJE V TEKU", borderwidth=2, relief="groove", justify="center", padding=(20, 10, 20, 10), background="#0059ea")
        elif self.controller.userdata.result == "maintenance":
            self.task_result = Label(self, text="VZDRŽEVANJE", borderwidth=2, relief="groove", justify="center", padding=(20, 10, 20, 10), background="#e2df00")
        else:
            self.task_result = Label(self, text="PRIPRAVLJEN", borderwidth=2, relief="groove", justify="center", padding=(20, 10, 20, 10), background="gray")

        self.task_result.grid(row=5,column=0, pady=5, padx=5, sticky="wes")



        self.time_frame = Frame(self)
        self.time_frame.columnconfigure(0, weight=1)
        self.time_frame.grid(row=4,column=0,sticky="nw")
        self.test_time_label = Label(self.time_frame, text="",font=("Calibri", 11))
        self.test_time_label.grid(row=0,column=0, pady=5, padx=10, sticky="wes")





        self.button_frame = Frame(self)
        self.button_frame.columnconfigure(0, weight=1)
        self.button_frame.grid(row=6,column=0,sticky="news")

        self.stop = Button(self.button_frame, text="STOP",command=self.stop_test_device)
        self.stop.grid(row=0, column=0, pady=10, padx=10, sticky="we")

        self.start = Button(self.button_frame, text="START",command=self.start_test_device)
        self.start.grid(row=0, column=1, pady=10, padx=10, sticky="we")

        if self.controller.userdata.master != self.controller.userdata.id_num:
            self.start.config(state="disabled")

        self.stats_frame = Frame(self)
        self.stats_frame.grid(row=3,column=3,sticky="nw",rowspan=3)
        self.rowconfigure(3, weight=1)

        self.other_frame = Frame(self)
        self.other_frame.grid(row=3,column=4,sticky="nw",rowspan=3)

        self.display_stats_frame()
        self.display_custom_attr()

        if self.controller.userdata.tester_init:
            if self.controller.userdata.path_manual:
                self.display_manual()

            self.display_shutdown()
            self.display_ping()

    def shutdown(self):
        # izklop TN

        self.controller.client.send({'shutdown': 'true'})

    def show_tasks(self):  # Show tasks when GUI init
        for task_number in range(self.controller.userdata.num_of_tasks):
            self.controller.userdata.task[task_number]['show'] = False

            self.make_task(task_number)

    def display_info_frame(self):
        self.test_type_list = ["Redna proizvodnja", "Kosi iz popravila", "Analiza reklamacije", "Ostalo"]

        self.info_frame = Frame(self)
        self.info_frame.grid(row=1, column=0, sticky="news",columnspan=3)

        self.lbl1 = Label(self.info_frame, text="Identifikacija: {}\nTip testiranja: {}".format(self.controller.userdata.id_num, self.test_type_list[self.controller.userdata.test_num]))
        self.lbl1.grid(row=1, column=0, sticky="news")

        # Not implemented yet.
        self.info_frame_extra_text = Label(self.info_frame, text="")
        self.info_frame_extra_text.grid(row=1, column=1, sticky="news",padx=20)

    def display_custom_attr(self):
        self.custom_attr_frame = Frame(self.stats_frame)
        self.custom_attr_frame.grid(row=2, column=0, sticky="nw")

        if self.controller.userdata.esd:
            self.esd_logo = PhotoImage(file=self.controller.userdata.directory + "/images/esd.gif")
            self.esd_logo = self.esd_logo.subsample(2,2)
            self.esd_image = Label(self.custom_attr_frame, image=self.esd_logo)
            self.esd_image.grid(row=0, column=0, sticky="nw", padx=5)

            self.esd_label = Label(self.custom_attr_frame, text="Obvezna uporaba ESD opreme.")
            self.esd_label.grid(row=0, column=1, sticky="new", pady=10)

        if self.controller.userdata.high_voltage:
            self.hv_logo = PhotoImage(file=self.controller.userdata.directory + "/images/hv.gif")
            self.hv_logo = self.hv_logo.subsample(2,2)
            self.hv_image = Label(self.custom_attr_frame, image=self.hv_logo)
            self.hv_image.grid(row=1, column=0, sticky="nw", padx=5)

            self.hv_label = Label(self.custom_attr_frame, text="Prisotnost visoke napetosti.")
            self.hv_label.grid(row=1, column=1, sticky="new", pady=10)

    def display_shutdown(self):
        self.shutdown_frame = Frame(self.stats_frame)
        self.shutdown_frame.grid(row=3, column=0, sticky="nw")

        self.shutdown_label = Label(self.shutdown_frame, text="IZKLOP", font=("Calibri", 15,'bold'))
        self.shutdown_label.grid(row=0, column=0, sticky="w", pady=5)

        self.shutdown_button = Button(self.shutdown_frame, text="Izklopi testno napravo",  command=self.shutdown)
        self.shutdown_button.grid(row=1, column=0, pady=5, sticky=W)

        if self.controller.userdata.master != self.controller.userdata.id_num:
            self.shutdown_button.config(state="disabled")


    def display_ping(self):
        self.ping_frame = Frame(self.stats_frame)
        self.ping_frame.grid(row=4, column=0, sticky="new")

        self.ping_label = Label(self.ping_frame, text="PING", font=("Calibri", 15,'bold'))
        self.ping_label.grid(row=0, column=0, sticky="w")

        self.ping_text = Label(self.ping_frame, text="{}ms" . format(int(self.controller.userdata.ping)))
        self.ping_text.grid(row=1, column=0, pady=5, sticky=W)

    def display_manual(self):
        self.manual_frame = Frame(self.other_frame)
        self.manual_frame.grid(row=1, column=0, sticky="new",padx=10)
        #self.manual_frame.columnconfigure(1, weight=1)
        #self.log_frame.rowconfigure(0, weight=1)

        self.manual_label = Label(self.manual_frame, text="NAVODILA ZA UPORABO", font=("Calibri", 15,'bold'))
        self.manual_label.grid(row=0, column=0, sticky="w", pady=10)

        self.log_label = Label(self.manual_frame, text="Navodila za uporabo testne naprave\n{} so dostopna na spodnji povezavi:" . format(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']))
        self.log_label.grid(row=1, column=0, sticky="w", pady=5)

        self.log_link = Label(self.manual_frame, text="Navodila za uporabo {}" . format(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']), foreground="blue", cursor="hand2")
        self.log_link.bind("<Button-1>", self.show_manual)
        self.log_link.grid(row=2, column=0, sticky="w", pady=5)


    def display_stats_frame(self):
        self.labelframe = LabelFrame(self.stats_frame, text="Statistika")
        self.labelframe.grid(row=0,column=0,sticky="news",padx=5)
        self.labelframe.config(borderwidth=2,relief="groove")
        self.labelframe.columnconfigure(0,weight=1)

        self.sublabelframe = Frame(self.labelframe)
        self.sublabelframe.grid(row=0,column=0,sticky="news", padx=10, pady=5)
        self.sublabelframe.columnconfigure(0,weight=1)

        localdate = pytz.utc.localize(self.controller.userdata.countdate).astimezone(pytz.timezone('Europe/Ljubljana'))

        self.sublabelframe_countdate = Label(self.sublabelframe, text="Serija: {}" . format(datetime.datetime.strftime(localdate,"%d.%m.%Y ob %H:%M:%S")))
        self.sublabelframe_countdate.grid(row=0, column=0, sticky="new",columnspan=2)

        self.sublabelframe_left_label = Label(self.sublabelframe, text="Tvoji:")
        self.sublabelframe_left_label.grid(row=1, column=0, sticky="new",pady=5)

        self.good_local_label = Label(self.sublabelframe, text="Dobri: {}".format(self.controller.userdata.good_count))
        self.good_local_label.grid(row=2, column=0, sticky="w")

        self.bad_local_label = Label(self.sublabelframe, text="Slabi: {}".format(self.controller.userdata.bad_count))
        self.bad_local_label.grid(row=3, column=0, sticky="w")

        self.sum_local_label = Label(self.sublabelframe, text="Skupaj: {}".format(self.controller.userdata.bad_count + self.controller.userdata.good_count))
        self.sum_local_label.grid(row=4, column=0, sticky="w")

        if self.controller.userdata.good_count or self.controller.userdata.bad_count:
            success = (self.controller.userdata.good_count / (self.controller.userdata.bad_count + self.controller.userdata.good_count)) * 100
            self.success_local = "Uspešnost: {0:.1f}%" . format(success)

            if success > 95:
                bg_color = "green"
            elif success > 90:
                bg_color = "#c99c22"
            else:
                bg_color = "red"
        else:
            self.success_local = "Uspešnost: N/A"
            bg_color = "black"

        self.suc_local_label = Label(self.sublabelframe, text=self.success_local, foreground=bg_color)
        self.suc_local_label.grid(row=5, column=0, sticky="w",pady=5)

        self.sublabelframe_right_label = Label(self.sublabelframe, text="Globalno:")
        self.sublabelframe_right_label.grid(row=1, column=1, sticky="new",padx=20,pady=5)

        self.good_global_label = Label(self.sublabelframe, text="Dobri: {}".format(self.controller.userdata.global_good_count))
        self.good_global_label.grid(row=2, column=1, sticky="w",padx=20)

        self.bad_global_label = Label(self.sublabelframe, text="Slabi: {}".format(self.controller.userdata.global_bad_count))
        self.bad_global_label.grid(row=3, column=1, sticky="w",padx=20)

        self.sum_global_label = Label(self.sublabelframe, text="Skupaj: {}".format(self.controller.userdata.global_bad_count + self.controller.userdata.global_good_count))
        self.sum_global_label.grid(row=4, column=1, sticky="w",padx=20)

        if self.controller.userdata.global_good_count or self.controller.userdata.global_bad_count:
            success = (self.controller.userdata.global_good_count / (self.controller.userdata.global_bad_count + self.controller.userdata.global_good_count)) * 100
            self.success_global = "Uspešnost: {0:.1f}%" . format(success)

            if success > 95:
                bg_color = "green"
            elif success > 90:
                bg_color = "#c99c22"
            else:
                bg_color = "red"
        else:
            self.success_global = "Uspešnost: N/A"
            bg_color = "black"

        self.suc_global_label = Label(self.sublabelframe, text=self.success_global, foreground=bg_color)
        self.suc_global_label.grid(row=5, column=1, sticky="w",padx=20,pady=5)



        self.test_count_reset_button = Button(self.sublabelframe, text="Ponastavi števec", command=self.reset_test_count)
        self.test_count_reset_button.grid(row=6, column=0, pady=5, sticky=W,columnspan=2)



        self.labelframe2 = LabelFrame(self.stats_frame, text="Servis in kalibracija")
        self.labelframe2.grid(row=1,column=0,sticky="new",padx=5,pady=10)
        self.labelframe2.config(borderwidth=2,relief="groove")

        self.lbl8 = Label(self.labelframe2, text="Št. ciklov do servisa: {}".format(self.controller.userdata.service))
        self.lbl8.grid(row=2, column=0, sticky=NW, padx=10, pady=5)

        self.cal_label = Label(self.labelframe2, text="Kalibracija: {}" . format(datetime.datetime.strftime(self.controller.userdata.calibrationdate,"%d.%m.%Y")))
        self.cal_label.grid(row=3, column=0, sticky=NW, padx=10, pady=5)



    def reset_test_count(self):
        # send server to reset counter
        countdate = datetime.datetime.utcnow()

        self.controller.client.send({'set_count': countdate})

        #self.test_count_reset_label.config(text="Ponastavljeno.", foreground="green")
        #self.test_count_reset_label.grid(row=4, column=0, sticky="w", padx=10,columnspan=5)



    def make_task(self,task_number):  # Show new task when GUI active
        if self.controller.userdata.task[task_number]['show'] == False:
            self.controller.userdata.task[task_number]['show'] = True

            fg_color = "black"
            if self.controller.userdata.task[task_number]['task_enable'].get():
                if self.controller.userdata.task[task_number]['task_state'] == "fail":
                    bg_color = "#e01a00"
                elif self.controller.userdata.task[task_number]['task_state'] == "ok":
                    bg_color = "#00ba06"
                elif self.controller.userdata.task[task_number]['task_state'] == "work":
                    bg_color = "#0059ea"
                else:
                    bg_color = "grey"
            else:
                bg_color = "#cccccc"
                fg_color = "gray"

            task_name = self.controller.userdata.task[task_number]['task_name']

            extra_info = ""
            for definition_number in range(self.controller.userdata.num_of_definitions):
                if self.controller.userdata.definition[definition_number]['definition_task'] == self.controller.userdata.task[task_number]['task_slug'] and len(self.controller.userdata.definition[definition_number]['definition_extra_info']):

                    # update task here and on gui
                    definition_extra_info = self.controller.userdata.definition[definition_number]['definition_extra_info']
                    start_pos = definition_extra_info.find("[D]")

                    if start_pos != -1:
                        definition_extra_info = definition_extra_info[:start_pos] + str(self.controller.userdata.definition[definition_number]['definition_value'].get()) + definition_extra_info[start_pos + 4:]

                    extra_info = extra_info + definition_extra_info + "\n"


            self.task_frame.columnconfigure(0, weight=1)

            self.sep.append({})

            self.sep[task_number]['frame'] = Frame(self.task_frame)
            self.sep[task_number]['frame'].grid(row=task_number + 1, column=0, padx=5,sticky="new")
            self.sep[task_number]['frame'].columnconfigure(0,weight=1)
            #self.sep[task_number]['frame'].rowconfigure(task_number + 1,weight=1)


            self.sep[task_number]['label'] = Label(self.sep[task_number]['frame'], text=task_name, borderwidth=2, relief="groove",justify="center",padding=(30, 10, 30, 10),background=bg_color,foreground=fg_color)
            self.sep[task_number]['label'].grid(row=0, column=0,sticky="we",pady=5)

            self.sep[task_number]['info'] = Label(self.sep[task_number]['frame'],text=extra_info,font=("Calibri", 11))

            if len(extra_info):
                self.sep[task_number]['info'].grid(row=1, column=0,sticky="we",padx=10)

            #self.sep.append(Label(self.task_frame, text=task_name, borderwidth=2, relief="groove",justify="center",padding=(30, 10, 30, 10),background=bg_color,foreground=fg_color))
            #self.sep[task_number].grid(row=task_number, column=0, pady=5, padx=5,sticky="we")

    def update_task(self,task_slug):  # Update task when GUI active
        self.task_number = self.get_task_number(task_slug)

        fg_color = "black"
        if self.controller.userdata.task[self.task_number]['task_enable'].get():
            if self.controller.userdata.task[self.task_number]['task_state'] == "fail":
                bg_color = "#e01a00"
            elif self.controller.userdata.task[self.task_number]['task_state'] == "ok":
                bg_color = "#00ba06"
            elif self.controller.userdata.task[self.task_number]['task_state'] == "work":
                bg_color = "#0059ea"
            else:
                bg_color = "grey"
        else:
            bg_color = "#cccccc"
            fg_color = "gray"

        task_name = self.controller.userdata.task[self.task_number]['task_name']
        extra_info = ""

        for definition_number in range(self.controller.userdata.num_of_definitions):
            if self.controller.userdata.definition[definition_number]['definition_task'] == task_slug and len(self.controller.userdata.definition[definition_number]['definition_extra_info']):

                # update task here and on gui
                definition_extra_info = self.controller.userdata.definition[definition_number]['definition_extra_info']
                start_pos = definition_extra_info.find("[D]")

                if start_pos != -1:
                    definition_extra_info = definition_extra_info[:start_pos] + str(self.controller.userdata.definition[definition_number]['definition_value'].get()) + definition_extra_info[start_pos + 4:]

                extra_info = extra_info + definition_extra_info + "\n"


        self.sep[self.task_number]['label'].config(text=task_name,background=bg_color,foreground=fg_color)

        if len(extra_info):
            self.sep[self.task_number]['info'].config(text=extra_info)
            self.sep[self.task_number]['info'].grid(row=1, column=0,sticky="we",padx=10)
        else:
            self.sep[self.task_number]['info'].grid_forget()

    def show_messages(self): # Shows all when GUI init
        for message_number in range(len(self.controller.userdata.messager)):
            self.controller.userdata.messager[message_number]['show'] = False

            self.make_message(message_number)

    def make_message(self,message_number): # Shows when GUI running
        if self.controller.userdata.messager[message_number]['show'] == False:
            self.controller.userdata.messager[message_number]['show'] = True

            self.txt.configure(state='normal')
            self.txt.insert(END, self.controller.userdata.messager[message_number]['text'], self.controller.userdata.messager[message_number]['tag'])
            self.txt.configure(state='disabled')
            self.txt.see("end")


    # Check after je uporabljen za posodobitev live testerja
    def check_after(self):
        self.after(10,self.check_after)

        #print(self.queue.qsize())
        if not self.queue.empty(): # something is in the queue
            msg = self.queue.get()

            if "tester_init" in msg: #enable tester page -> controlled by client (TN)!
                id = msg['tester_init']['id']

                if id == -1:
                    print("DUPLICATE with id: {}" . format(self.controller.userdata.id_num))
                else:
                    self.show_gui()

            if "text" in msg: # new text
                self.make_message(msg['text']['text_number'])

            if "task" in msg: #create new task, pridejo za tester_init
                self.make_task(msg['task']['task_number'])

            if "task_update" in msg:
                self.task_slug = msg['task_update']['task_slug']
                self.update_task(self.task_slug)

            if "definition" in msg: #create new task, pridejo za tester_init
                self.task_slug = msg['definition']['definition_task']

                self.update_task(self.task_slug)

            if "definition_update" in msg:
                self.task_slug = msg['definition_update']['definition_task']
                self.update_task(self.task_slug)

            if "task_result" in msg:
                self.controller.userdata.result = msg['task_result']

                if self.controller.userdata.result == "fail":
                    self.task_result.config(text="TEST FAIL",background="#e01a00")
                elif self.controller.userdata.result == "ok":
                    self.task_result.config(text="TEST OK",background="#00ba06")
                elif self.controller.userdata.result == "work":
                    self.task_result.config(text="TESTIRANJE V TEKU",background="#0059ea")
                elif self.controller.userdata.result == "maintenance":
                    self.task_result.config(text="VZDRŽEVANJE",background="#e2df00")
                else:
                    self.task_result.config(text="PRIPRAVLJEN",background="grey")


            if "count" in msg:
                if "countdate" in msg["count"]:
                    countdate = parser.parse(msg['count']['countdate'])
                    localdate = pytz.utc.localize(countdate).astimezone(pytz.timezone('Europe/Ljubljana'))
                    print("Countdate: {}" . format(countdate))
                    print("Local: {}" . format(localdate))
                    self.sublabelframe_countdate.config(text="Serija: {}".format(datetime.datetime.strftime(localdate,"%d.%m.%Y ob %H:%M:%S")))

                self.good_local_label.config(text="Dobri: {}".format(msg['count']['good']))
                self.bad_local_label.config(text="Slabi: {}".format(msg['count']['bad']))
                self.sum_local_label.config(text="Skupaj: {}".format(msg['count']['good'] + msg['count']['bad']))

                if msg['count']['good'] or msg['count']['bad']:
                    success = (msg['count']['good'] / (msg['count']['bad'] + msg['count']['good'])) * 100
                    self.success_local = "Uspešnost: {0:.1f}%".format(success)

                    if success > 95:
                        bg_color = "green"
                    elif success > 90:
                        bg_color = "#c99c22"
                    else:
                        bg_color = "red"
                else:
                    self.success_local = "Uspešnost: N/A"
                    bg_color = "black"

                self.suc_local_label.config(text=self.success_local, foreground=bg_color)

                self.good_global_label.config(text="Dobri: {}".format(msg['count']['good_global']))
                self.bad_global_label.config(text="Slabi: {}".format(msg['count']['bad_global']))
                self.sum_global_label.config(text="Skupaj: {}".format(msg['count']['good_global'] + msg['count']['bad_global']))


                if msg['count']['good_global'] or msg['count']['bad_global']:
                    success = (msg['count']['good_global'] / (msg['count']['bad_global'] + msg['count']['good_global'])) * 100
                    self.success_global = "Uspešnost: {0:.1f}%".format(success)

                    if success > 95:
                        bg_color = "green"
                    elif success > 90:
                        bg_color = "#c99c22"
                    else:
                        bg_color = "red"
                else:
                    self.success_global = "Uspešnost: N/A"
                    bg_color = "black"

                self.suc_global_label.config(text=self.success_global, foreground=bg_color)


            if "service" in msg:
                self.lbl8.config(text="Št. ciklov do servisa: {}".format(self.controller.userdata.service))

            if "calibration" in msg:
                calibrationdate = datetime.datetime.strptime(msg['calibration'], "%Y-%m-%d %H:%M:%S")
                self.cal_label.config(text="Kalibracija: {}".format(datetime.datetime.strftime(calibrationdate, "%d.%m.%Y")))

            if "esd" in msg or "high_voltage" in msg:
                self.display_custom_attr()

            if "ping_answer" in msg:
                self.ping_text.config(text="{}ms" . format(int(self.controller.userdata.ping)))

                # Test time implementation
                if self.controller.userdata.test_time_enable:
                    print("BEFORE")
                    test_time = datetime.datetime.utcnow() - self.controller.userdata.start_test_time
                    print("AFTER")
                    self.test_time_label.config(text="Čas testiranja: {}s" . format(str(test_time)[:-7]))

    def stop_test_device(self):
        self.controller.client.send({'stop_test_device': 'true'})

    def start_test_device(self):
        self.controller.client.send({'start_test_device': 'true'})

    def get_task_number(self,task_slug):

        for task_number in range(self.controller.userdata.num_of_tasks):
            if self.controller.userdata.task[task_number]['task_slug'] == task_slug:
                return task_number

        print("No task with task slug '{}' found." . format(task_slug))
        return None


class PropertiesPage(Frame):
    def __init__(self, parent, controller):
        self.parent = parent
        self.controller = controller

        self.queue = self.controller.userdata.properties_queue

        self.controller.current_frame = "PropertiesPage"

        Frame.__init__(self, parent)

        self.columnconfigure(1, weight=1)
        self.rowconfigure(3, weight=1)
        self.grid(row=0,column=0,sticky="news",padx=20,pady=20)

        self.menu = Menu(self)
        self.controller.config(menu=self.menu)

        self.menu.add_command(label="Vpis",command=lambda: self.controller.switch_frame(LoginPage))
        self.menu.add_command(label="Tester",command=lambda: self.controller.switch_frame(TesterPage))
        self.menu.add_command(label="Nastavitve")

        self.lbl0 = Label(self, text="Nastavitve",font=("Calibri", 15,'bold'), padding=(0,0,0,20))
        self.lbl0.grid(row=0, column=0, sticky="nw")

        self.logo = PhotoImage(file=self.controller.userdata.directory + "/images/strips.gif")
        self.copyright_img = Label(self, image=self.logo)
        self.copyright_img.grid(row=0, column=2, sticky=NE)


        self.task_frame = Frame(self)
        self.task_frame.grid(row=3, column=0, sticky="new")
        self.task_frame.rowconfigure(3,weight=1)

        self.lbl2 = Label(self, text="KONFIGURACIJA", font=("Calibri", 15,'bold'))
        self.lbl2.grid(row=2, column=0, sticky="w", pady=10)

        self.config_frame = Frame(self.task_frame)
        self.config_frame.grid(row=0, column=0, sticky="new")

        self.test_device_label = Label(self.config_frame, text="Testna naprava:")
        self.test_device_label.grid(row=0, column=0, sticky=W, pady=5)

        variable = StringVar(self)
        variable.set(self.controller.userdata.test_devices[self.controller.userdata.prop_test_device])  # default value

        test_device_names = []
        for i in range(len(self.controller.userdata.test_devices)):
            test_device_names.append(self.controller.userdata.test_devices[i]['name'])

        self.test_device_option = OptionMenu(self.config_frame, variable,test_device_names[self.controller.userdata.prop_test_device],*test_device_names,command=self.set_test_device)
        self.test_device_option.grid(row=0, column=1, sticky=W,columnspan=2)



        self.ip = Label(self.config_frame, text="IP naslov:")
        self.ip.grid(row=1, column=0, sticky="w", pady=5)

        self.ip_entry = Entry(self.config_frame, width=20,font=("Calibri", 14))
        self.ip_entry.insert(END, self.controller.userdata.test_devices[self.controller.userdata.test_device]['ip'])
        self.ip_entry.grid(row=1, column=1, sticky="w")

        self.ip = Label(self.config_frame, text="Port:")
        self.ip.grid(row=2, column=0, sticky="w", pady=5)

        self.port_entry = Entry(self.config_frame, width=10,font=("Calibri", 14))
        self.port_entry.insert(END, self.controller.userdata.test_devices[self.controller.userdata.test_device]['port'])
        self.port_entry.grid(row=2, column=1, sticky=W)

        self.save_test_device_button = Button(self.config_frame, text="Shrani testno napravo",  command=self.save_test_device_settings)
        self.save_test_device_button.grid(row=3, column=0, pady=10, sticky=W,columnspan=2)


        if self.controller.userdata.tester_init:
            self.display_log()

            if self.controller.userdata.path_manual:
                self.display_manual()

            self.display_shutdown()
        self.display_logoff()


        self.lbl3 = Label(self, text="TESTNA NAPRAVA", font=("Calibri", 15,'bold'))
        self.lbl3.grid(row=2, column=1, sticky="w", pady=10)

        self.lbl4 = Label(self, text="OSTALO", font=("Calibri", 15,'bold'))
        self.lbl4.grid(row=2, column=2, sticky="w", pady=10)

        self.test_device_frame = Frame(self)
        self.test_device_frame.grid(row=3, column=1, sticky="news",padx=10,rowspan=2)
        self.test_device_frame.columnconfigure(0, weight=1)
        self.test_device_frame.rowconfigure(1, weight=1)



        if self.controller.userdata.tester_init:

            self.canvas = Canvas(self.test_device_frame)
            self.canvas.grid(row=1, column=0, sticky="news")
            self.canvas.columnconfigure(0, weight=1)

            self.test_device_frame_inner = Frame(self.canvas)
            self.canvas_frame = self.canvas.create_window((0, 0), window=self.test_device_frame_inner, anchor="nw")

            self.scrollbar = Scrollbar(self.canvas, orient="vertical", command=self.canvas.yview)
            self.scrollbar.pack(side=RIGHT, fill=Y)
            self.canvas['yscrollcommand'] = self.scrollbar.set
            #self.canvas.config(borderwidth=2, relief="groove")

            self.test_device_frame_inner.bind("<Configure>", self.onFrameConfigure)
            self.canvas.bind('<Configure>', self.FrameWidth)


            self.sep = []

            self.aa = Label(self.test_device_frame, text="Trenutno povezan na: {}\n\nSeznam nalog:".format(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']))
            self.aa.grid(row=0, column=0, sticky="new", pady=5,columnspan=2)

            self.show_tasks()

            self.sep[task_number]['frame'] = Frame(self.test_device_frame_inner)
            self.sep[task_number]['frame'].grid(row=task_number + 1, column=0, pady=5, padx=5,sticky="we")
            self.sep[task_number]['frame'].columnconfigure(3,weight=1)
            self.sep[task_number]['frame'].rowconfigure(task_number + 1,weight=1)


            # show only if tasks are there
            self.save_task_settings_button = Button(self.test_device_frame, text="Shrani nastavitve nalog", command=self.save_task_settings)
            self.save_task_settings_button.grid(row=2, column=0, pady=10, sticky=W)

            self.save_task_settings_label = Label(self.test_device_frame, text="")

            self.after(10, self.check_after)
        else:
            self.aa = Label(self.test_device_frame, text="Trenutno nisi povezan na nobeno testno napravo.")
            self.aa.grid(row=0, column=0, sticky="nw", pady=5)

        self.right_frame = Frame(self)
        self.right_frame.grid(row=3, column=2, sticky="news")


        if self.controller.userdata.tester_init:
            self.display_stats()

            self.display_factory_reset()



        #self.startBtn = Button(self, text="Tovarniške nastavitve", command=self.factory_reset)
        #self.startBtn.grid(row=2, column=0, pady=20, sticky=W)

        #self.startBtn = Button(self, text="Shrani",  command=self.save)
        #self.startBtn.grid(row=3, column=0, pady=5, sticky=W)


        self.after(10, self.redirect)

    def FrameWidth(self, event):
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_frame, width = canvas_width)

    def onFrameConfigure(self, event):
        '''Reset the scroll region to encompass the inner frame'''
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def display_stats(self):
        self.stats_frame = Frame(self.right_frame)
        self.stats_frame.grid(row=0, column=0, sticky="news")

        self.stats_title = Label(self.stats_frame, text="STATISTIKA", font=("Calibri", 15, 'bold'), anchor="w")
        self.stats_title.grid(row=0, column=0, sticky="w", pady=10)

        self.labelframe = LabelFrame(self.stats_frame, text="Števec")
        self.labelframe.grid(row=1, column=0, sticky="new", padx=5)
        self.labelframe.config(borderwidth=2, relief="groove")

        self.labelframe2 = LabelFrame(self.stats_frame, text="Servis in kalibracija")
        self.labelframe2.grid(row=2, column=0, sticky="new", padx=5, pady=10)
        self.labelframe2.config(borderwidth=2, relief="groove")

        self.from_count = Label(self.labelframe, text="Začetek štetja kosov:")
        self.from_count.grid(row=0, column=0, sticky="w", padx=10, pady=5,columnspan=5)


        self.day_variable = StringVar(self)
        self.month_variable = StringVar(self)
        self.year_variable = StringVar(self)
        self.hour_variable = StringVar(self)

        self.day_list = []
        self.month_list = ['januar', 'februar', 'marec', 'april', 'maj', 'junij', 'julij', 'avgust', 'september', 'oktober', 'november', 'december']
        self.year_list = []
        self.hour_list = []

        for i in range(0,31):
            self.day_list.append(i+1)

        for i in range(20):
            self.year_list.append(2005 + i)

        for i in range(24):
            self.hour_list.append("{}:00" . format(i))


        self.counter_day_option = OptionMenu(self.labelframe, self.day_variable,self.day_list[self.controller.userdata.countdate.day - 1],*self.day_list)
        self.counter_day_option.grid(row=1, column=0, sticky=W,padx=10,pady=5)

        self.counter_month_option = OptionMenu(self.labelframe, self.month_variable,self.month_list[self.controller.userdata.countdate.month - 1],*self.month_list)
        self.counter_month_option.grid(row=1, column=1, sticky=W,pady=5)

        self.counter_year_option = OptionMenu(self.labelframe, self.year_variable,self.year_list[self.controller.userdata.countdate.year - 2005],*self.year_list)
        self.counter_year_option.grid(row=1, column=2, sticky=W,padx=10,pady=5)

        self.counter_hour_option = OptionMenu(self.labelframe, self.hour_variable,self.hour_list[self.controller.userdata.countdate.hour],*self.hour_list)
        self.counter_hour_option.grid(row=1, column=3, sticky=W,pady=5)





        self.test_count_reset_button = Button(self.labelframe, text="Nastavi števec", command=self.set_test_count)
        self.test_count_reset_button.grid(row=2, column=0, padx=10, pady=5, sticky=W,columnspan=5)

        self.test_count_reset_button = Button(self.labelframe, text="Ponastavi števec", command=self.reset_test_count)
        self.test_count_reset_button.grid(row=3, column=0, padx=10, pady=5, sticky=W,columnspan=5)

        self.test_count_reset_label = Label(self.labelframe, text="")

        self.lbl8 = Label(self.labelframe2, text="Št. ciklov do servisa:")
        self.lbl8.grid(row=0, column=0, sticky=NW, padx=10, pady=5, columnspan=2)

        self.service_entry = Entry(self.labelframe2, width=6,font=("Calibri", 14))
        self.service_entry.insert(END, self.controller.userdata.service)
        self.service_entry.grid(row=1, column=0, sticky=W, padx=10)

        self.service_button = Button(self.labelframe2, text="Spremeni", command=self.set_service_counter)
        self.service_button.grid(row=1, column=1, sticky=W,pady=5)

        self.save_service_label = Label(self.labelframe2, text="")
        # self.save_service_label.grid_forget()

        self.cal_label = Label(self.labelframe2, text="Datum zadnje kalibracije:")
        self.cal_label.grid(row=3, column=0, sticky=NW, padx=10, pady=5, columnspan=3)

        self.cal_day_variable = StringVar(self)
        self.cal_month_variable = StringVar(self)
        self.cal_year_variable = StringVar(self)
        self.cal_hour_variable = StringVar(self)

        self.cal_day_option = OptionMenu(self.labelframe2, self.cal_day_variable,self.day_list[self.controller.userdata.calibrationdate.day - 1],*self.day_list)
        self.cal_day_option.grid(row=4, column=0, sticky=W,padx=10,pady=5)

        self.cal_month_option = OptionMenu(self.labelframe2, self.cal_month_variable,self.month_list[self.controller.userdata.calibrationdate.month - 1],*self.month_list)
        self.cal_month_option.grid(row=4, column=1, sticky=W,pady=5)

        self.cal_year_option = OptionMenu(self.labelframe2, self.cal_year_variable,self.year_list[self.controller.userdata.calibrationdate.year - 2005],*self.year_list)
        self.cal_year_option.grid(row=4, column=2, sticky=W,padx=10,pady=5)

        self.cal_button = Button(self.labelframe2, text="Spremeni", command=self.set_calibration_date)
        self.cal_button.grid(row=5, column=0, sticky=W, padx=10, pady=5, columnspan=3)

        self.cal_apply_label = Label(self.labelframe2, text="")
        # self.cal_apply_label.grid_forget()

    def display_factory_reset(self):
        self.factory_reset_frame = Frame(self.right_frame)
        self.factory_reset_frame.grid(row=1, column=0, sticky="new")
        #self.factory_reset_frame.columnconfigure(1, weight=1)

        self.factory_reset_label = Label(self.factory_reset_frame, text="TOVARNIŠKE NASTAVITVE", font=("Calibri", 15,'bold'))
        self.factory_reset_label.grid(row=0, column=0, sticky="w", pady=10, columnspan=2)

        self.factory_reset_text = Label(self.factory_reset_frame, text="Povrnitev testne naprave {} na tovarniške\nnastavitve:" . format(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']))
        self.factory_reset_text.grid(row=1, column=0, sticky="w", pady=5, columnspan=2)

        self.factory_reset_pass = Label(self.factory_reset_frame, text="Geslo:")
        self.factory_reset_pass.grid(row=2, column=0, sticky="w", pady=5)

        self.factory_reset_entry = Entry(self.factory_reset_frame, width=15,font=("Calibri", 14))
        self.factory_reset_entry.grid(row=2, column=1, sticky="w", pady=5)

        self.factory_reset_button = Button(self.factory_reset_frame, text="Povrni", command=self.factory_reset)
        self.factory_reset_button.grid(row=3, column=0, sticky="w", pady=5, columnspan=2)

    def display_logoff(self):
        self.logoff_frame = Frame(self.task_frame)
        self.logoff_frame.grid(row=3, column=0, sticky="news")

        self.logoff_label = Label(self.logoff_frame, text="ODJAVA", font=("Calibri", 15,'bold'))
        self.logoff_label.grid(row=0, column=0, sticky="w", pady=10)
        self.logoff_text = Label(self.logoff_frame, text="Za nadaljno uporabo testne naprave se\nmorate odjaviti iz nastavitev.")
        self.logoff_text.grid(row=1, column=0, sticky="w", pady=5)
        self.logout_button = Button(self.logoff_frame, text="Odjava",  command=self.logout)
        self.logout_button.grid(row=2, column=0, pady=5, sticky=W)




    def display_log(self):
        self.log_frame = Frame(self.task_frame)
        self.log_frame.grid(row=1, column=0, sticky="new")

        self.log_label_title = Label(self.log_frame, text="ZAPISNIK", font=("Calibri", 15,'bold'))
        self.log_label_title.grid(row=0, column=0, sticky="w",columnspan=5, pady=10)

        self.log_label = Label(self.log_frame, text="Zapisnik si shranjuje podatke o testiranem izdelku.")
        self.log_label.grid(row=1, column=0, sticky="w", pady=5,columnspan=5)

        self.log_start_time_label = Label(self.log_frame, text="Od:")
        self.log_start_time_label.grid(row=2, column=0, sticky="w", pady=5)

        self.start_day_variable = StringVar(self)
        self.start_month_variable = StringVar(self)
        self.start_year_variable = StringVar(self)

        self.end_day_variable = StringVar(self)
        self.end_month_variable = StringVar(self)
        self.end_year_variable = StringVar(self)

        self.day_list = []
        self.month_list = ['januar', 'februar', 'marec', 'april', 'maj', 'junij', 'julij', 'avgust', 'september', 'oktober', 'november', 'december']
        self.year_list = []

        for i in range(1,32):
            self.day_list.append(i+1)

        for i in range(20):
            self.year_list.append(2005 + i)

        self.log_start_time_day_option = OptionMenu(self.log_frame, self.start_day_variable,self.day_list[0],*self.day_list)
        self.log_start_time_day_option.grid(row=2, column=1, sticky=W)


        self.log_start_time_month_option = OptionMenu(self.log_frame, self.start_month_variable,self.month_list[0],*self.month_list)
        self.log_start_time_month_option.grid(row=2, column=2, sticky=W)


        self.log_start_time_year_option = OptionMenu(self.log_frame, self.start_year_variable,self.year_list[0],*self.year_list)
        self.log_start_time_year_option.grid(row=2, column=3, sticky=W)


        self.log_end_time_label = Label(self.log_frame, text="Do:")
        self.log_end_time_label.grid(row=3, column=0, sticky="w", pady=5)

        # Set end date to today (can't look into future)
        date = datetime.date.today()

        self.log_end_time_day_option = OptionMenu(self.log_frame, self.end_day_variable, self.day_list[date.day - 1], *self.day_list)
        self.log_end_time_day_option.grid(row=3, column=1, sticky=W)

        self.log_end_time_month_option = OptionMenu(self.log_frame, self.end_month_variable, self.month_list[date.month - 1], *self.month_list)
        self.log_end_time_month_option.grid(row=3, column=2, sticky=W)

        self.log_end_time_year_option = OptionMenu(self.log_frame, self.end_year_variable, self.year_list[date.year - 2005], *self.year_list)
        self.log_end_time_year_option.grid(row=3, column=3, sticky=W)


        self.loggenerate_button = Button(self.log_frame, text="Prenesi zapisnik",command=self.make_log)
        self.loggenerate_button.grid(row=4, column=0, pady=10, sticky=W, columnspan=5)


    def display_shutdown(self):
        self.shutdown_frame = Frame(self.task_frame)
        self.shutdown_frame.grid(row=4, column=0, sticky="new")
        #self.shutdown_frame.columnconfigure(1, weight=1)

        self.shutdown_label = Label(self.shutdown_frame, text="IZKLOP", font=("Calibri", 15,'bold'))
        self.shutdown_label.grid(row=0, column=0, sticky="w", pady=10)

        self.shutdown_button = Button(self.shutdown_frame, text="Izklopi testno napravo",  command=self.shutdown)
        self.shutdown_button.grid(row=1, column=0, pady=5, sticky=W)

    def shutdown(self):
        # izklop TN

        self.controller.client.send({'shutdown': 'true'})








    def show_manual(self,event):
        webbrowser.open(self.controller.userdata.path_manual)

    def show_tasks(self): # Show tasks when GUI init
        for task_number in range(len(self.controller.userdata.task)):
            self.controller.userdata.task[task_number]['show'] = False

            self.make_task(task_number)

    def make_task(self,task_number): # Show new task when GUI active
        if self.controller.userdata.task[task_number]['show'] == False:
            self.controller.userdata.task[task_number]['show'] = True

            bg_color = "grey"

            self.sep.append({})

            self.sep[task_number]['frame'] = Frame(self.test_device_frame_inner)
            self.sep[task_number]['frame'].grid(row=task_number + 1, column=0, pady=5, padx=5,sticky="we")
            self.sep[task_number]['frame'].columnconfigure(3,weight=1)
            self.sep[task_number]['frame'].rowconfigure(task_number + 1,weight=1)


            self.sep[task_number]['checkbutton'] = Checkbutton(self.sep[task_number]['frame'], variable=self.controller.userdata.task[task_number]['task_enable'])
            self.sep[task_number]['checkbutton'].grid(row=0, column=0,sticky="w",padx=5,columnspan=3)

            self.sep[task_number]['label'] = Label(self.sep[task_number]['frame'], text=self.controller.userdata.task[task_number]['task_name'], font="Helvetica 10 bold")
            self.sep[task_number]['label'].grid(row=0, column=0,padx=30,sticky="w",columnspan=3)

            self.sep[task_number]['desc'] = Label(self.sep[task_number]['frame'], text=self.controller.userdata.task[task_number]['task_description'])
            self.sep[task_number]['desc'].grid(row=1, column=0,sticky="w",padx=5,columnspan=3)

            # Does task has any definitions?
            if self.controller.userdata.task[task_number]['task_definition']:
                self.sep[task_number]['definition'] = []

                for i in range(self.controller.userdata.num_of_definitions):
                    if self.controller.userdata.definition[i]['definition_task'] == self.controller.userdata.task[task_number]['task_slug']:
                        self.sep[task_number]['definition'].append({})

                        self.sep[task_number]['definition'][-1]['label'] = Label(self.sep[task_number]['frame'], text="{}:" . format(self.controller.userdata.definition[i]['definition_name']))
                        self.sep[task_number]['definition'][-1]['label'].grid(row=1 + len(self.sep[task_number]['definition']), column=0, padx=5,pady=5,sticky="w")

                        self.sep[task_number]['definition'][-1]['entry'] = Entry(self.sep[task_number]['frame'], textvariable=self.controller.userdata.definition[i]['definition_value'],width=len(str(self.controller.userdata.definition[i]['definition_value'].get())) + 1,font=("Calibri", 14))
                        self.sep[task_number]['definition'][-1]['entry'].grid(row=1 + len(self.sep[task_number]['definition']), column=1,sticky="w")

                        self.sep[task_number]['definition'][-1]['def_unit'] = Label(self.sep[task_number]['frame'], text=self.controller.userdata.definition[i]['definition_unit'])
                        self.sep[task_number]['definition'][-1]['def_unit'].grid(row=1 + len(self.sep[task_number]['definition']), column=2,sticky="w")

                        self.sep[task_number]['definition'][-1]['def_desc'] = Label(self.sep[task_number]['frame'], text=self.controller.userdata.definition[i]['definition_desc'],font="Calibri 12 italic")
                        self.sep[task_number]['definition'][-1]['def_desc'].grid(row=1 + len(self.sep[task_number]['definition']), column=3,sticky="we",padx=20)


            # self.sep.append(Label(self.task_frame, text=self.controller.userdata.task[task_number]['task_description']))
            # self.sep[task_number * 2 + 1].grid(row=task_number * 2 + 1, column=1, padx=25,sticky="we")


            # Izpiši kalibracijo pod vsaki task













    def check_after(self):
        self.after(10,self.check_after)

        if not self.queue.empty(): # something is in the prop queue
            msg = self.queue.get()

            if "text" in msg: # new text
                self.make_message(msg['text']['text_number'])

            if "task" in msg: #create new task, pridejo za tester_init
                self.make_task(msg['task']['task_number'])

            if "task_update" in msg:
                self.task_number = msg['task_update']['task_number']

                self.update_task(msg['task_update']['task_number'])

            if "service" in msg:
                self.service_entry.delete(0, 'end')
                self.service_entry.insert(END, self.controller.userdata.service)

            if "log_file" in msg:
                if msg['log_file']:
                    self.log_info_label = Label(self.log_frame, text="Zapisnik uspešno prenešen.",foreground="green")
                else:
                    self.log_info_label = Label(self.log_frame, text="Napaka pri prenašanju zapisnika.", foreground="red")

                self.log_info_label.grid(row=5, column=0, sticky="w", pady=5, columnspan=5)

            if "factory_reset" in msg:
                if msg['factory_reset']:
                    self.factory_reset_label2 = Label(self.factory_reset_frame, text="Nastavitve povrnjene.", foreground="green")
                else:
                    self.factory_reset_label2 = Label(self.factory_reset_frame, text="Napaka pri povrnitvi nastavitev.", foreground="red")

                self.factory_reset_label2.grid(row=4, column=0, sticky="w", pady=5)


    def reset_test_count(self):
        # send server to reset counter
        countdate = datetime.datetime.utcnow()
        localdate = pytz.utc.localize(countdate).astimezone(pytz.timezone('Europe/Ljubljana'))
        self.day_variable.set(localdate.day)

        self.month_variable.set(self.month_list[localdate.month - 1])
        self.year_variable.set(localdate.year)

        self.hour_variable.set("{}:{}" . format(localdate.hour,localdate.minute))


        # Strip off miliseconds
        #countdate = datetime.datetime(countdate.year,countdate.month,countdate.day,countdate.hour,countdate.minute,countdate.second)

        self.controller.client.send({'set_count': countdate})

        self.test_count_reset_label.config(text="Ponastavljeno.", foreground="green")
        self.test_count_reset_label.grid(row=4, column=0, sticky="w", padx=10,columnspan=5)



    def set_test_count(self):
        # send server to reset counter

        day = int(self.day_variable.get())
        year = int(self.year_variable.get())

        for i in range(len(self.month_list)):
            if self.month_list[i] == self.month_variable.get():
                month = i + 1

        position = (self.hour_variable.get()).find(":")
        hour = int((self.hour_variable.get())[:position])

        try:
            # Time provided will be in local time. It needs to be converted to UTC

            timezone = pytz.timezone('Europe/Ljubljana')
            countdate = datetime.datetime(year, month, day, hour, 0, 0, 0)
            utcdate = timezone.localize(countdate,is_dst=None).astimezone(pytz.utc)

            # Send server command to send log
            self.controller.client.send({'set_count': utcdate})

            self.test_count_reset_label.config(text="Števec nastavljen.", foreground="green")
        except ValueError:
            # Invalid date entered
            self.test_count_reset_label.config(text="Datum štetja je nastavljen.", foreground="red")

        self.test_count_reset_label.grid(row=4, column=0, sticky="w", padx=10,columnspan=5)







    def set_service_counter(self):
        # send server to reset counter
        service = int(self.service_entry.get())

        if(0 < service < 100000):
            self.controller.client.send({'service': service})
            self.save_service_label.config(text="Shranjeno!", foreground="green")
        else:
            self.save_service_label.config(text="Nepravilni vnos!", foreground="red")

        self.save_service_label.grid(row=2, column=0, sticky="w", padx=10,pady=5,columnspan=2)

    def set_calibration_date(self):

        day = int(self.cal_day_variable.get())
        year = int(self.cal_year_variable.get())

        for i in range(len(self.month_list)):
            if self.month_list[i] == self.cal_month_variable.get():
                month = i + 1

        try:
            calibrationdate = datetime.datetime(year, month, day)

            # Send server command to send log
            self.controller.client.send({'calibration': calibrationdate})

            self.cal_apply_label.config(text="Kalibracija nastavljena.", foreground="green")
        except ValueError:
            # Invalid date
            self.cal_apply_label.config(text="Datum kalibracije je neveljaven.", foreground="red")

        self.cal_apply_label.grid(row=6, column=0, sticky="w", padx=10,columnspan=3)



    def update_task(self,task_number):  # Update task when GUI active
        bg_color = "grey"

        self.sep[task_number].config(text=self.controller.userdata.task[task_number]['task_name'],background=bg_color)

    def set_test_device(self,value):
        i = 0
        for i in range(len(self.controller.userdata.test_devices)):
            if self.controller.userdata.test_devices[i]['name'] == value:
                self.controller.userdata.prop_test_device = i
                break

        if i == len(self.controller.userdata.test_devices):
            print("Invalid TN number")

        self.ip_entry.delete(0, 'end')
        self.ip_entry.insert(END, self.controller.userdata.test_devices[i]['ip'])

        self.port_entry.delete(0, 'end')
        self.port_entry.insert(END, self.controller.userdata.test_devices[i]['port'])




    def save_test_device_settings(self):
        ip = self.ip_entry.get()
        port = self.port_entry.get()

        self.controller.userdata.test_devices[self.controller.userdata.prop_test_device]['ip'] = ip
        self.controller.userdata.test_devices[self.controller.userdata.prop_test_device]['port'] = port

        try:
            with open(self.controller.userdata.directory + '/config.strips', 'r') as data_file:
                data = json.load(data_file)

                for i in range(len(data)):
                    if self.controller.userdata.test_devices[self.controller.userdata.prop_test_device]['name'] == data[i]['name']:
                        # if current TN in data, replace it
                        data[i]['ip'] = ip
                        data[i]['port'] = port

            with open(self.controller.userdata.directory + '/config.strips', 'w') as data_file:
                json.dump(data,data_file)

            self.save_test_device_label = Label(self.config_frame, text="Shranjeno.", foreground="green")

        except Exception as error:
            print("[save_test_device_settings] Error: {}" . format(error))
            self.save_test_device_label = Label(self.config_frame, text="Datoteka 'config.strips' ne obstaja!", foreground="red")

        finally:
            self.save_test_device_label.grid(row=4, column=0, sticky="w",columnspan=2)

    def save_task_settings(self):
        # send to server task data

        for task_number in range(len(self.controller.userdata.task)):
            print("{}: {}".format(self.controller.userdata.task[task_number]['task_name'],self.controller.userdata.task[task_number]['task_enable'].get()))

            if self.controller.userdata.task[task_number]['task_definition']:
                for definition_number in range(len(self.controller.userdata.definition)):
                    if self.controller.userdata.definition[definition_number]['definition_task'] == self.controller.userdata.task[task_number]['task_slug']:
                        print("{}: {}".format(self.controller.userdata.definition[definition_number]['definition_name'],self.controller.userdata.definition[definition_number]['definition_value'].get()))
                        self.controller.client.send({"definition_update": {"definition_task": self.controller.userdata.definition[definition_number]['definition_task'],"definition_slug": self.controller.userdata.definition[definition_number]['definition_slug'], "definition_value": self.controller.userdata.definition[definition_number]['definition_value'].get()}})

            #  Simultaneously update task_info
            self.controller.client.send({"task_update": {"task_slug": self.controller.userdata.task[task_number]['task_slug'], "task_enable": self.controller.userdata.task[task_number]['task_enable'].get()}})


        self.save_task_settings_label.config(text="Shranjeno!", foreground="green")
        self.save_task_settings_label.grid(row=3, column=0, sticky="w")



    def save(self):
        self.controller.userdata.service = self.ent1.get()

        self.lbl2.config(text="Shranjeno")

    def logout(self):
        self.controller.userdata.admin_logged = False

        if self.controller.userdata.tester_init:  # Check if user is connected on TN
            if self.controller.userdata.maintenance == self.controller.userdata.id_num:
                self.controller.client.send({"maintenance": -1}) # release maintenance mode


        self.controller.switch_frame(PropertiesLoginPage)

    def redirect(self):
        # Return to login page if admin is not logged.
        if self.controller.userdata.admin_logged == False:
            self.controller.switch_frame(PropertiesLoginPage)
        else:
            if self.controller.userdata.tester_init: # Check if user is connected on TN
                if self.controller.userdata.maintenance == -1 or self.controller.userdata.maintenance == self.controller.userdata.id_num: # Check if device is already in maintenance
                    # send to server that TN is in maintenance mode by this user
                    self.controller.client.send({"maintenance": self.controller.userdata.id_num})

    def factory_reset(self):
        password = self.factory_reset_entry.get()

        if(password == self.controller.userdata.admin_pass):
            self.controller.client.send({"factory_reset": self.controller.userdata.id_num})
        else:
            self.factory_reset_label2 = Label(self.factory_reset_frame, text="Nepravilno geslo.", foreground="red")
            self.factory_reset_label2.grid(row=4, column=0, sticky="w", pady=5)


    def make_log(self):
        self.file = filedialog.asksaveasfilename(initialdir = "/",title = "Shrani zapisnik",filetypes = (("csv datoteka","*.csv"),("vse datoteke","*.*")))

        if self.file: # asksaveasfile return `None` if dialog closed with "cancel".

            # Change log file path
            self.controller.userdata.log_path = self.file

            st_day = int(self.start_day_variable.get())
            st_year = int(self.start_year_variable.get())

            en_day = int(self.end_day_variable.get())
            en_year = int(self.end_year_variable.get())

            for i in range(len(self.month_list)):
                if self.month_list[i] == self.start_month_variable.get():
                    st_month = i + 1

                if self.month_list[i] == self.end_month_variable.get():
                    en_month = i + 1

            try:
                st_date = datetime.date(st_year,st_month,st_day)
                en_date = datetime.date(en_year,en_month,en_day)


                self.log_info_label = Label(self.log_frame, text="Prenašanje zapisnika...", foreground="black")

                # Send server command to send log
                self.controller.client.send({"make_log": {"id": self.controller.userdata.id_num, "st_date": st_date.strftime("%Y.%m.%d"), "en_date": en_date.strftime("%Y.%m.%d")}})
            except ValueError:
                # Invalid date entered
                self.log_info_label = Label(self.log_frame, text="Izbrani datum je neveljaven!", foreground="red")

            self.log_info_label.grid(row=5, column=0, sticky="w", pady=5,columnspan=5)

class MyOptionMenu(OptionMenu):
    def __init__(self, master, status, *options):
        self.var = StringVar(master)
        self.var.set(status)
        OptionMenu.__init__(self, master, self.var, *options)
        self.config(font=('calibri',(10)),bg='white',width=12)
        self['menu'].config(font=('calibri',(10)),bg='white')


class PropertiesLoginPage(Frame):
    def __init__(self, parent, controller):
        Frame.__init__(self, parent)

        self.parent = parent
        self.controller = controller

        self.controller.current_frame = "PropertiesLoginPage"

        self.columnconfigure(2, weight=1)
        self.rowconfigure(4, weight=1)

        self.grid(row=0,column=0,sticky="news",padx=20,pady=20)

        self.menu = Menu(self)
        self.controller.config(menu=self.menu)

        #dodaj login formo, ce ta ni izpolnjena pravilno, ostane spodnji frame zaklenjen, sicer se odklene

        self.menu.add_command(label="Vpis",command=lambda: self.controller.switch_frame(LoginPage))
        self.menu.add_command(label="Tester",command=lambda: self.controller.switch_frame(TesterPage))
        self.menu.add_command(label="Nastavitve")

        self.lbl0 = Label(self, text="Nastavitve",font=("Calibri", 15,'bold'), padding=(0,0,0,20))
        self.lbl0.grid(row=0, column=0, sticky=W)

        self.lbl1 = Label(self, text="Za nadaljevanje se morate prijaviti.")
        self.lbl1.grid(row=1, column=0, sticky=W, pady=5,columnspan=2)

        self.lbl2 = Label(self, text="Geslo:")
        self.lbl2.grid(row=2, column=0, sticky=W, pady=5)

        self.ent1 = Entry(self, width=15,font=("Calibri", 14))
        self.ent1.insert(END, "")
        self.ent1.grid(row=2, column=1, sticky=W)

        self.lbl3 = Label(self, text="")

        self.startBtn = Button(self, text="Prijava",  command=self.userLogin)
        self.startBtn.grid(row=4, column=0, pady=20, sticky="nw")

        self.logo = PhotoImage(file=self.controller.userdata.directory + "/images/strips.gif")
        self.copyright_img = Label(self, image=self.logo)
        self.copyright_img.grid(row=0, column=2, sticky=NE)


    def userLogin(self):
        password = self.ent1.get()

        if(password == self.controller.userdata.admin_pass):
            #self.lbl2.config(text="Geslo OK!",foreground="green")

            if self.controller.userdata.tester_init:
                if self.controller.userdata.maintenance != -1:
                    if self.controller.userdata.maintenance != self.controller.userdata.id_num:
                        #print(self.controller.userdata.maintenance)
                        #print(self.controller.userdata.id_num)
                        self.lbl3.config(text="Nastavitve že v uporabi.", foreground="red")
                        self.lbl3.grid(row=2, column=2, sticky=W, padx=20, pady=5)

                        return

            self.controller.userdata.admin_logged = True
            self.controller.switch_frame(PropertiesPage)
        else:
            self.lbl3.config(text="Nepravilno geslo!",foreground="red")
            self.lbl3.grid(row=2, column=2, sticky=W, padx=20, pady=5)


class SplashScreen(Frame):
    def __init__(self, parent, controller):
        Frame.__init__(self, parent)
        self.parent = parent
        self.controller = controller

        self.controller.current_frame = "SplashScreen"

        self.place(x=-2,y=-2)

        controller.title("StripsTester v{}" . format(self.controller.userdata.version))

        controller.overrideredirect(True)

        # Give window icon if platform is Windows
        if platform.system() == 'Windows':
            #print("PATH: {}" . format(self.controller.userdata.directory))
            controller.iconbitmap(self.controller.userdata.directory + "/images/icon.ico")

        x = (self.controller.winfo_screenwidth() - 640) / 2
        y = (self.controller.winfo_screenheight() - 375) / 2

        self.controller.geometry("638x372+%d+%d" % (x, y))

        self.canvas = Canvas(self,width=640, height=375)
        self.canvas.pack(expand=YES, fill=BOTH)

        self.logo = PhotoImage(file=self.controller.userdata.directory + "/images/splash.gif")
        self.canvas_image = self.canvas.create_image(0,0, image=self.logo, anchor=NW)
        self.canvas_text = self.canvas.create_text(10,350,text="Nalaganje testnih naprav...",anchor="nw",fill="white")
        self.canvas_text_version = self.canvas.create_text(435,209,text="v{}" . format(self.controller.userdata.version),font=("Calibri", 18),anchor="nw",fill="#657983")

        if os.path.isfile(self.controller.userdata.directory + "/config.strips"):
            # Open file, read all TN settings

            with open(self.controller.userdata.directory + '/config.strips') as data_file:
                try:
                    data = json.load(data_file)

                    for i in range(len(data)):
                        self.controller.userdata.test_devices.append(data[i])
                        self.canvas.itemconfig(self.canvas_text,text="Najdena testna naprava {}" .format(data[i]['name']))
                        self.controller.update()
                        time.sleep(0.1)

                    count = len(self.controller.userdata.test_devices)

                    # get random message from database
                    messages = []
                    messages.append("Pozdravljeni!")
                    messages.append("Zdravo!")
                    messages.append("Looking good today :)!")

                    motd = messages[random.randint(0,len(messages) - 1)]

                    if(count == 1):
                        self.canvas.itemconfig(self.canvas_text,text="Najdena 1 testna naprava. {}" .format(motd))
                    elif(count == 2):
                        self.canvas.itemconfig(self.canvas_text,text="Najdeni 2 testni napravi. {}" .format(motd))
                    elif(count == 3 or count == 4):
                        self.canvas.itemconfig(self.canvas_text,text="Najdene {} testne naprave. {}" . format(count,motd))
                    else:
                        self.canvas.itemconfig(self.canvas_text,text="Najdenih {} testnih naprav. {}" . format(count,motd))

                    self.after(2000, self.end)
                except Exception as error:
                    #print(error)
                    self.canvas.itemconfig(self.canvas_text,text="Datoteka 'config.strips' je prazna oz. neveljavna.")
                    self.after(5000, self.terminate)
        else:
            # Missing file!
            self.canvas.itemconfig(self.canvas_text,text="Datoteke 'config.strips' ni mogoče najti.")
            self.after(5000, self.terminate)



    def end(self):
        x = (self.controller.winfo_screenwidth() - 1024) / 2
        y = (self.controller.winfo_screenheight() - 600) / 2

        default_font = tkFont.nametofont("TkDefaultFont")
        default_font.configure(size=13)
        default_font.configure(family="Calibri")

        self.controller.overrideredirect(False)
        self.controller.geometry("1024x600+%d+%d" % (x, y))
        self.controller.update()
        self.controller.switch_frame(LoginPage)

    def terminate(self):
        sys.exit()


class UserData():
    # Dodaj privzete vrednosti in jih podvoji z zacetnimi... ko uporabnik klikne factory reset, se vrednosti ponastavijo

    def __init__(self):
        self.id_num = 0
        self.test_num = 0
        self.good_count = 0
        self.bad_count = 0
        self.global_good_count = 0
        self.global_bad_count = 0
        self.service = 0
        self.countdate = datetime.datetime.today()
        self.calibrationdate = datetime.datetime.today()
        self.path_manual = ""

        self.admin_pass = "strips"
        self.admin_logged = False

        self.default_id_num = 0
        self.default_test_num = 0
        self.default_good_count = 0
        self.default_bad_count = 0
        self.default_service = 999

        self.tester_init = False

        self.messager = {}
        self.task = {}
        self.definition = {}

        self.num_of_messager = 0
        self.num_of_tasks = 0
        self.num_of_definitions = 0

        self.directory = os.path.dirname(os.path.realpath(__file__))
        #self.main_directory = os.path.join(os.path.dirname(__file__), "configs", self.get_setting_file_name())

        self.test_devices = []
        self.test_device = 0

        self.prop_test_device = 0

        self.login_queue = Queue(0)
        self.tester_queue = Queue(0)
        self.properties_queue = Queue(0)

        self.esd = False
        self.high_voltage = False

        self.result = "ready"
        self.maintenance = -1

        self.log_path = ""

        self.version = "1.2"

        self.run = True # Run recieve thread

        self.ping = time.clock()
        self.ping_count = 0

        self.test_time_enable = False
        self.start_test_time = 0
        self.end_test_time = 0

# INTERPROCESS COMMUNICATION
class Client:
    def __init__(self,controller):
        self.controller = controller
        self.clientdata = {}
        self.socket_alive = False
        self.send_queue = Queue(0)

        # print("TCP Send thread started!")
        self.send_thread = threading.Thread(target=self.send_process)
        self.send_thread.setDaemon(True)
        self.send_thread.start()

        self.ping_timer = time.clock()

    def start(self):
        if self.socket_alive:
            self.close()
            time.sleep(0.5)



        # Setup TCP socket
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            #self.client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.client_socket.settimeout(3)
            self.client_socket.connect((self.controller.userdata.test_devices[self.controller.userdata.test_device]['ip'], int(self.controller.userdata.test_devices[self.controller.userdata.test_device]['port'])))
            self.client_socket.settimeout(None)

            self.socket_alive = True
            self.controller.userdata.run = True

            # Make new thread for recieveing
            self.recieve_thread = threading.Thread(target=self.recieve)
            self.recieve_thread.setDaemon(True)
            self.recieve_thread.start()

            # Make new thread for recieveing
            self.ping_thread = threading.Thread(target=self.ping_server)
            self.ping_thread.setDaemon(True)
            self.ping_thread.start()

            # Redirect to TesterPage if connected successfully
            return True
        except Exception as error:
            print("[start client]: {}" . format(error))

            #print(error) [WinError 10061] No connection could be made because the target machine actively refused it
            return False


    def close(self):
        self.delete_data()

        try:
            print("closing1")
            if self.socket_alive:  # Close the socket only if alive
                print("closing2")
                self.socket_alive = False

                self.send({'close': True})

                while not self.send_queue.empty():
                    time.sleep(0.01)

                self.client_socket.shutdown(socket.SHUT_RDWR)
                self.client_socket.close()

            else:
                print("Socket not alive")
        except Exception as err:
            print("Cant close client: {}" . format(err))

        return

    def delete_data(self):

        self.controller.userdata.result = "ready"
        self.controller.userdata.test_time_enable = False
        self.controller.userdata.run = False

        # Restore task and definition dictionary
        self.controller.userdata.messager = {}
        self.controller.userdata.task = {}
        self.controller.userdata.definition = {}

        self.controller.userdata.num_of_messager = 0
        self.controller.userdata.num_of_tasks = 0
        self.controller.userdata.num_of_definitions = 0

        self.controller.userdata.ping_count = 0


        # Close only on login page, change title in case of reconnect
        self.controller.title("StripsTester v{}" . format(self.controller.userdata.version))

        if self.controller.userdata.tester_init:
            self.controller.userdata.tester_init = False








    def recvall(self,sock, count):
        # Empty whole buffer
        buf = b''

        # Loop this code until all bytes have arrived (count)
        while count:
            try:
                sock.settimeout(5)  # Set timeout to 5 seconds (so it will be timeout in case of not recieving for more than 5 seconds)
                newbuf = sock.recv(count)
                sock.settimeout(None)
            except socket.timeout:
                raise
            except:
                return ""

            if not newbuf: return ""
            buf += newbuf
            count -= len(newbuf)
        return buf

    def recv_one_message(self,sock):
        try:
            lengthbuf = self.recvall(sock, 4)

            if lengthbuf:
                length, = struct.unpack('!I', lengthbuf)

                return self.recvall(sock, length) # Return whole message
            else:
                return ""

        except Exception as err:
            print("[recv_one_message] Error at server! ({})" . format(err))


            self.close()

            print("send disc mesg")
            self.controller.userdata.login_queue.put(json.loads('{"disconnect": "Izguba povezave s strežnikom"}'))  # Update tester page
            print("send disc mesg ok")

            if self.controller.current_frame != "LoginPage":
                # Redirect to LoginPage
                self.controller.switch_frame(LoginPage)

    def send_one_message(self, data):
        length = len(data)
        try:
            self.client_socket.sendall(struct.pack('!I', length))
            self.client_socket.sendall(data)
        except Exception as err:
            print("Close GUI - send error ({} | {}) {}".format(length,data,err))
            #self.close()



    def send(self,data):
        # Add message to queue so it won't interfere with other threads
        msg = {}
        msg['data'] = data

        self.send_queue.put(msg)


    '''
    def send(self,data):
        # Send message to server (TN)
        data = json.dumps(data,default=str)
        print("Sending {}" . format(data))

        try:
            msg = {}
            msg['data'] = data

            self.send_queue.put(msg)
            
            
            
            # Message to server does not need checksum TCP
            self.send_one_message(self.client_socket,data.encode())
        except Exception as err:
            print("[send] Error sending to server! ({})" . format(err))
            self.close()
    '''

    def ping_server(self):
        while self.controller.userdata.run:
            if time.clock() > self.ping_timer + 1:
                self.ping_timer = time.clock()

                if self.controller.userdata.tester_init:
                    self.send({'ping': time.clock()})

                    self.controller.userdata.ping_count = self.controller.userdata.ping_count + 1

                    if self.controller.userdata.ping_count > 15:  # No answer from server
                        self.close()

                        self.controller.userdata.login_queue.put(json.loads('{"disconnect": "Server se ne odziva"}'))  # Update tester page

                        # Redirect to LoginPage
                        self.controller.switch_frame(LoginPage)

            time.sleep(0.001)
        return

    def recieve(self):
        print("TCP Client started")
        self.send({'welcome': {'id': self.controller.userdata.id_num, 'test_type': self.controller.userdata.test_num}})

        while self.controller.userdata.run:
            try:
                data = self.recv_one_message(self.client_socket)

                if data:
                    #print("JSON: {}" . format(data))
                    msg = json.loads(data.decode())

                    if "tester_init" in msg:  # enable tester page -> accepted by server (TN)!
                        id = msg['tester_init']['id']

                        if id == -1:
                            # Duplicate socket, close it
                            print("Client duplicate, so close it.")
                            self.close()

                        else:
                            self.controller.userdata.master = msg['tester_init']['id']

                            if self.controller.userdata.tester_init == False:
                                self.controller.userdata.tester_init = True
                                self.controller.userdata.admin_logged = False # Da se ne prijavi v Properties offline pa se potem prijavi na TN

                                self.controller.title("StripsTester v{} [{}]".format(self.controller.userdata.version,self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']))

                        if self.controller.current_frame == "LoginPage":
                            self.controller.userdata.login_queue.put(msg)

                    if "text" in msg:  # update text
                        self.add_message(msg['text']['text'], msg['text']['tag'])
                        msg['text']['text_number'] = self.controller.userdata.num_of_messager - 1

                        if self.controller.current_frame == "TesterPage":
                            self.controller.userdata.tester_queue.put(msg)





                    if "test_time" in msg:  # update text
                        if "start_test" in msg['test_time']:
                            #print("I got {}" . format(msg['test_time']['start_test']))
                            print("Start_time: {}" . format(msg['test_time']))
                            self.controller.userdata.start_test_time = parser.parse(msg['test_time']['start_test'])
                            #print("parsed")
                            print("Parsed start time: {}" . format(self.controller.userdata.start_test_time))
                        if "end_test" in msg['test_time']:
                            self.controller.userdata.end_test_time = parser.parse(msg['test_time']['end_test'])
                            print("Parsed end time: {}" . format(self.controller.userdata.end_test_time))
                            self.controller.userdata.test_time_enable = False
                            print("a")
                        else:
                            self.controller.userdata.test_time_enable = True

                    if "task" in msg:  # create new task, pridejo za tester_init
                        self.add_task(msg['task']['task_name'],msg['task']['task_slug'], msg['task']['task_state'], msg['task']['task_description'], msg['task']['task_enable'], msg['task']['task_info'])
                        msg['task']['task_number'] = self.controller.userdata.num_of_tasks - 1 # give task number

                        if self.controller.current_frame == "TesterPage":
                            self.controller.userdata.tester_queue.put(msg)

                    if "task_update" in msg:
                        self.task_slug = msg['task_update']['task_slug']
                        self.task_number = self.get_task_number(self.task_slug)

                        if "task_state" in msg['task_update']:
                            self.controller.userdata.task[self.task_number]['task_state'] = msg['task_update']['task_state']

                        if "task_name" in msg['task_update']:
                            self.controller.userdata.task[self.task_number]['task_name'] = msg['task_update']['task_name']

                        if "task_enable" in msg['task_update']:
                            self.controller.userdata.task[self.task_number]['task_enable'].set(msg['task_update']['task_enable'])


                        #print("Recieved task_update on def recieve")
                        if self.controller.current_frame == "TesterPage":
                            #print("Putting on Tester Queue")
                            self.controller.userdata.tester_queue.put(msg)

                    if "definition" in msg:
                        self.add_definition(msg['definition']['definition_task'], msg['definition']['definition_name'], msg['definition']['definition_slug'], msg['definition']['definition_desc'], msg['definition']['definition_value'], msg['definition']['definition_unit'], msg['definition']['definition_extra_info'])
                        msg['definition']['definition_number'] = self.controller.userdata.num_of_definitions - 1 # give definition number

                        if self.controller.current_frame == "PropertiesPage":
                            self.controller.userdata.properties_queue.put(msg)

                        if self.controller.current_frame == "TesterPage":
                            self.controller.userdata.tester_queue.put(msg)


                    # Recieve definition update
                    if "definition_update" in msg:
                        self.definition_number = self.get_definition_number(msg['definition_update']['definition_task'],msg['definition_update']['definition_slug'])

                        if "definition_value" in msg['definition_update']:
                            self.controller.userdata.definition[self.definition_number]['definition_value'].set(msg['definition_update']['definition_value'])

                            #print("Recieved definition_update on def recieve")
                            if self.controller.current_frame == "TesterPage":
                                #print("Putting definition on Tester Queue")
                                self.controller.userdata.tester_queue.put(msg)

                    if "count" in msg:  # Counter update
                        self.controller.userdata.good_count = int(msg['count']['good'])
                        self.controller.userdata.bad_count = int(msg['count']['bad'])
                        self.controller.userdata.global_good_count = int(msg['count']['good_global'])
                        self.controller.userdata.global_bad_count = int(msg['count']['bad_global'])

                        if "countdate" in msg['count']:
                            print("AAAA")
                            self.controller.userdata.countdate = parser.parse(msg['count']['countdate'])
                            print("BBB")
                        if self.controller.current_frame == "TesterPage":
                            self.controller.userdata.tester_queue.put(msg) # Update tester page

                    if "service" in msg:  # Counter update
                        self.controller.userdata.service = int(msg['service'])

                        if self.controller.current_frame == "TesterPage":
                            self.controller.userdata.tester_queue.put(msg) # Update tester page
                        elif self.controller.current_frame == "PropertiesPage":
                            self.controller.userdata.properties_queue.put(msg)

                    if "calibration" in msg:  # Calibration date update
                        self.controller.userdata.calibrationdate = datetime.datetime.strptime(msg['calibration'], "%Y-%m-%d %H:%M:%S")

                        if self.controller.current_frame == "TesterPage":
                            self.controller.userdata.tester_queue.put(msg)  # Update tester page

                    if "path_manual" in msg:  # Calibration date update
                        self.controller.userdata.path_manual = msg['path_manual']

                    if "esd" in msg:
                        self.controller.userdata.esd = msg['esd']

                        if self.controller.current_frame == "TesterPage":
                            self.controller.userdata.tester_queue.put(msg) # Update tester page

                    if "high_voltage" in msg:
                        self.controller.userdata.high_voltage = msg['high_voltage']

                        if self.controller.current_frame == "TesterPage":
                            self.controller.userdata.tester_queue.put(msg) # Update tester page

                    if "task_result" in msg:
                        self.controller.userdata.result = msg['task_result']

                        if self.controller.current_frame == "TesterPage":
                            self.controller.userdata.tester_queue.put(msg) # Update tester page

                    if "maintenance" in msg:
                        self.controller.userdata.maintenance = msg['maintenance']

                    if "shutdown" in msg:
                        self.close()

                        self.controller.userdata.login_queue.put(json.loads('{"disconnect": "Testna naprava se je zaustavila"}'))  # Update tester page

                        if self.controller.current_frame != "LoginPage":
                            # Redirect to LoginPage
                            self.controller.switch_frame(LoginPage)

                    if "log_file" in msg:
                        #print("LOG FILE: {}" . format(msg['log_file']))

                        with open(self.controller.userdata.log_path + ".csv", "w") as data_file:
                            try:
                                for i in range(len(msg['log_file'])):
                                    data_file.write(msg['log_file'][i] + "\n")

                                # Send log saved successfully message
                                if self.controller.current_frame == "PropertiesPage":
                                    self.controller.userdata.properties_queue.put({'log_file': True})

                            except Exception as err:
                                print("Error: {}".format(err))

                                if self.controller.current_frame == "PropertiesPage":
                                    self.controller.userdata.properties_queue.put({'log_file': False})

                    if "factory_reset" in msg: # Forward to PropertiesPage
                        if self.controller.current_frame == "PropertiesPage":
                            self.controller.userdata.properties_queue.put(msg)

                    if "ping_answer" in msg:
                        #print("calculated ping: {}" . format(self.controller.userdata.ping))
                        self.controller.userdata.ping = (time.clock() - msg['ping_answer']) * 1000
                        self.controller.userdata.ping_count = 0
                        if self.controller.current_frame == "TesterPage":
                            self.controller.userdata.tester_queue.put(msg)

            except socket.error as msg:
                #print("Socket error! {}" .format(msg))
                print("Client closed safely.")
                self.close()

                # Send log saved successfully message
                if self.controller.current_frame != "LoginPage":
                    # Redirect to LoginPage
                    self.controller.switch_frame(LoginPage)

                if self.controller.userdata.tester_init:
                    self.controller.userdata.tester_init = False

        return


    # Send thread: so multiple threads send only one
    # This thread can be active whole time, as its part of test device
    def send_process(self):
        while True:
            if not self.send_queue.empty():  # Something is in the send queue
                msg = self.send_queue.get()  # Get ID and message

                data = json.dumps(msg['data'],default=str)
                #print("send_one_message {}" . format(msg['data']))
                self.send_one_message(data.encode())

            time.sleep(0.001)


    def add_message(self,messager_text,messager_tag):
        self.controller.userdata.messager[self.controller.userdata.num_of_messager] = {}

        self.controller.userdata.messager[self.controller.userdata.num_of_messager]['text'] = messager_text
        self.controller.userdata.messager[self.controller.userdata.num_of_messager]['tag'] = messager_tag
        self.controller.userdata.messager[self.controller.userdata.num_of_messager]['show'] = False

        self.controller.userdata.num_of_messager = self.controller.userdata.num_of_messager + 1

    def add_task(self, task_name, task_slug, task_state, task_description, task_enable, task_info):
        self.controller.userdata.task[self.controller.userdata.num_of_tasks] = {}

        self.controller.userdata.task[self.controller.userdata.num_of_tasks]['task_name'] = task_name
        self.controller.userdata.task[self.controller.userdata.num_of_tasks]['task_slug'] = task_slug
        self.controller.userdata.task[self.controller.userdata.num_of_tasks]['task_state'] = task_state
        self.controller.userdata.task[self.controller.userdata.num_of_tasks]['show'] = False
        self.controller.userdata.task[self.controller.userdata.num_of_tasks]['task_description'] = task_description
        self.controller.userdata.task[self.controller.userdata.num_of_tasks]['task_enable'] = IntVar()
        self.controller.userdata.task[self.controller.userdata.num_of_tasks]['task_enable'].set(task_enable)
        self.controller.userdata.task[self.controller.userdata.num_of_tasks]['task_definition'] = False
        self.controller.userdata.task[self.controller.userdata.num_of_tasks]['task_info'] = task_info

        self.controller.userdata.num_of_tasks = self.controller.userdata.num_of_tasks + 1
        print("[Strips INFO] Task '{}' created." . format(task_name))

    def add_definition(self,task_slug,definition_name,definition_slug,definition_desc,definition_value,definition_unit,definition_extra_info):
        self.controller.userdata.definition[self.controller.userdata.num_of_definitions] = {}

        self.controller.userdata.definition[self.controller.userdata.num_of_definitions]['definition_task'] = task_slug
        self.controller.userdata.definition[self.controller.userdata.num_of_definitions]['definition_name'] = definition_name
        self.controller.userdata.definition[self.controller.userdata.num_of_definitions]['definition_slug'] = definition_slug
        self.controller.userdata.definition[self.controller.userdata.num_of_definitions]['definition_desc'] = definition_desc
        self.controller.userdata.definition[self.controller.userdata.num_of_definitions]['definition_unit'] = definition_unit
        self.controller.userdata.definition[self.controller.userdata.num_of_definitions]['definition_extra_info'] = definition_extra_info


        if type(definition_value) == str: # Check if definition is string
            self.controller.userdata.definition[self.controller.userdata.num_of_definitions]['definition_value'] = StringVar()
        else:
            self.controller.userdata.definition[self.controller.userdata.num_of_definitions]['definition_value'] = DoubleVar()

        self.controller.userdata.definition[self.controller.userdata.num_of_definitions]['definition_value'].set(definition_value)


        self.controller.userdata.num_of_definitions = self.controller.userdata.num_of_definitions + 1
        self.controller.userdata.task[self.get_task_number(task_slug)]['task_definition'] = True

    def get_task_number(self,task_slug):

        for task_number in range(self.controller.userdata.num_of_tasks):
            if self.controller.userdata.task[task_number]['task_slug'] == task_slug:
                return task_number

        print("No task with task slug '{}' found." . format(task_slug))
        return None

    def get_definition_number(self,task_slug,definition_slug):

        for definition_number in range(self.controller.userdata.num_of_definitions):
            if self.controller.userdata.definition[definition_number]['definition_task'] == task_slug and self.controller.userdata.definition[definition_number]['definition_slug'] == definition_slug:
                return definition_number

        print("No definition with task slug '{}' and def slug '{}' found." . format(task_slug,definition_slug))
        return None

class Program(Tk):
    def __init__(self):
        Tk.__init__(self)

        self.container = Frame(self)
        self.container.pack(fill=BOTH, expand=True)
        self.container.columnconfigure(0,weight=1)
        self.container.rowconfigure(0,weight=1)

        self.userdata = UserData()
        self.client = Client(controller=self)

        self.current_frame = "SplashScreen"
        self._frame = SplashScreen(parent=self.container, controller=self)

    def switch_frame(self, frame_class):
        """Destroys current frame and replaces it with a new one."""
        new_frame = frame_class(parent=self.container, controller=self)
        self._frame.destroy()
        self._frame = new_frame

def main():
    app = Program()

    app.mainloop()


if __name__ == '__main__':
    main()
