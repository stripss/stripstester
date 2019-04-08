## !/usr/bin/env python3
# -*- coding: utf-8 -*-


'''

CE JE CONNECTAN in gre nato na LoginPage in se se enkrat prijavi, window freezes
delete tasks when reconnect



'''


from tkinter import *
from tkinter.ttk import *
from tkinter import filedialog

import json
import os
import random
import time
import datetime
import platform
import webbrowser
import tkinter.font as tkFont
import pytz
from dateutil import parser
import socket
import bisect

from twisted.internet import tksupport, reactor, protocol, error
from twisted.protocols.basic import LineReceiver

from collections import OrderedDict

class LoginPage(Frame):
    def __init__(self, parent, controller):
        # Initialisation header

        Frame.__init__(self, parent)
        self.bind("<<ShowFrame>>", self.on_show_frame)
        self.controller = controller

        self.columnconfigure(3, weight=1)
        #self.rowconfigure(1, weight=1)
        self.grid(row=0,column=0,sticky="news")

        self.logo = PhotoImage(file=self.controller.userdata.directory + "/images/strips.gif")
        self.copyright_img = Label(self, image=self.logo)
        self.copyright_img.grid(row=0, column=4, sticky=NE, rowspan=4) #  Upostevaj colspan

        # Page creation
        self.show_title()
        self.show_test_type()
        self.show_test_user()
        self.show_login()
        #self.show_test_devices() - called from splashscreen
        #self.show_test_device_info()

    def on_show_frame(self, event):
        #print("You got to LoginPage")
        self.update_test_devices()

    def show_title(self):
        self.login_title = Label(self, text="Prijava v sistem", font=self.controller.title_font)
        self.login_title.grid(row=0, column=0, sticky="nw", pady=(0,20))

    def show_test_devices(self):
        self.test_device_label = Label(self, text="Testna naprava:")
        self.test_device_label.grid(row=1, column=0, sticky="nw")

        self.test_device_list = StringVar(self)

        test_device_names = []
        for test_device in self.controller.userdata.test_devices:
            test_device_names.append(test_device['name'])

        self.test_device_option = OptionMenu(self, self.test_device_list,test_device_names[0],*test_device_names,command=self.set_test_device)
        self.test_device_option.grid(row=1, column=1, sticky="nw",columnspan=2,padx=20)

        # Set first TN to be selected
        self.test_device_list.set(test_device_names[0])

    # Update OptionMenu for test devices (called every on_show_frame)
    def update_test_devices(self):
        self.test_device_option['menu'].delete(0,'end')

        for test_device in self.controller.userdata.test_devices:
            self.test_device_option['menu'].add_command(label=test_device['name'],command=lambda value=test_device['name']: self.set_test_device(value,True))

        # Set previously device if exist (otherwise set it to first one)
        self.set_test_device(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name'],True)


    def show_test_type(self):
        self.test_label = Label(self, text="Tip testiranja:")
        self.test_label.grid(row=2, column=0, sticky=W, pady=5)

        self.test_type_list = StringVar(self)
        self.test_type_names = ["Redna proizvodnja", "Kosi iz popravila", "Analiza reklamacije", "Ostalo"]

        self.test_type_option = OptionMenu(self, self.test_type_list,self.test_type_names[0],*self.test_type_names)
        self.test_type_option.grid(row=2, column=1, sticky=W, columnspan=2,padx=20)

        # Set test type default value
        self.test_type_list.set(self.test_type_names[0])

    def show_test_user(self):
        self.user_label = Label(self, text="Številka operaterja:")
        self.user_label.grid(row=3, column=0, sticky=W, pady=5)

        self.user_entry = Entry(self, width=10, font=self.controller.entry_font)
        self.user_entry.insert(END, self.controller.userdata.id_num)
        self.user_entry.grid(row=3, column=1, sticky=W,padx=20)
        self.user_entry.bind("<KeyRelease>", self.on_user_entry)

        self.user_info = Label(self, text="")
        self.user_info.grid(row=3, column=2, sticky=W, pady=5, padx=10)

    def on_user_entry(self, event):
        value = self.user_entry.get()

        try:
            if value != '':
                value = int(value)  # Check if it is integer

                if int(value) not in range(0, 100):  # Check if it is in range
                    raise ValueError

        except ValueError:
            self.user_info.config(text="Napačna identifikacija",foreground="red")
            self.login_button.config(state='disabled')

        else:
            self.user_info.config(text="")
            self.login_button.config(state='normal')

    def show_login(self):
        self.login_button = Button(self, text="Prijava",  command=self.userLogin, style="style1.TButton")
        self.login_button.grid(row=4, column=0, pady=20, sticky="nw")

        self.login_status_label = Label(self, text="")
        self.login_status_label.grid(row=5, column=0, sticky="nw",columnspan=4)

    def show_test_device_info(self):
        self.test_device_info = {}

        self.test_device_info['labelframe'] = LabelFrame(self,text="Podrobnosti")
        self.test_device_info['labelframe'].grid(row=1,column=3,sticky=W,rowspan=3)

        self.test_device_info['frame'] = Frame(self.test_device_info['labelframe'])
        self.test_device_info['frame'].grid(row=0,column=0,padx=10,pady=10)

        self.test_device_info['title'] = Label(self.test_device_info['frame'], text=self.controller.userdata.test_devices[self.controller.userdata.test_device]['name'])
        self.test_device_info['title'].grid(row=0, column=0, sticky="n")

        self.test_device_info['ip_title'] = Label(self.test_device_info['frame'], text="IP Naslov:")
        self.test_device_info['ip_title'].grid(row=1, column=0, sticky="w")
        self.test_device_info['ip'] = Label(self.test_device_info['frame'], text=self.controller.userdata.test_devices[self.controller.userdata.test_device]['ip'])
        self.test_device_info['ip'].grid(row=1, column=1, sticky="w")

        self.test_device_info['port_title'] = Label(self.test_device_info['frame'], text="Port:")
        self.test_device_info['port_title'].grid(row=2, column=0, sticky="w")
        self.test_device_info['port'] = Label(self.test_device_info['frame'], text=self.controller.userdata.test_devices[self.controller.userdata.test_device]['port'])
        self.test_device_info['port'].grid(row=2, column=1, sticky="w")


    def set_test_device(self,test_device,set = False):
        if set:
            self.test_device_list.set(test_device)

        found = False
        for i in range(len(self.controller.userdata.test_devices)):
            if self.controller.userdata.test_devices[i]['name'] == test_device:
                self.controller.userdata.test_device = i
                self.test_device_list.set(test_device)
                found = True
                break

        if not found:  # If not found, use first on list
            self.controller.userdata.test_device = 0
            self.test_device_list.set(self.controller.userdata.test_devices[test_device]['name'])

        # Update extra info
        self.test_device_info['title'].config(text=self.controller.userdata.test_devices[self.controller.userdata.test_device]['name'])
        self.test_device_info['ip'].config(text=self.controller.userdata.test_devices[self.controller.userdata.test_device]['ip'])
        self.test_device_info['port'].config(text=self.controller.userdata.test_devices[self.controller.userdata.test_device]['port'])

        # Set test device also in PropertiesPage (it always exist because it is the same list)
        self.controller.get_frame("PropertiesPage").set_test_device(test_device)

    def userLogin(self):
        # Assuming test_type and id_num are correct (Login button was enabled)
        # test_type is sent to server when start test applied
        self.controller.userdata.id_num = int(self.user_entry.get())
        self.controller.userdata.test_type = self.test_type_names.index(self.test_type_list.get())

        ip = self.controller.userdata.test_devices[self.controller.userdata.test_device]['ip']
        port = int(self.controller.userdata.test_devices[self.controller.userdata.test_device]['port'])

        #  Solve message 'disconnected' with deferred? When successful closed, fire deferred to connect
        if self.controller.userdata.connected:
            self.controller.userdata.protocol.close()

        self.controller.userdata.protocol = reactor.connectTCP(ip, port, clientfactory(self.controller), 3)


class TesterPage(Frame):
    def __init__(self, parent, controller):
        # Initialisation header

        Frame.__init__(self, parent)
        self.bind("<<ShowFrame>>", self.on_show_frame)
        self.controller = controller

        self.columnconfigure(1, weight=1)
        self.rowconfigure(3, weight=1)
        self.grid(row=0, column=0, sticky="news")

        self.logo = PhotoImage(file=self.controller.userdata.directory + "/images/strips.gif")
        self.copyright_img = Label(self, image=self.logo)
        self.copyright_img.grid(row=0, column=2, sticky=NE, columnspan=2)  # Upostevaj colspan

        self.show_title()
        self.make_info_frame()
        self.make_task_frame()
        self.make_messager_frame()
        self.make_stats_frame()

    def on_show_frame(self, event):
        #print("You got to TesterPage")

        self.display_info_frame()
        self.reset_test_count_label.grid_forget()

    def show_title(self):
        self.tester_title = Label(self, text="Operativni uporabniški vmesnik", font=self.controller.title_font)
        self.tester_title.grid(row=0, column=0, sticky="nw", pady=(0, 20),columnspan=2)

    def make_info_frame(self):
        self.info_frame = Frame(self)
        self.info_text = Label(self.info_frame, text="Ni povezave s testno napravo.")
        self.info_frame_extra_text = Label(self.info_frame, text="")

    def display_info_frame(self):
        self.info_frame.grid(row=1, column=0, sticky="news", columnspan=3)
        self.info_text.grid(row=1, column=0, sticky="news")
        self.info_frame_extra_text.grid(row=1, column=1, sticky="news",padx=(50,0))

    def make_task_frame(self):
        self.task_frame = Frame(self)
        self.task_frame.columnconfigure(0, weight=1)
        self.task_frame.rowconfigure(1, weight=1)

        self.task_title = Label(self.task_frame, text="FAZA TESTIRANJA", font=self.controller.subtitle_font)

        self.test_task_frame = Frame(self.task_frame)
        self.test_task_frame.config(borderwidth=2, relief="groove")

        self.canvas = Canvas(self.test_task_frame)
        #self.canvas.columnconfigure(0, weight=1)

        self.canvas_frame = Frame(self.canvas)
        #self.canvas_frame.columnconfigure(0, weight=1)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.canvas_frame, anchor="nw")

        self.test_task_frame_inner = Frame(self.canvas_frame)
        self.test_task_frame_inner.columnconfigure(0,weight=1)

        self.task_scrollbar = Scrollbar(self.canvas, orient="vertical", command=self.canvas.yview)
        self.canvas['yscrollcommand'] = self.task_scrollbar.set

        self.canvas_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.frame_width)

        self.task_result = Label(self.task_frame, text="PRIPRAVLJEN", borderwidth=2, relief="groove", justify="center", padding=(20, 10, 20, 10), background="gray")

        self.manual_test_frame = Frame(self.task_frame)
        self.manual_test_frame.columnconfigure(0, weight=1)

        # Display test time, last test time
        self.test_time_label = Label(self.manual_test_frame, text="")

        self.manual_stop_button = Button(self.manual_test_frame, text="STOP", command=self.stop_test_device, style="style1.TButton")
        self.manual_start_button = Button(self.manual_test_frame, text="START", command=self.start_test_device, style="style1.TButton")



    def frame_width(self, event):
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)

    def on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_mouse_wheel(self, event):
        if event.num == 4:
            self.canvas.yview('scroll', -1, 'units')
        elif event.num == 5:
            self.canvas.yview('scroll', 1, 'units')

    def on_mouse_wheel_bind(self, event):
        self.canvas.bind_all('<MouseWheel>', self.rollWheel)

    def on_mouse_wheel_unbind(self, event):
        self.canvas.unbind_all('<MouseWheel>')

    def rollWheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")




    def display_task_frame(self):
        self.task_frame.grid(row=3, column=0, sticky="news")
        self.task_title.grid(row=0, column=0, sticky="nw", pady=10)



        self.manual_test_frame.grid(row=3,column=0,sticky="wes")
        self.test_time_label.grid(row=0,column=0, pady=5, padx=10, sticky="we", columnspan=2)
        self.manual_stop_button.grid(row=1, column=0, pady=10, padx=10, sticky="we")
        self.manual_start_button.grid(row=1, column=1, pady=10, padx=10, sticky="we")

        self.test_task_frame.grid(row=1,column=0, pady=5, sticky="news")
        self.canvas.grid(row=0, column=0, sticky="news")
        self.test_task_frame_inner.grid(row=0, column=0, sticky="news")
        #self.task_scrollbar.pack(side=RIGHT, fill=Y)
        self.task_result.grid(row=2, column=0, pady=5, padx=5, sticky="wes")

        # Bind canvas window to react to scrollbar
        self.canvas.bind('<Enter>', self.on_mouse_wheel_bind)
        self.canvas.bind('<Leave>', self.on_mouse_wheel_unbind)




    def hide_task_frame(self):
        self.task_frame.grid_forget()

    def update_time_label(self):
        self.after_cancel(self.time_update)

        if self.controller.userdata.start_test is not None:
            test_time = pytz.utc.localize(datetime.datetime.utcnow()) - self.controller.userdata.start_test

            # Removes the bug, where time is negative due to RPi and PC clock difference (-1day 23:59:59)
            #if test_time >= datetime.timedelta(0):
            self.test_time_label.config(text="Čas testiranja: {}" . format(str(test_time)[:-7]))  # Strip off miliseconds

            self.time_update = self.after(1000, self.update_time_label)

    def make_messager_frame(self):
        self.messager_frame = Frame(self)

        self.messager_frame.columnconfigure(0, weight=1)
        self.messager_frame.rowconfigure(1, weight=1)

        self.messager_title = Label(self.messager_frame, text="INFORMACIJE", font=self.controller.subtitle_font)

        self.textbox = Text(self.messager_frame)
        self.textbox.tag_config('red', foreground="red")
        self.textbox.tag_config('green', foreground="green")
        self.textbox.tag_config('yellow', foreground="#c99c22")
        self.textbox.tag_config('blue', foreground="blue")
        self.textbox.tag_config('purple', foreground="magenta")
        self.textbox.tag_config('black', foreground="black")
        self.textbox.tag_config('grey', foreground="grey")
        self.textbox.config(state="disabled")

        self.scrollbar = Scrollbar(self.messager_frame,command=self.textbox.yview)
        self.scrollbar.grid(row=1,column=1,sticky="ns")
        self.textbox['yscrollcommand'] = self.scrollbar.set

    def display_messager_frame(self):
        self.messager_frame.grid(row=3, column=1, sticky="news", padx=5)
        self.messager_title.grid(row=0, column=0, sticky="nw", pady=10)
        self.textbox.grid(row=1,column=0,sticky="news")

    def hide_messager_frame(self):
        self.messager_frame.grid_forget()

    def add_message(self,message,tag):
        self.textbox.configure(state='normal')
        self.textbox.insert(END, message, tag)
        self.textbox.configure(state='disabled')
        self.textbox.see("end")

    def make_stats_frame(self):
        self.stats_frame = Frame(self)

        self.stats_title = Label(self.stats_frame, text="DODATNO", font=self.controller.subtitle_font)

        self.labelframe = LabelFrame(self.stats_frame, text="Statistika")
        self.labelframe.config(borderwidth=2, relief="groove")

        self.countdate = Label(self.labelframe, text="Serija: Neznano")
        self.local_title = Label(self.labelframe, text="Tvoji:")
        self.good_local_label = Label(self.labelframe, text="Dobri: N/A")
        self.bad_local_label = Label(self.labelframe, text="Slabi: N/A")
        self.sum_local_label = Label(self.labelframe, text="Skupaj: N/A")
        self.suc_local_label = Label(self.labelframe, text="Uspešnost: N/A")

        self.global_title = Label(self.labelframe, text="Globalno:")
        self.good_global_label = Label(self.labelframe, text="Dobri: N/A")
        self.bad_global_label = Label(self.labelframe, text="Slabi: N/A")
        self.sum_global_label = Label(self.labelframe, text="Skupaj: N/A")
        self.suc_global_label = Label(self.labelframe, text="Uspešnost: N/A")

        self.reset_test_count_button = Button(self.labelframe, text="Ponastavi števec", command=self.reset_test_count, style="style1.TButton")
        self.reset_test_count_label = Label(self.labelframe, text="")

        self.service_frame = LabelFrame(self.stats_frame, text="Servis in kalibracija")
        self.service_frame.config(borderwidth=2,relief="groove")

        self.service_counter = Label(self.service_frame, text="Št. ciklov do servisa: N/A")
        self.calibration_date = Label(self.service_frame, text="Kalibracija: N/A")

        self.shutdown_frame = Frame(self.stats_frame)
        self.shutdown_title = Label(self.shutdown_frame, text="IZKLOP", font=self.controller.subtitle_font)
        self.shutdown_button = Button(self.shutdown_frame, text="Izklopi testno napravo",  command=self.shutdown, style="style1.TButton")

        self.safety_frame = Frame(self.stats_frame)
        # Add ESD, HV...

        self.make_manual_frame()

    def display_stats_frame(self):
        self.stats_frame.grid(row=3, column=2, sticky="nw")
        self.stats_title.grid(row=0, column=0, sticky="nw", pady=10)

        self.labelframe.grid(row=1, column=0, sticky="news", padx=5)

        self.countdate.grid(row=0, column=0, sticky="new", padx=5, pady=5, columnspan=2)

        self.local_title.grid(row=1, column=0, sticky="new", padx=5, pady=5)
        self.good_local_label.grid(row=2, column=0, sticky="w", padx=5)
        self.bad_local_label.grid(row=3, column=0, sticky="w", padx=5)
        self.sum_local_label.grid(row=4, column=0, sticky="w", padx=5)
        self.suc_local_label.grid(row=5, column=0, sticky="w", padx=5, pady=(5, 0))

        self.global_title.grid(row=1, column=1, sticky="new", pady=5, padx=(20, 5))
        self.good_global_label.grid(row=2, column=1, sticky="w", padx=(20, 5))
        self.bad_global_label.grid(row=3, column=1, sticky="w", padx=(20, 5))
        self.sum_global_label.grid(row=4, column=1, sticky="w", padx=(20, 5))
        self.suc_global_label.grid(row=5, column=1, sticky="w", padx=(20, 5), pady=(5, 0))

        self.reset_test_count_button.grid(row=6, column=0, padx=5, pady=(10, 5), sticky="w", columnspan=2)

        self.service_frame.grid(row=2,column=0,sticky="news", padx=5, pady=5)

        self.service_counter.grid(row=0, column=0, sticky="new", padx=5, pady=(5,0))
        self.calibration_date.grid(row=1, column=0, sticky="new", padx=5, pady=(0,5))

        self.shutdown_frame.grid(row=3,column=0,sticky="news")
        self.shutdown_title.grid(row=0, column=0, sticky="nw", pady=10)
        self.shutdown_button.grid(row=1, column=0, pady=5, sticky=W)

        self.safety_frame.grid(row=4,column=0,sticky="news")

    def hide_stats_frame(self):
        self.stats_frame.grid_forget()

    def make_tasks(self):  # Show new task when GUI active
        # All tasks are displayed together, so this function is called only once (when GUI connects to the server)
        # Server responds with list of all tasks available. Their states are updated.

        self.test_task = []
        for task in self.controller.userdata.task:
            self.test_task.append({})  # Append dictionary to test task

            bg_color_list = {"fail": "#e01a00", "ok": "#00ba06", "work": "#0059ea", "idle": "gray"}
            fg_color = "black"

            if task['enable']:
                bg_color = bg_color_list[task['state']]  # Take color from colorlist
            else:
                bg_color = "#cccccc"
                fg_color = "gray"

            self.test_task[-1]['slug'] = task['slug']
            self.test_task[-1]['frame'] = Frame(self.test_task_frame_inner)
            self.test_task[-1]['frame'].columnconfigure(0, weight=1)
            self.test_task[-1]['label'] = Label(self.test_task[-1]['frame'], text=task['name'], borderwidth=2, relief="groove", justify="center", padding=(30, 10, 30, 10), background=bg_color, foreground=fg_color)
            self.test_task[-1]['info'] = Label(self.test_task[-1]['frame'], text="")

            '''
            # Check if task has definition
            if 'definition' in task:
                self.test_task[-1]['definition'] = []

                for definition in task['definition']:
                    self.test_task[-1]['definition'].append({})
            
            extra_info = ""
            for definition_number in range(self.controller.userdata.num_of_definitions):
                if self.controller.userdata.definition[definition_number]['definition_task'] == self.controller.userdata.task[task_number]['task_slug'] and len(self.controller.userdata.definition[definition_number]['definition_extra_info']):

                    # update task here and on gui
                    definition_extra_info = self.controller.userdata.definition[definition_number]['definition_extra_info']
                    start_pos = definition_extra_info.find("[D]")

                    if start_pos != -1:
                        definition_extra_info = definition_extra_info[:start_pos] + str(self.controller.userdata.definition[definition_number]['definition_value'].get()) + definition_extra_info[start_pos + 4:]

                    extra_info = extra_info + definition_extra_info + "\n"

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
            
            '''

    def display_tasks(self):
        for task_number in range(len(self.controller.userdata.task)):
            self.test_task[task_number]['frame'].grid(row=1+task_number, column=0, padx=5,sticky="new")
            self.test_task[task_number]['label'].grid(row=0, column=0,sticky="we",pady=5)
            #self.test_task[task_number]['info'].grid(row=1, column=0,sticky="we",padx=10)

    def delete_tasks(self):
        # Destroy task widgets
        if len(self.controller.userdata.task):  # Check if any tasks have been made
            for task_number in range(len(self.test_task)):
                if self.test_task[task_number]['frame'].winfo_exists():
                    # Destroy all children widgets of current task frame
                    for child in self.test_task[task_number]['frame'].winfo_children():
                        child.destroy()

                    # Destroy parent frame
                    self.test_task[task_number]['frame'].destroy()

                self.test_task[task_number].clear()



    def shutdown(self):
        self.controller.userdata.protocol.send({"command": "shutdown"})  # Shut down TN

    def stop_test_device(self):  # Stop test
        self.controller.userdata.protocol.send({"command": "stop_test"})

    def start_test_device(self):   # Start test
        self.controller.userdata.protocol.send({"command": "start_test"})

    def reset_test_count(self):
        # Set count date to current date
        utc_date = pytz.utc.localize(datetime.datetime.utcnow()) + self.controller.userdata.timedif

        self.controller.userdata.protocol.send({"command": "count", "date": utc_date.isoformat()})

        self.reset_test_count_label.config(text="Ponastavljeno.", foreground="green")
        self.reset_test_count_label.grid(row=7, column=0, sticky="w", padx=5, pady=(0,5))


    # Manual Frame
    def make_manual_frame(self):
        self.manual_frame = Frame(self.stats_frame)
        self.manual_title = Label(self.manual_frame, text="NAVODILA ZA UPORABO", font=self.controller.subtitle_font)

        self.manual_text = Label(self.manual_frame, text="")
        self.manual_link = Label(self.manual_frame, text="", foreground="blue", cursor="hand2")

        self.manual_link.bind("<Button-1>", self.show_manual)

    def display_manual_frame(self):
        self.manual_frame.grid(row=5, column=0, sticky="news")
        self.manual_title.grid(row=0, column=0, sticky="nw", pady=10)
        self.manual_text.config(text="Navodila za uporabo testne naprave\n{} so dostopna na spodnji povezavi:" . format(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']))
        self.manual_link.config(text="Navodila za uporabo {}" . format(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']))

        self.manual_text.grid(row=1, column=0, sticky="w", pady=5)
        self.manual_link.grid(row=2, column=0, pady=5, sticky="w")

    def show_manual(self, event):  # Open test device manual (preffered in PDF)
        webbrowser.open(self.controller.userdata.path_manual)

    '''
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
                    self.task_result.config(text="VZDRzEVANJE",background="#e2df00")
                else:
                    self.task_result.config(text="PRIPRAVLJEN",background="grey")


            if "esd" in msg or "high_voltage" in msg:
                self.display_custom_attr()
'''

class PropertiesPage(Frame):
    def __init__(self, parent, controller):
        # Initialisation header

        Frame.__init__(self, parent)
        self.bind("<<ShowFrame>>", self.on_show_frame)
        self.controller = controller

        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)
        self.grid(row=0, column=0, sticky="news")

        self.logo = PhotoImage(file=self.controller.userdata.directory + "/images/strips.gif")
        self.copyright_img = Label(self, image=self.logo)
        self.copyright_img.grid(row=0, column=2, sticky=NE, columnspan=2)  # Upostevaj colspan

        self.make_login_frame()

        self.make_left_frame()
        self.make_center_frame()
        self.make_right_frame()

        self.show_title()
        self.display_login_frame()


    def on_show_frame(self, event):
        #print("You got to PropertiesPage")

        # Hide all temporary messages
        self.login_text_label.grid_forget()
        self.save_test_device_label.grid_forget()
        self.log_info_label.grid_forget()
        self.save_task_settings_label.grid_forget()
        self.count_reset_label.grid_forget()
        self.service_save_label.grid_forget()
        self.cal_apply_label.grid_forget()
        self.factory_info_label.grid_forget()

    def show_title(self):
        self.properties_title = Label(self, text="Nastavitve", font=self.controller.title_font)
        self.properties_title.grid(row=0, column=0, sticky="nw", pady=(0, 20), columnspan=2)



    # Login Frame
    def make_login_frame(self):
        self.login_frame = Frame(self)

        self.login_label = Label(self.login_frame, text="Za nadaljevanje se morate prijaviti.")
        self.login_password_label = Label(self.login_frame, text="Geslo:")
        self.login_password_entry = Entry(self.login_frame, width=15, show="*")
        self.login_button = Button(self.login_frame, text="Prijava", command=self.on_user_login, style="style1.TButton")
        self.login_text_label = Label(self.login_frame, text="")

    def display_login_frame(self):
        self.login_password_entry.delete(0, "end")  # Empty password entry

        self.login_frame.grid(row=1,column=0,sticky="nw")
        self.login_label.grid(row=0, column=0, sticky="nw", pady=(0,10), columnspan=2)
        self.login_password_label.grid(row=1, column=0, sticky="nw", pady=5)
        self.login_password_entry.grid(row=1, column=1, sticky="nw")
        self.login_button.grid(row=2, column=0, pady=20, sticky="nw")

        self.login_password_entry.bind('<Return>', lambda event: self.on_user_login())

    def hide_login_frame(self):
        self.login_frame.grid_forget()
        self.login_text_label.grid_forget()
        self.login_password_entry.unbind('<Return>')

    def on_user_login(self):
        password = self.login_password_entry.get()

        if password == self.controller.userdata.admin_pass:
            # Login successful - redirect to properties page
            if self.controller.userdata.connected:  # Working on TN
                self.controller.userdata.protocol.send({"command": "maintenance", "status": "request"})  # Ask server for maintenance (handling in lineRecieved)
            else:
                self.hide_login_frame()

                self.display_left_frame()

                self.display_center_frame()
        else:
            self.login_text_label.config(text="Nepravilno geslo!",foreground="red")
            self.login_text_label.grid(row=3, column=0, sticky="nw",columnspan=2)


    # Left Frame
    def make_left_frame(self):
        self.left_frame = Frame(self)

        self.make_logout_frame()
        self.make_log_frame()
        self.make_shutdown_frame()
        self.make_manual_frame()

    def display_left_frame(self):
        self.left_frame.grid(row=1,column=0, sticky="news")

        self.display_config_frame()
        self.display_logout_frame()

    def hide_left_frame(self):
        self.left_frame.grid_forget()

        for child in self.left_frame.winfo_children():
            child.grid_forget()

    # Config Frame
    def make_config_frame(self):
        self.test_device_selected = None

        # Config frame
        self.config_frame = Frame(self.left_frame)
        self.config_title = Label(self.config_frame, text="KONFIGURACIJA", font=self.controller.subtitle_font)

        self.test_device_label = Label(self.config_frame, text="Testna naprava:")
        self.test_device_list = StringVar(self)

        test_device_names = []
        for test_device in self.controller.userdata.test_devices:
            test_device_names.append(test_device['name'])

        self.test_device_option = OptionMenu(self.config_frame, self.test_device_list, test_device_names[0], *test_device_names, command=self.set_test_device)

        # Set first TN to be selected
        self.test_device_list.set(test_device_names[0])

        self.ip_label = Label(self.config_frame, text="IP naslov:")
        self.ip_entry = Entry(self.config_frame, width=20)

        self.port_label = Label(self.config_frame, text="Port:")
        self.port_entry = Entry(self.config_frame, width=10)

        self.save_test_device_button = Button(self.config_frame, text="Shrani testno napravo",  command=self.save_test_device_settings, style="style1.TButton")
        self.save_test_device_label = Label(self.config_frame, text="")

    def display_config_frame(self):
        self.config_frame.grid(row=0, column=0, sticky="news")
        self.config_title.grid(row=0, column=0, sticky="nw", pady=10)

        self.test_device_label.grid(row=1, column=0, sticky="nw")
        self.test_device_option.grid(row=1, column=1, sticky="nw")

        self.ip_label.grid(row=2, column=0, sticky="w", pady=5)
        self.ip_entry.grid(row=2, column=1, sticky="w")

        self.port_label.grid(row=3, column=0, sticky="w", pady=5)
        self.port_entry.grid(row=3, column=1, sticky="w")

        self.save_test_device_button.grid(row=4, column=0, pady=10, sticky=W,columnspan=2)



    # Update OptionMenu for test devices (called every on_show_frame)
    def update_test_devices(self):
        self.test_device_option['menu'].delete(0, 'end')

        for test_device in self.controller.userdata.test_devices:
            self.test_device_option['menu'].add_command(label=test_device['name'], command=lambda value=test_device['name']: self.set_test_device(value, True))

        # Set previously device if exist (otherwise set it to first one)
        self.set_test_device(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name'], True)

    def set_test_device(self, test_device, set = False):
        if set:
            self.test_device_list.set(test_device)

        found = False
        self.test_device_selected = 0
        for i in range(len(self.controller.userdata.test_devices)):
            if self.controller.userdata.test_devices[i]['name'] == test_device:
                self.test_device_selected = i
                self.test_device_list.set(test_device)
                found = True
                break

        if not found:  # If not found, use first on list
            self.test_device_list.set(self.controller.userdata.test_devices[0])

        # Update config info
        self.ip_entry.delete(0, END)
        self.port_entry.delete(0, END)
        self.ip_entry.insert(END,self.controller.userdata.test_devices[self.test_device_selected]['ip'])
        self.port_entry.insert(END,self.controller.userdata.test_devices[self.test_device_selected]['port'])

    def save_test_device_settings(self):
        # Get variables
        ip = self.ip_entry.get()
        try:
            # Validate IP address
            socket.inet_aton(ip)

            port = int(self.port_entry.get())  # Check if it is integer

            if int(port) not in range(80, 65535):  # Check if it is in range
                raise ValueError

            # Append changes
            self.controller.userdata.test_devices[self.test_device_selected]['ip'] = ip
            self.controller.userdata.test_devices[self.test_device_selected]['port'] = port

            # Save to file
            with open(self.controller.userdata.directory + '/config.strips', 'w') as data_file:
                json.dump(self.controller.userdata.test_devices, data_file)

            self.save_test_device_label.config(text="Testna naprava {} posodobljena." . format(self.controller.userdata.test_devices[self.test_device_selected]['name']), foreground="green")
        except socket.error:
            self.save_test_device_label.config(text="IP naslov neveljaven.", foreground="red")

        except ValueError:
            self.save_test_device_label.config(text="Port neveljaven.", foreground="red")

        except Exception:
            self.save_test_device_label.config(text="Datoteke 'config.strips' ni mogoče shraniti!", foreground="red")

        finally:
            self.save_test_device_label.grid(row=5, column=0, sticky="w",columnspan=2)

    # Shutdown Frame
    def make_shutdown_frame(self):
        self.shutdown_frame = Frame(self.left_frame)
        self.shutdown_title = Label(self.shutdown_frame, text="IZKLOP", font=self.controller.subtitle_font)
        self.shutdown_button = Button(self.shutdown_frame, text="Izklopi testno napravo",  command=self.shutdown, style="style1.TButton")

    def display_shutdown_frame(self):
        self.shutdown_frame.grid(row=4,column=0,sticky="news")
        self.shutdown_title.grid(row=0, column=0, sticky="nw", pady=10)
        self.shutdown_button.grid(row=1, column=0, pady=5, sticky=W)

    def shutdown(self):
        self.controller.userdata.protocol.send({"command": "shutdown"})  # Shut down TN


    # Logout Frame
    def make_logout_frame(self):
        # Logout frame
        self.logout_frame = Frame(self.left_frame)
        self.logout_title = Label(self.logout_frame, text="ODJAVA", font=self.controller.subtitle_font)

        self.logout_text = Label(self.logout_frame, text="Za nadaljno uporabo testne naprave se\nmorate odjaviti iz nastavitev.")
        self.logout_button = Button(self.logout_frame, text="Odjava", command=self.logout, style="style1.TButton")

    def display_logout_frame(self):
        self.logout_frame.grid(row=2, column=0, sticky="news")
        self.logout_title.grid(row=0, column=0, sticky="nw", pady=10)
        self.logout_text.grid(row=1, column=0, sticky="w", pady=5)
        self.logout_button.grid(row=2, column=0, pady=5, sticky=W)

    def logout(self):
        self.hide_left_frame()
        self.hide_center_frame()
        self.hide_right_frame()

        self.display_login_frame()

        if self.controller.userdata.connected:  # User is connected to TN
            # User has defenitely had mainenance as master
            self.controller.userdata.protocol.send({"command": "maintenance", "status": "drop"})  # Send server to drop maintenance mode



    # Log frame
    def make_log_frame(self):
        self.log_frame = Frame(self.left_frame)
        self.log_title = Label(self.log_frame, text="ZAPISNIK", font=self.controller.subtitle_font)

        self.log_label = Label(self.log_frame, text="Zapisnik si shranjuje podatke o testiranih izdelkih.")

        self.log_start_time_label = Label(self.log_frame, text="Od:")

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

        # Set end date to today (can't look into future)
        start_date = datetime.date.today() - datetime.timedelta(days=1)
        end_date = datetime.date.today()

        self.log_start_time_day_option = OptionMenu(self.log_frame, self.start_day_variable,start_date.day,*self.day_list)
        self.log_start_time_month_option = OptionMenu(self.log_frame, self.start_month_variable,self.month_list[start_date.month - 1],*self.month_list)
        self.log_start_time_year_option = OptionMenu(self.log_frame, self.start_year_variable,start_date.year,*self.year_list)

        self.log_end_time_label = Label(self.log_frame, text="Do:")

        self.log_end_time_day_option = OptionMenu(self.log_frame, self.end_day_variable, end_date.day, *self.day_list)
        self.log_end_time_month_option = OptionMenu(self.log_frame, self.end_month_variable, self.month_list[end_date.month - 1], *self.month_list)
        self.log_end_time_year_option = OptionMenu(self.log_frame, self.end_year_variable, end_date.year, *self.year_list)

        self.log_button = Button(self.log_frame, text="Prenesi zapisnik",command=self.download_log, style="style1.TButton")
        self.log_info_label = Label(self.log_frame, text="")

    def display_log_frame(self):
        self.log_frame.grid(row=3, column=0, sticky="nw")
        self.log_title.grid(row=0, column=0, sticky="nw", pady=10)
        self.log_label.grid(row=1, column=0, sticky="w", pady=5,columnspan=5)
        self.log_start_time_label.grid(row=2, column=0, sticky="w", pady=5)

        self.log_start_time_day_option.grid(row=2, column=1, sticky=W)
        self.log_start_time_month_option.grid(row=2, column=2, sticky=W)
        self.log_start_time_year_option.grid(row=2, column=3, sticky=W)

        self.log_end_time_label.grid(row=3, column=0, sticky="w", pady=5)

        self.log_end_time_day_option.grid(row=3, column=1, sticky=W)
        self.log_end_time_month_option.grid(row=3, column=2, sticky=W)
        self.log_end_time_year_option.grid(row=3, column=3, sticky=W)

        self.log_button.grid(row=4, column=0, pady=10, sticky=W, columnspan=5)

    def download_log(self):
        self.file = filedialog.asksaveasfilename(initialdir = "/",title = "Shrani zapisnik",filetypes = (("csv datoteka","*.csv"),("vse datoteke","*.*")))

        if self.file: # asksaveasfile return `None` if dialog closed with "cancel".
            # Change log file path
            self.controller.userdata.log_path = self.file

            st_day = int(self.start_day_variable.get())
            st_year = int(self.start_year_variable.get())

            en_day = int(self.end_day_variable.get())
            en_year = int(self.end_year_variable.get())

            st_month = self.month_list.index(self.start_month_variable.get())
            en_month = self.month_list.index(self.end_month_variable.get())

            try:
                st_date = datetime.date(st_year, st_month, st_day)
                en_date = datetime.date(en_year, en_month, en_day)

                self.log_info_label.config(text="Prenašanje zapisnika...", foreground="black")

                # Send server command to send log
                #self.controller.userdata.protocol.send({"command": "download_log", "st_date": st_date.strftime("%Y.%m.%d"), "en_date": en_date.strftime("%Y.%m.%d")})
                # GET UTC DATE AND SEND IT TOGETHER

                '''
                if "log_file" in msg:
                    if msg['log_file']:
                        self.log_info_label = Label(self.log_frame, text="Zapisnik uspesno prenesen.",foreground="green")
                    else:
                        self.log_info_label = Label(self.log_frame, text="Napaka pri prenasanju zapisnika.", foreground="red")
    
                    self.log_info_label.grid(row=5, column=0, sticky="w", pady=5, columnspan=5)
                '''


            except ValueError:  # Invalid date entered
                self.log_info_label.config(text="Izbrani datum je neveljaven!", foreground="red")

            finally:
                self.log_info_label.grid(row=5, column=0, sticky="w", pady=5, columnspan=5)





    # Manual Frame
    def make_manual_frame(self):
        self.manual_frame = Frame(self.left_frame)
        self.manual_title = Label(self.manual_frame, text="NAVODILA ZA UPORABO", font=self.controller.subtitle_font)

        self.manual_text = Label(self.manual_frame, text="")
        self.manual_link = Label(self.manual_frame, text="", foreground="blue", cursor="hand2")

        self.manual_link.bind("<Button-1>", self.show_manual)

    def display_manual_frame(self):
        self.manual_frame.grid(row=5, column=0, sticky="news")
        self.manual_title.grid(row=0, column=0, sticky="nw", pady=10)
        self.manual_text.config(text="Navodila za uporabo testne naprave\n{} so dostopna na spodnji povezavi:" . format(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']))
        self.manual_link.config(text="Navodila za uporabo {}" . format(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']))

        self.manual_text.grid(row=1, column=0, sticky="w", pady=5)
        self.manual_link.grid(row=2, column=0, pady=5, sticky="w")

    def show_manual(self, event):  # Open test device manual (preffered in PDF)
        webbrowser.open(self.controller.userdata.path_manual)








    # Center Frame
    def make_center_frame(self):
        self.center_frame = Frame(self)
        self.center_frame.columnconfigure(0, weight=1)
        self.center_frame.rowconfigure(2, weight=1)

        self.center_title = Label(self.center_frame, text="TESTNA NAPRAVA", font=self.controller.subtitle_font)

        self.test_device_tasks_frame = Frame(self.center_frame)
        self.test_device_tasks_frame.config(borderwidth=2, relief="groove")
        self.test_device_tasks_frame.columnconfigure(0, weight=1)
        self.test_device_tasks_frame.rowconfigure(0, weight=1)

        self.canvas = Canvas(self.test_device_tasks_frame)
        self.canvas.columnconfigure(0, weight=1)

        self.canvas_frame = Frame(self.canvas)
        self.canvas_frame.columnconfigure(0, weight=1)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.canvas_frame, anchor="nw")

        self.scrollbar = Scrollbar(self.canvas, orient="vertical", command=self.canvas.yview)
        self.canvas['yscrollcommand'] = self.scrollbar.set

        self.canvas_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.frame_width)

        self.center_info = Label(self.center_frame, text="Trenutno ni povezave z nobeno testno napravo.")

        self.save_task_settings_button = Button(self.center_frame, text="Shrani nastavitve nalog", command=self.save_tasks, state="disabled", style="style1.TButton")
        self.save_task_settings_label = Label(self.center_frame, text="")

    def display_center_frame(self):
        self.center_frame.grid(row=1,column=1, sticky="news", padx=10)
        self.center_title.grid(row=0, column=0, sticky="nw", pady=10)

        if self.controller.userdata.connected:
            self.center_info.config(text="Trenutno povezan na: {}" . format(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']))

            self.test_device_tasks_frame.grid(row=2,column=0,sticky="news")
            self.canvas.grid(row=0, column=0, sticky="news")
            self.scrollbar.pack(side=RIGHT, fill=Y)

            # Bind canvas window to react to scrollbar
            self.canvas.bind('<Enter>', self.on_mouse_wheel_bind)
            self.canvas.bind('<Leave>', self.on_mouse_wheel_unbind)

            self.save_task_settings_button.config(state="normal")
        else:
            self.center_info.config(text="Trenutno ni povezave z nobeno testno napravo.")

            self.save_task_settings_button.config(state="disabled")

        self.center_info.grid(row=1, column=0, sticky="new", pady=5,columnspan=2)

        self.save_task_settings_button.grid(row=3, column=0, pady=10, sticky=W)

    def hide_center_frame(self):
        self.center_frame.grid_forget()

        for child in self.center_frame.winfo_children():
            child.grid_forget()

    def frame_width(self, event):
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)

    def on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_mouse_wheel(self, event):
        if event.num == 4:
            self.canvas.yview('scroll', -1, 'units')
        elif event.num == 5:
            self.canvas.yview('scroll', 1, 'units')

    def on_mouse_wheel_bind(self, event):
        self.canvas.bind_all('<MouseWheel>', self.rollWheel)

    def on_mouse_wheel_unbind(self, event):
        self.canvas.unbind_all('<MouseWheel>')

    def rollWheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")



    def make_tasks(self):  # Show new task when GUI active
        # All tasks are displayed together, so this function is called only once (when GUI connects to the server)
        # Server responds with list of all tasks available. Their states are updated.

        self.test_task = []
        for task in self.controller.userdata.task:
            self.test_task.append({})  # Append dictionary to test task
            self.test_task[-1]['slug'] = task['slug']

            self.test_task[-1]['frame'] = Frame(self.canvas_frame)
            self.test_task[-1]['frame'].columnconfigure(3, weight=1)

            # Make IntVar for checkbutton handler
            self.test_task[-1]['checkbutton_var'] = IntVar()
            self.test_task[-1]['checkbutton_var'].set(task['enable'])

            self.test_task[-1]['checkbutton'] = Checkbutton(self.test_task[-1]['frame'], variable=self.test_task[-1]['checkbutton_var'])
            self.test_task[-1]['label'] = Label(self.test_task[-1]['frame'], text=task['name'], font=self.controller.task_font)
            self.test_task[-1]['description'] = Label(self.test_task[-1]['frame'], text=task['desc'])


            if 'definition' in task.keys():
                self.test_task[-1]['definition'] = []

                for definition in task['definition']:
                    self.test_task[-1]['definition'].append({})
                    self.test_task[-1]['definition'][-1]['slug'] = definition['slug']

                    # Make StringVar for entry handler
                    if type(definition['value']) == str:
                        self.test_task[-1]['definition'][-1]['entry_var'] = StringVar()
                    else:
                        self.test_task[-1]['definition'][-1]['entry_var'] = IntVar()

                    self.test_task[-1]['definition'][-1]['entry_var'].set(definition['value'])

                    self.test_task[-1]['definition'][-1]['label'] = Label(self.test_task[-1]['frame'], text="{}:" . format(definition['name']))
                    self.test_task[-1]['definition'][-1]['entry'] = Entry(self.test_task[-1]['frame'], textvariable=self.test_task[-1]['definition'][-1]['entry_var'], width=len(str(definition['value'])) + 2)
                    self.test_task[-1]['definition'][-1]['unit'] = Label(self.test_task[-1]['frame'], text=definition['unit'])
                    self.test_task[-1]['definition'][-1]['description'] = Label(self.test_task[-1]['frame'], text=definition['desc'], font=self.controller.task_font_italic)

    def display_tasks(self):
        for task_number in range(len(self.controller.userdata.task)):
            self.test_task[task_number]['frame'].grid(row=task_number, column=0, padx=(5,20), pady=5, sticky="we")
            self.test_task[task_number]['checkbutton'].grid(row=0, column=0,sticky="w",padx=5,columnspan=3)
            self.test_task[task_number]['label'].grid(row=0, column=0, padx=30, sticky="w", columnspan=3)
            self.test_task[task_number]['description'].grid(row=1, column=0, sticky="we", padx=5, pady=5, columnspan=3)

            if 'definition' in self.test_task[task_number].keys():
                for definition_number in range(len(self.test_task[task_number]['definition'])):
                    self.test_task[task_number]['definition'][definition_number]['label'].grid(row=2 + definition_number, column=0, padx=10, pady=5, sticky="w")
                    self.test_task[task_number]['definition'][definition_number]['entry'].grid(row=2 + definition_number, column=1, padx=(10,0),sticky="w")
                    self.test_task[task_number]['definition'][definition_number]['unit'].grid(row=2 + definition_number, column=2, padx=(0,10),sticky="w")
                    self.test_task[task_number]['definition'][definition_number]['description'].grid(row=2 + definition_number, column=3, padx=10,sticky="we")

    def delete_tasks(self):
        # Destroy task widgets
        if len(self.controller.userdata.task):  # Check if any tasks have been made
            for task_number in range(len(self.test_task)):
                if self.test_task[task_number]['frame'].winfo_exists():
                    # Destroy all children widgets of current task frame
                    for child in self.test_task[task_number]['frame'].winfo_children():
                        child.destroy()

                    # Destroy parent frame
                    self.test_task[task_number]['frame'].destroy()

                self.test_task[task_number].clear()

    def save_tasks(self):

        # Change task data.... server also sends task_update so it will remain the same

        for task in self.controller.userdata.task:  # Loop through all tasks in settings
            for task_number in range(len(self.controller.userdata.task)):
                if self.test_task[task_number]['slug'] == task['slug']:
                    task_index = self.controller.userdata.task.index(task)  # Get index in task list by slug

                    # Change task enable
                    self.controller.userdata.task[task_index]['enable'] = self.test_task[task_number]['checkbutton_var'].get()

                    if 'definition' in task.keys():
                        for definition in task['definition']:
                            for definition_number in range(len(self.test_task[task_index]['definition'])):
                                if self.test_task[task_number]['definition'][definition_number]['slug'] == definition['slug']:
                                    definition_index = self.controller.userdata.task[task_index]['definition'].index(definition)  # Get index in task list by slug

                                    # Change definition value
                                    self.controller.userdata.task[task_index]['definition'][definition_index]['value'] = self.test_task[task_number]['definition'][definition_number]['entry_var'].get()


        # Send to server updated task data
        self.controller.userdata.protocol.send({"command": "task_update", "update": self.controller.userdata.task})

        self.save_task_settings_label.config(text="Shranjeno!", foreground="green")
        self.save_task_settings_label.grid(row=4, column=0, sticky="w")



    # Right Frame
    def make_right_frame(self):
        self.right_frame = Frame(self)
        self.right_frame.columnconfigure(0,weight=1)
        self.right_frame.rowconfigure(1,weight=1)

        self.make_stats_frame()
        self.make_factory_frame()

    def display_right_frame(self):
        self.right_frame.grid(row=1,column=2, sticky="news", padx=10)

        self.display_stats_frame()
        self.display_factory_frame()

    def hide_right_frame(self):
        self.right_frame.grid_forget()

        for child in self.right_frame.winfo_children():
            child.grid_forget()

    # Make stats frame
    def make_stats_frame(self):
        self.stats_frame = Frame(self.right_frame)
        self.stats_title = Label(self.stats_frame, text="STATISTIKA", font=self.controller.subtitle_font)

        self.counter_frame = LabelFrame(self.stats_frame, text="Števec")
        self.counter_frame.config(borderwidth=2, relief="groove")

        self.from_count = Label(self.counter_frame, text="Začetek štetja kosov:")

        self.day_variable = StringVar(self)
        self.month_variable = StringVar(self)
        self.year_variable = StringVar(self)
        self.hour_variable = StringVar(self)

        self.day_list = []
        self.month_list = ['januar', 'februar', 'marec', 'april', 'maj', 'junij', 'julij', 'avgust', 'september', 'oktober', 'november', 'december']
        self.year_list = []
        self.hour_list = []

        for i in range(0, 32):
            self.day_list.append(i + 1)

        for i in range(20):
            self.year_list.append(2005 + i)

        for i in range(24):
            self.hour_list.append("{:02}:00" . format(i))

        self.counter_day_option = OptionMenu(self.counter_frame, self.day_variable, self.controller.userdata.countdate.day, *self.day_list)
        self.counter_month_option = OptionMenu(self.counter_frame, self.month_variable, self.month_list[self.controller.userdata.countdate.month - 1], *self.month_list)
        self.counter_year_option = OptionMenu(self.counter_frame, self.year_variable, self.controller.userdata.countdate.year, *self.year_list)
        self.counter_hour_option = OptionMenu(self.counter_frame, self.hour_variable, "{}:00" . format(self.controller.userdata.countdate.hour), *self.hour_list)

        self.count_set_button = Button(self.counter_frame, text="Nastavi števec", command=self.set_test_count, style="style1.TButton")
        self.count_reset_button = Button(self.counter_frame, text="Ponastavi števec", command=self.reset_test_count, style="style1.TButton")
        self.count_reset_label = Label(self.counter_frame, text="")


        self.service_frame = LabelFrame(self.stats_frame, text="Servis in kalibracija")
        self.service_frame.config(borderwidth=2, relief="groove")

        self.service_label = Label(self.service_frame, text="Št. ciklov do servisa:")

        self.service_entry = Entry(self.service_frame, width=6)
        self.service_entry.insert(END, self.controller.userdata.service)
        self.service_entry.bind("<KeyRelease>", self.on_service_entry)

        self.service_button = Button(self.service_frame, text="Nastavi", command=self.set_service_counter, style="style1.TButton")
        self.service_save_label = Label(self.service_frame, text="")

        self.calibration_label = Label(self.service_frame, text="Datum zadnje kalibracije:")

        self.cal_day_variable = StringVar(self)
        self.cal_month_variable = StringVar(self)
        self.cal_year_variable = StringVar(self)

        self.cal_day_option = OptionMenu(self.service_frame, self.cal_day_variable, self.controller.userdata.calibrationdate.day, *self.day_list)
        self.cal_month_option = OptionMenu(self.service_frame, self.cal_month_variable, self.month_list[self.controller.userdata.calibrationdate.month - 1], *self.month_list)
        self.cal_year_option = OptionMenu(self.service_frame, self.cal_year_variable, self.controller.userdata.calibrationdate.year, *self.year_list)

        self.cal_button = Button(self.service_frame, text="Spremeni", command=self.set_calibration_date, style="style1.TButton")
        self.cal_apply_label = Label(self.service_frame, text="")

    def display_stats_frame(self):
        self.stats_frame.grid(row=0, column=0, sticky="news")
        self.stats_title.grid(row=0, column=0, sticky="nw", pady=10)

        self.counter_frame.grid(row=1, column=0, sticky="news", padx=5)
        self.from_count.grid(row=0, column=0, sticky="w", padx=10, pady=5,columnspan=5)

        self.counter_day_option.grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.counter_month_option.grid(row=1, column=1, sticky="w",pady=5)
        self.counter_year_option.grid(row=1, column=2, sticky="w",padx=5,pady=5)
        self.counter_hour_option.grid(row=1, column=3, sticky="w",pady=5)

        self.count_set_button.grid(row=2, column=0, padx=10, pady=5, sticky="w",columnspan=5)
        self.count_reset_button.grid(row=3, column=0, padx=10, pady=5, sticky="w",columnspan=5)

        self.service_frame.grid(row=2, column=0, sticky="we", padx=5, pady=10)
        self.service_label.grid(row=0, column=0, sticky="we", padx=5, pady=10, columnspan=2)
        self.service_entry.grid(row=0, column=2, sticky="w", padx=10)
        self.service_button.grid(row=1, column=0, sticky="w", padx=5, pady=5, columnspan=2)

        self.calibration_label.grid(row=3, column=0, sticky="nw", padx=10, pady=5, columnspan=3)

        self.cal_day_option.grid(row=4, column=0, sticky="w", padx=5, pady=5)
        self.cal_month_option.grid(row=4, column=1, sticky="w", pady=5)
        self.cal_year_option.grid(row=4, column=2, sticky="w", padx=5, pady=5)
        self.cal_button.grid(row=5, column=0, sticky="w", padx=5, pady=5, columnspan=3)

    def on_service_entry(self, event):
        value = self.service_entry.get()

        try:
            if value != '':
                value = int(value)  # Check if it is integer

                if int(value) not in range(0, 10000):  # Check if it is in range
                    raise ValueError

        except ValueError:
            self.service_save_label.config(text="Nepravilni vnos.", foreground="red")
            self.service_save_label.grid(row=2, column=0, sticky="w", padx=5, pady=5, columnspan=2)
            self.service_button.config(state='disabled')
        else:
            self.service_save_label.grid_forget()
            self.service_button.config(state='normal')

    # Set test device test counter
    def reset_test_count(self):
        # Set count date to current date
        utc_date = pytz.utc.localize(datetime.datetime.utcnow()) + self.controller.userdata.timedif

        self.controller.userdata.protocol.send({"command": "count", "date": utc_date.isoformat()})

        self.count_reset_label.config(text="Ponastavljeno.", foreground="green")
        self.count_reset_label.grid(row=4, column=0, sticky="w", padx=10,columnspan=5)

        # Counter variables are updated when GUI recieves count command!

    # TO DO
    def set_test_count(self):
        for i in range(len(self.month_list)):
            if self.month_list[i] == self.month_variable.get():
                month = i + 1
        try:
            date = datetime.datetime(int(self.year_variable.get()), month, int(self.day_variable.get()), int(self.hour_variable.get()[:2]))
        except ValueError: # Invalid date applied
            raise
            self.count_reset_label.config(text="Datum štetja je neveljaven.", foreground="red")
        else:
            date = date + self.controller.userdata.timedif
            # Convert local time to UTC
            utcdate = pytz.timezone('Europe/Ljubljana').localize(date,is_dst=None).astimezone(pytz.utc)

            # Send to server new calibration date
            self.controller.userdata.protocol.send({"command": "count", "date": utcdate.isoformat()})
            self.count_reset_label.config(text="Datum štetja nastavljen.", foreground="green")

            # Calibration variables are updated when GUI recieves calibration command!
        finally:
            self.count_reset_label.grid(row=4, column=0, sticky="w", padx=10,columnspan=5)

    # Set test device service counter
    def set_service_counter(self):
        try:
            service = int(self.service_entry.get())

            self.controller.userdata.protocol.send({"command": "service", "data": service})
            self.service_save_label.config(text="Shranjeno!", foreground="green")

            self.service_save_label.grid(row=2, column=0, sticky="w", padx=5, pady=5, columnspan=2)
        except ValueError:  # Prevent error if user clicks button too fast when enter wrong number
            pass

    # Set test device calibration date
    def set_calibration_date(self):
        for i in range(len(self.month_list)):
            if self.month_list[i] == self.cal_month_variable.get():
                month = i + 1
        try:
            date = datetime.datetime(int(self.cal_year_variable.get()), month, int(self.cal_day_variable.get()))
        except ValueError:  # Invalid date applied
            self.cal_apply_label.config(text="Datum kalibracije je neveljaven.", foreground="red")
        else:
            date = date + self.controller.userdata.timedif
            # Convert local time to UTC
            utcdate = pytz.timezone('Europe/Ljubljana').localize(date,is_dst=None).astimezone(pytz.utc)

            # Send to server new calibration date
            self.controller.userdata.protocol.send({"command": "calibration", "date": utcdate.isoformat()})
            self.cal_apply_label.config(text="Kalibracija nastavljena.", foreground="green")

            # Calibration variables are updated when GUI recieves calibration command!
        finally:
            self.cal_apply_label.grid(row=6, column=0, sticky="w", padx=10,columnspan=3)




    # Make factory frame
    def make_factory_frame(self):
        self.factory_frame = Frame(self.right_frame)
        self.factory_title = Label(self.factory_frame, text="TOVARNIŠKE NASTAVITVE", font=self.controller.subtitle_font)

        self.factory_label = Label(self.factory_frame, text="")

        self.factory_entry_label = Label(self.factory_frame, text="Geslo:")
        self.factory_entry = Entry(self.factory_frame, width=15, show="*")

        self.factory_button = Button(self.factory_frame, text="Povrni", command=self.factory_reset, style="style1.TButton")

        self.factory_info_label = Label(self.factory_frame, text="")

    def display_factory_frame(self):
        self.factory_frame.grid(row=1, column=0, sticky="news")
        self.factory_title.grid(row=0, column=0, sticky="nw", pady=10, columnspan=2)

        self.factory_label.config(text="Povrnitev testne naprave {} na tovarniške \nnastavitve:" . format(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']))
        self.factory_label.grid(row=1, column=0, sticky="w", pady=5, columnspan=2)
        self.factory_entry_label.grid(row=2, column=0, sticky="w", pady=5)

        self.factory_entry.delete(0, 'end')  # Clear password
        self.factory_entry.grid(row=2, column=1, sticky="w", pady=5)
        self.factory_button.grid(row=3, column=0, sticky="w", pady=5, columnspan=2)

    def factory_reset(self):
        password = self.factory_entry.get()

        if password == self.controller.userdata.admin_pass:
            self.controller.userdata.protocol.send({"command": "factory_reset"})

            # Response is handled when we recieve data from server
        else:
            self.factory_info_label.config(text="Nepravilno geslo.", foreground="red")

        self.factory_info_label.grid(row=4, column=0, sticky="w", pady=5, columnspan=2)





class SplashScreen(Frame):
    def __init__(self, parent, controller):
        # Initialisation header
        Frame.__init__(self, parent)
        self.bind("<<ShowFrame>>", self.on_show_frame)
        self.controller = controller
        self.controller.title("StripsTester v{}".format(self.controller.userdata.version))

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.grid(row=0,column=0,sticky="news")

        # Make window splash screen
        x = (self.controller.winfo_screenwidth() - 640) / 2
        y = (self.controller.winfo_screenheight() - 375) / 2

        self.controller.geometry("638x372+%d+%d" % (x, y))
        self.controller.overrideredirect(True)

        self.canvas = Canvas(self,width=640,height=375, highlightthickness=0)
        self.canvas.pack(expand=YES, fill=BOTH)

        self.logo = PhotoImage(file=self.controller.userdata.directory + "/images/splash.gif")
        self.canvas_image = self.canvas.create_image(0,0, image=self.logo, anchor=NW)
        self.canvas_text = self.canvas.create_text(10,350,text="Nalaganje testnih naprav...",anchor="nw",fill="white")
        self.canvas_author = self.canvas.create_text(630,350,text="Izdelal: Marcel Jančar",anchor="ne",fill="#657983")
        self.canvas_text_version = self.canvas.create_text(435,209,text="v{}" . format(self.controller.userdata.version),font=("Calibri", 18),anchor="nw",fill="#657983")
        self.controller.update()

    def play_animation(self):
        load_time = 0.1
        error_wait_time = 5000
        ok_wait_time = 2000

        try:
            for test_device in self.controller.userdata.load_test_devices():
                self.canvas.itemconfig(self.canvas_text,text="Najdena testna naprava {}" .format(test_device['name']))
                self.controller.update()
                time.sleep(load_time)

        except FileNotFoundError:
            self.canvas.itemconfig(self.canvas_text,text="Datoteke 'config.strips' ni mogoče najti.")
            self.after(error_wait_time,self.terminate)

        except (IOError, json.JSONDecodeError):
            self.canvas.itemconfig(self.canvas_text,text="Datoteka 'config.strips' je prazna oz. neveljavna.")
            self.after(error_wait_time,self.terminate)

        else:
            # Get random MOTD messages from file
            messages = []
            messages.append("Pozdravljeni!")
            messages.append("Zdravo!")
            messages.append("Looking good today :)!")
            messages.append("Lep pozdrav!")

            motd = messages[random.randint(0, len(messages) - 1)]

            if len(self.controller.userdata.test_devices) == 1:
                self.canvas.itemconfig(self.canvas_text, text="Najdena 1 testna naprava. {}".format(motd))
            elif len(self.controller.userdata.test_devices) == 2:
                self.canvas.itemconfig(self.canvas_text, text="Najdeni 2 testni napravi. {}".format(motd))
            elif len(self.controller.userdata.test_devices) == 3 or len(self.controller.userdata.test_devices) == 4:
                self.canvas.itemconfig(self.canvas_text, text="Najdene {} testne naprave. {}".format(len(self.controller.userdata.test_devices), motd))
            else:
                self.canvas.itemconfig(self.canvas_text, text="Najdenih {} testnih naprav. {}".format(len(self.controller.userdata.test_devices), motd))

            self.after(ok_wait_time,self.end)

    def on_show_frame(self, event):
        self.place(x=-2,y=-2)  # Offset window so the border disappear

        self.play_animation()
        #print("You got to SplashScreen")

    def end(self):
        # Make application fullscreen
        self.controller.state('zoomed')
        self.controller.overrideredirect(False)
        self.controller.config(padx=20, pady=20)
        self.controller.make_menu()

        self.controller.get_frame("LoginPage").show_test_devices()
        self.controller.get_frame("LoginPage").show_test_device_info()

        self.controller.get_frame("PropertiesPage").make_config_frame()

        # Redirect to LoginPage
        self.controller.show_frame("LoginPage")

    def terminate(self):
        reactor.stop()

class UserData():
    # Dodaj privzete vrednosti in jih podvoji z zacetnimi... ko uporabnik klikne factory reset, se vrednosti ponastavijo

    def __init__(self):
        self.protocol = None  # Client connection handler
        self.connected = False  # Connection status to TN

        self.id_num = 0
        self.test_type = 0

        self.admin_pass = "strips"

        self.directory = os.path.dirname(os.path.realpath(__file__))

        self.test_devices = []
        self.test_device = 0

        self.result = "ready"
        self.maintenance = None

        self.version = "1.3"

        self.start_test = None
        self.end_test = None

        self.service = 0
        self.countdate = datetime.datetime.today()
        self.calibrationdate = datetime.datetime.today()

        self.task = []
        self.definition = {}

        self.timedif = None  # Saves time difference between UTC GUI and UTC Rpi
        self.path_manual = None

    def delete_data(self):
        self.result = "idle"

        self.start_test = None
        self.end_test = None

        self.protocol = None  # Client connection handler
        self.connected = False  # Connection status to TN

    def load_test_devices(self):
        try:
            os.path.isfile(self.directory + "/config.strips")

            # Open file, read all TN settings
            with open(self.directory + '/config.strips') as data_file:
                try:
                    data = json.load(data_file)

                    for i in range(len(data)):
                        self.test_devices.append(data[i])

                    return self.test_devices

                except (IOError, json.JSONDecodeError):
                    raise

        except FileNotFoundError:
            raise

# INTERPROCESS COMMUNICATION
class ClientProtocol(LineReceiver):
    def __init__(self,controller):
        self.controller = controller
        self.buffer = None

    def sendData(self, data):
        #print("sending %s...." % data)
        self.sendLine(data.encode('utf-8'))

    def lineReceived(self, line):
        #print("MESSAGE: {}" . format(line))
        # Recieve JSON message in ordered format
        #print("DEC: {}" . format(line.decode('utf-8')))
        message = json.loads(line.decode('utf-8'), object_pairs_hook=OrderedDict)
        command = message['command']

        #print("RECIEVED: {}" . format(message))

        if command == "welcome":  # GUI accepted by server
            self.controller.userdata.timedif = parser.parse(message['utc']) - pytz.utc.localize(datetime.datetime.utcnow())

            #print("Time difference between RPi and GUI: {}" . format(self.controller.userdata.timedif))

            # Close only on login page, change title in case of reconnect
            self.controller.title("StripsTester v{} [{}]".format(self.controller.userdata.version, self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']))

            self.controller.show_frame("TesterPage")

        elif command == "user_exists":
            self.controller.get_frame("LoginPage").login_status_label.config(text="Uporabnik z identifikacijo '{}' že obstaja." . format(self.controller.userdata.id_num), foreground="red")

            # Close the connection
            self.close()

        elif command == "ping":
            latency = message['latency'] * 1000

            self.controller.title("StripsTester v{} [{}] - {}ms".format(self.controller.userdata.version, self.controller.userdata.test_devices[self.controller.userdata.test_device]['name'],int(latency)))

            # Send pong back to server
            self.send({"command": "ping", "ping": (pytz.utc.localize(datetime.datetime.utcnow()) + self.controller.userdata.timedif).isoformat()})

        elif command == "text":
            text = message['text']
            tag = message['tag']

            self.controller.get_frame("TesterPage").add_message(text, tag)

        elif command == "tasks":
            if len(self.controller.userdata.task):
                self.controller.get_frame("TesterPage").delete_tasks()
                self.controller.get_frame("PropertiesPage").delete_tasks()

                # Clear global task variable
                self.controller.userdata.task.clear()

            for task in message['tasks']:  # Loop through tasks, which are OrderedDict
                self.controller.userdata.task.append(message['tasks'][task])  # Store task data into global variable (append dict to list)
                self.controller.userdata.task[-1]['slug'] = task  # Apply slug to task data
                self.controller.userdata.task[-1]['state'] = "idle"  # Apply slug to task data

            self.controller.get_frame("TesterPage").make_tasks()  # Make task blocks in TesterPage
            self.controller.get_frame("TesterPage").display_tasks()  # Make task blocks in TesterPage

            self.controller.get_frame("PropertiesPage").make_tasks()  # Make task blocks in PropertiesPage
            self.controller.get_frame("PropertiesPage").display_tasks()  # Make task blocks in PropertiesPage

        elif command == "task_update":
            # Update all test_tasks
            #print("UPD: {}" . format(message['update']))
            for task in message['update']:  # Loop through all tasks in settings
                #print(task)

                for task_index in range(len(self.controller.userdata.task)):
                    if self.controller.userdata.task[task_index]['slug'] == task['slug']:  # Get the right task_index from userdata.tasks
                        self.controller.userdata.task[task_index].update(task)  # Update task dict

                        break

                for task_number in range(len(self.controller.get_frame("TesterPage").test_task)):
                    if self.controller.get_frame("TesterPage").test_task[task_number]['slug'] == task['slug']:
                        # MUST DO (Update all properties page entries)

                        bg_color_list = {"fail": "#e01a00", "ok": "#00ba06", "work": "#0059ea", "idle": "gray"}
                        fg_color = "black"

                        if self.controller.userdata.task[task_index]['enable']:
                            bg_color = bg_color_list[self.controller.userdata.task[task_index]['state']]  # Take color from colorlist
                        else:
                            bg_color = "#cccccc"
                            fg_color = "gray"

                        # Update labels, and states
                        self.controller.get_frame("TesterPage").test_task[task_number]['label'].config(background=bg_color, foreground=fg_color)

                        break

        elif command == "task_result":
            result = message['result']
            option_list = {"fail": {"color": "#e01a00", "text": "TEST FAIL"},
                           "ok": {"color": "#00ba06", "text": "TEST OK"},
                           "work": {"color": "#0059ea", "text": "TESTIRANJE V TEKU"},
                           "idle": {"color": "gray", "text": "PRIPRAVLJEN"}}

            self.controller.get_frame("TesterPage").task_result.config(text=option_list[result]['text'], background=option_list[result]['color'])

            if result == "work":
                self.controller.get_frame("TesterPage").manual_stop_button.config(state='normal')
                self.controller.get_frame("TesterPage").manual_start_button.config(state='disabled')
            else:
                self.controller.get_frame("TesterPage").manual_stop_button.config(state='disabled')
                self.controller.get_frame("TesterPage").manual_start_button.config(state='normal')


        elif command == "maintenance":
            status = message['status']

            if status == "ok":  # Maintenance mode as master (Gets into PropertiesPage)
                self.controller.get_frame("PropertiesPage").hide_login_frame()

                self.controller.get_frame("PropertiesPage").display_left_frame()
                self.controller.get_frame("PropertiesPage").display_log_frame()
                self.controller.get_frame("PropertiesPage").display_shutdown_frame()

                if self.controller.userdata.path_manual is not None:
                    self.controller.get_frame("PropertiesPage").display_manual_frame()

                self.controller.get_frame("PropertiesPage").display_center_frame()

                self.controller.get_frame("PropertiesPage").display_right_frame()

            elif status == "occupied":
                id = message['id']

                self.controller.get_frame("PropertiesPage").login_text_label.config(text="Nastavitve uporablja ID {}." . format(id), foreground="red")
                self.controller.get_frame("PropertiesPage").login_text_label.grid(row=3, column=0, sticky="nw", columnspan=2)

            elif status == "taken":
                self.controller.get_frame("TesterPage").task_result.config(text="VZDRŽEVANJE", background="#e2df00")

                self.controller.get_frame("TesterPage").manual_start_button.config(state="disabled")
                self.controller.get_frame("TesterPage").manual_stop_button.config(state="disabled")
                self.controller.get_frame("TesterPage").shutdown_button.config(state="disabled")
                self.controller.get_frame("TesterPage").reset_test_count_button.config(state="disabled")

            elif status == "dropped":  # Maintenance is dropped
                self.controller.get_frame("TesterPage").shutdown_button.config(state="normal")
                self.controller.get_frame("TesterPage").reset_test_count_button.config(state="normal")

        elif command == "count":
            utc_date = parser.parse(message['date'])  # Parse datetime string to datetime

            utc_date = utc_date - self.controller.userdata.timedif

            # Localize UTC date
            date = utc_date.astimezone(pytz.timezone('Europe/Ljubljana'))

            # Update TesterPage variables
            self.controller.get_frame("TesterPage").countdate.config(text="Serija: {} ob {}" . format(date.strftime("%d.%m.%Y"), date.strftime("%H:%M")))

            success_local = self.calculate_success(message['good'], message['bad'])
            success_global = self.calculate_success(message['good_global'], message['bad_global'])

            success_color_list = ["red", "#c99c22", "green"]

            color_local = success_color_list[bisect.bisect_left([90,95],success_local)]
            color_global = success_color_list[bisect.bisect_left([90,95],success_global)]

            self.controller.get_frame("TesterPage").good_local_label.config(text="Dobri: {}" . format(message['good']))
            self.controller.get_frame("TesterPage").bad_local_label.config(text="Slabi: {}" . format(message['bad']))
            self.controller.get_frame("TesterPage").sum_local_label.config(text="Skupaj: {}" . format(message['good'] + message['bad']))
            self.controller.get_frame("TesterPage").suc_local_label.config(text="Uspešnost: {0:.1f}%" . format(success_local), foreground=color_local)

            self.controller.get_frame("TesterPage").good_global_label.config(text="Dobri: {}" . format(message['good_global']))
            self.controller.get_frame("TesterPage").bad_global_label.config(text="Slabi: {}" . format(message['bad_global']))
            self.controller.get_frame("TesterPage").sum_global_label.config(text="Skupaj: {}" . format(message['good_global'] + message['bad_global']))
            self.controller.get_frame("TesterPage").suc_global_label.config(text="Uspešnost: {0:.1f}%" . format(success_global), foreground=color_global)


            # Update PropertiesPage variables
            self.controller.get_frame("PropertiesPage").day_variable.set(date.day)
            self.controller.get_frame("PropertiesPage").month_variable.set(self.controller.get_frame("PropertiesPage").month_list[date.month - 1])
            self.controller.get_frame("PropertiesPage").year_variable.set(date.year)
            self.controller.get_frame("PropertiesPage").hour_variable.set("{:02}:{:02}".format(date.hour, date.minute))

        elif command == "service":
            service = message['data']

            # Update TesterPage variables
            self.controller.get_frame("TesterPage").service_counter.config(text="Št. ciklov do servisa: {}" . format(service))

            # Update PropertiesPage variables
            self.controller.get_frame("PropertiesPage").service_entry.delete(0, 'end')
            self.controller.get_frame("PropertiesPage").service_entry.insert(END, service)

        elif command == "calibration":
            utc_date = parser.parse(message['date'])  # Parse datetime string to datetime
            utc_date = utc_date - self.controller.userdata.timedif  # Synchronize time with GUI

            # Localize UTC date
            date = utc_date.astimezone(pytz.timezone('Europe/Ljubljana'))

            # Update TesterPage variables
            self.controller.get_frame("TesterPage").calibration_date.config(text="Kalibracija: {}".format(date.strftime("%d.%m.%Y")))

            # Update PropertiesPage variables
            self.controller.get_frame("PropertiesPage").cal_day_variable.set(date.day)
            self.controller.get_frame("PropertiesPage").cal_month_variable.set(self.controller.get_frame("PropertiesPage").month_list[date.month - 1])
            self.controller.get_frame("PropertiesPage").cal_year_variable.set(date.year)

        elif command == "factory_reset":
            status = message['status']

            if status == "ok":
                self.controller.get_frame("PropertiesPage").factory_info_label.config(text="Nastavitve uspešno povrnjene", foreground="green")

            elif status == "fail":
                self.controller.get_frame("PropertiesPage").factory_info_label.config(text="Nastavitve so že povrnjene.", foreground="red")

            elif status == "testing":
                self.controller.get_frame("PropertiesPage").factory_info_label.config(text="Test se ne sme izvajati.", foreground="red")

            self.controller.get_frame("PropertiesPage").factory_info_label.grid(row=4, column=0, sticky="w", pady=5, columnspan=2)

        elif command == "path_manual":
            self.controller.userdata.path_manual = message['path']

            self.controller.get_frame("TesterPage").display_manual_frame()

        elif command == "file":
            mode = message['mode']

            if mode == "data":
                self.buffer = self.buffer + message['data']  # Add chunk to buffer
            if mode == "end":
                pass

        elif command == "test_time":
            start_test = message['start_test']
            end_test = message['end_test']

            if start_test is not None:  # Test is in progress
                self.controller.userdata.start_test = parser.parse(message['start_test']) - self.controller.userdata.timedif

                self.controller.get_frame("TesterPage").time_update = self.controller.after(1000, self.controller.get_frame("TesterPage").update_time_label)

                # Engage after method
                self.controller.get_frame("TesterPage").update_time_label()

            elif end_test is not None:  # Means that the test was finished
                end_test = parser.parse(message['end_test']) - self.controller.userdata.timedif

                # Localize UTC date
                end_test = end_test.astimezone(pytz.timezone('Europe/Ljubljana'))

                if self.controller.userdata.start_test is not None:  # End of test
                    self.controller.after_cancel(self.controller.get_frame("TesterPage").time_update)

                    test_time = pytz.utc.localize(datetime.datetime.utcnow()) - self.controller.userdata.start_test
                    self.controller.get_frame("TesterPage").test_time_label.config(text="Čas testiranja: {}\nTest izveden: {} ob {}" . format(str(test_time)[:-7],end_test.strftime("%d.%m.%Y"), end_test.strftime("%H:%M")))

                else:
                    self.controller.get_frame("TesterPage").test_time_label.config(text="Zadnji test: {} ob {}" . format(end_test.strftime("%d.%m.%Y"), end_test.strftime("%H:%M")))
            else:
                self.controller.get_frame("TesterPage").test_time_label.config(text="")


    def calculate_success(self, good, bad):
        if good:
            success = (good / (good + bad)) * 100
        else:
            success = 0

        return success

    def rawDataReceived(self, data):
        self.remain = self.remain - len(data)  # Reduce remaining size
        self.buffer = self.buffer + data

        #print(data)

        if not self.remain:
            self.remain = None
            #print("File sent successfully!")

            #print(buffer)
            self.setLineMode()  # Set mode back to normal


    # Connection established with server
    def connectionMade(self):
        self.controller.userdata.protocol = self
        self.controller.userdata.connected = True

        self.controller.get_frame("TesterPage").info_text.config(text="Identifikacija: {}\nTip testiranja: {}".format(self.controller.userdata.id_num, self.controller.get_frame("LoginPage").test_type_list.get()))
        self.controller.get_frame("TesterPage").display_task_frame()
        self.controller.get_frame("TesterPage").display_messager_frame()
        self.controller.get_frame("TesterPage").display_stats_frame()

        self.controller.get_frame("LoginPage").login_button.config(state='normal')
        self.controller.get_frame("LoginPage").test_device_option.config(state='normal')
        self.controller.get_frame("LoginPage").login_status_label.config(text="Povezan na testno napravo {}".format(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']), foreground="green")

        # Initiate talk with server
        self.send({"command": "welcome", "id": self.controller.userdata.id_num, "test_type": self.controller.userdata.test_type})

    def close(self):
        self.transport.loseConnection()

    # Send data as JSON object
    def send(self,message):
        #print("SEND: {}" . format(message))
        self.sendLine(json.dumps(message, ensure_ascii=False).encode("utf-8"))

# Factory for client (handling connection status)
class clientfactory(protocol.ClientFactory):
    def __init__(self, controller):
        self.controller = controller

    def buildProtocol(self, addr):
        return ClientProtocol(self.controller)

    def clientConnectionFailed(self, connector, reason):
        self.controller.userdata.protocol = None
        self.controller.userdata.connected = False

        self.controller.get_frame("LoginPage").login_button.config(state='normal')
        self.controller.get_frame("LoginPage").test_device_option.config(state='normal')
        self.controller.get_frame("LoginPage").login_status_label.config(text="Testna naprava {} ni dosegljiva.".format(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']), foreground="red")

    def startedConnecting(self, connector):
        self.controller.userdata.connected = False

        self.controller.get_frame("LoginPage").login_button.config(state='disabled')
        self.controller.get_frame("LoginPage").test_device_option.config(state='disabled')
        self.controller.get_frame("LoginPage").login_status_label.config(text="Povezovanje na testno napravo {}..." . format(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']), foreground="black")

        # If client was logged in offline mode and then wants to connect to TN
        self.controller.get_frame("PropertiesPage").hide_left_frame()
        self.controller.get_frame("PropertiesPage").hide_center_frame()
        self.controller.get_frame("PropertiesPage").hide_right_frame()
        self.controller.get_frame("PropertiesPage").display_login_frame()

    def clientConnectionLost(self, connector, reason):
        self.controller.userdata.protocol = None
        self.controller.userdata.connected = False

        self.controller.userdata.delete_data()

        # Navigate to LoginPage
        self.controller.show_frame("LoginPage")
        self.controller.get_frame("TesterPage").info_text.config(text="Ni povezave s testno napravo.")

        # If user has maintenance and reconnect, we must revert button states because otherwise they will remain locked.
        self.controller.get_frame("TesterPage").shutdown_button.config(state="normal")
        self.controller.get_frame("TesterPage").reset_test_count_button.config(state="normal")

        self.controller.get_frame("TesterPage").hide_task_frame()
        self.controller.get_frame("TesterPage").hide_messager_frame()
        self.controller.get_frame("TesterPage").hide_stats_frame()

        # Delete all tasks which have been made
        self.controller.get_frame("TesterPage").delete_tasks()
        self.controller.get_frame("PropertiesPage").delete_tasks()

        # Clear global task variable
        self.controller.userdata.task.clear()

        self.controller.get_frame("PropertiesPage").hide_left_frame()
        self.controller.get_frame("PropertiesPage").hide_center_frame()
        self.controller.get_frame("PropertiesPage").hide_right_frame()
        self.controller.get_frame("PropertiesPage").display_login_frame()

        # Close only on login page, change title in case of reconnect
        self.controller.title("StripsTester v{}" . format(self.controller.userdata.version))

        if reason.type == error.ConnectionDone:  # Connection was closed cleanly
            self.controller.get_frame("LoginPage").login_status_label.config(text="Povezava s testno napravo {} zaustavljena." . format(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']), foreground="red")

        elif reason.type == error.ConnectionLost:  # Connection lost (attempt reconnect?)
            self.controller.get_frame("LoginPage").login_status_label.config(text="Prekinjena povezava s testno napravo {}." . format(self.controller.userdata.test_devices[self.controller.userdata.test_device]['name']), foreground="red")


class Program(Tk):
    def __init__(self):
        Tk.__init__(self)

        # Global container which holds entire GUI
        self.container = Frame(self)
        self.container.pack(side="top", fill="both", expand=True)
        self.container.columnconfigure(0,weight=1)
        self.container.rowconfigure(0,weight=1)

        # Global variables stored in UserData
        self.userdata = UserData()

        # Create user-defined fonts
        self.make_fonts()

        # Create user-defined styles
        self.make_styles()

        # Give window icon if platform is Windows
        if platform.system() == 'Windows':
            self.iconbitmap(self.userdata.directory + "/images/icon.ico")

        # Define frames / pages of GUI
        self.frames = {}
        for F in (LoginPage, TesterPage, PropertiesPage, SplashScreen):
            page_name = F.__name__
            frame = F(self.container, self)
            self.frames[page_name] = frame

            # put all of the pages in the same location;
            # the one on the top of the stacking order
            # will be the one that is visible.
            frame.grid(row=0, column=0, sticky="news")

        # Close only on login page, change title in case of reconnect
        self.title("StripsTester v{}" . format(self.userdata.version))

        self.show_frame("SplashScreen")

    # Show frame at a given name
    def show_frame(self, page_name):
        frame = self.frames[page_name]
        frame.tkraise()
        frame.event_generate("<<ShowFrame>>")

    # Get frame attributes
    def get_frame(self, page_class):
        return self.frames[page_class]

    def make_menu(self):
        # Create menu bar
        self.menu = Menu(self)
        self.config(menu=self.menu)

        self.menu.add_command(label="Vpis", command=lambda: self.show_frame("LoginPage"))
        self.menu.add_command(label="Tester", command=lambda: self.show_frame("TesterPage"))
        self.menu.add_command(label="Nastavitve", command=lambda: self.show_frame("PropertiesPage"))

    def make_fonts(self):
        self.title_font = tkFont.Font(family='Helvetica', size=15, weight='bold')
        self.subtitle_font = tkFont.Font(family='Helvetica', size=13, weight='bold')
        self.text_font = tkFont.Font(family='Helvetica', size=12)
        self.task_font = tkFont.Font(family='Helvetica', size=10, weight='bold')
        self.task_font_italic = tkFont.Font(family='Helvetica', size=10, slant="italic")
        self.entry_font = tkFont.Font(family='Helvetica', size=10)
        self.button_font = tkFont.Font(family='Helvetica', size=10)

    def make_styles(self):
        style = Style()
        style.configure("style1.TButton", font=self.button_font)

def main():
    # Define our program application
    app = Program()

    # Install support for tkinter and twisted
    tksupport.install(app)
    app.protocol("WM_DELETE_WINDOW", reactor.stop)
    reactor.run()


if __name__ == '__main__':
    main()
