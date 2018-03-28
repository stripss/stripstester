

from tkinter import *
from tkinter.ttk import *

from multiprocessing import Queue, Process

import time
import random
import threading
import socket
import select
import json

from decimal import Decimal, getcontext



class LoginPage(Frame):
    def __init__(self, parent, controller, q):
        self.current_frame = "LoginPage"
        Frame.__init__(self, parent)

        self.columnconfigure(2, weight=1)
        self.rowconfigure(3, weight=1)
        self.grid(sticky=N+S+E+W,padx=20,pady=20)

        self.queue = q
        self.parent = parent
        self.controller = controller

        controller.title("Strip's LOGIN")

        self.lbl0 = Label(self, text="Prijava v sistem",font=("Verdana", 14), padding=(0,0,0,20))
        self.lbl0.grid(row=0, column=0, sticky="nw")

        self.logo = PhotoImage(file="/strips_tester_project/strips_tester/images/strips.gif")
        self.copyright_img = Label(self, image=self.logo)
        self.copyright_img.grid(row=0, column=2, sticky=NE)

        self.lbl1 = Label(self, text="Tip modula:")
        self.lbl1.grid(row=1, column=0, sticky=W, pady=5)

        self.ent1 = Entry(self, width=10)
        self.ent1.insert(END, "2")
        self.ent1.grid(row=1, column=1, sticky=W)

        self.lbl2 = Label(self, text="",foreground="red")
        self.lbl2.grid(row=1, column=2, sticky=W, pady=5, padx=20)

        self.lbl3 = Label(self, text="Testiranje:")
        self.lbl3.grid(row=2, column=0, sticky=W, pady=5)

        self.ent2 = Entry(self, width=10)
        self.ent2.insert(END, "1")
        self.ent2.grid(row=2, column=1, sticky=W)

        self.lbl4 = Label(self, text="",foreground="red")
        self.lbl4.grid(row=2, column=2, sticky=W, pady=5, padx=20)

        self.lbl5 = Label(self, text="Številka operaterja:")
        self.lbl5.grid(row=3, column=0, sticky=W, pady=5)

        self.ent3 = Entry(self, width=10)
        self.ent3.insert(END, self.controller.userdata.id_num)
        self.ent3.grid(row=3, column=1, sticky=W)

        self.lbl6 = Label(self, text="",foreground="red")
        self.lbl6.grid(row=3, column=2, sticky=W, pady=5, padx=20)

        self.startBtn = Button(self, text="Prijava",  command=self.userLogin)
        self.startBtn.grid(row=4, column=0, pady=20, sticky=W)

        #print(self.controller.current_frame)

    def userLogin(self):
        self.controller.userdata.type_num = self.ent1.get()
        self.controller.userdata.test_num = self.ent2.get()
        self.controller.userdata.id_num = self.ent3.get()

        ok = True

        self.lbl2.config(text="")
        self.lbl4.config(text="")
        self.lbl6.config(text="")

        if(int(self.controller.userdata.type_num) not in range(0,3)):
            self.lbl2.config(text="Nepravilni tip modula")
            ok = False

        if(int(self.controller.userdata.test_num) not in range(0,4)):
            self.lbl4.config(text="Nepravilno testiranje")
            ok = False

        if(int(self.controller.userdata.id_num) not in range(0,100)):
            self.lbl6.config(text="Napačna identifikacija")
            ok = False

        if(ok):
            self.controller.switch_frame(TesterPage)

class TesterPage(Frame):
    def __init__(self, parent, controller, q):
        self.current_frame = "TesterPage"

        Frame.__init__(self, parent)

        self.queue = q
        self.parent = parent
        self.controller = controller

        self.columnconfigure(1, weight=1)
        self.grid(sticky=N+S+E+W,padx=20,pady=20)

        self.menu = Menu(self)
        self.controller.config(menu=self.menu)

        self.menu.add_command(label="Vpis",command=lambda: self.controller.switch_frame(LoginPage))
        self.menu.add_command(label="Tester")
        self.menu.add_command(label="Nastavitve",command=lambda: self.controller.switch_frame(PropertiesPage))

        self.lbl0 = Label(self, text="Operativni uporabniški vmesnik",font=("Verdana", 14), padding=(0,0,0,20))
        self.lbl0.grid(row=0, column=0, sticky="nw",columnspan=2)

        self.logo = PhotoImage(file="/strips_tester_project/strips_tester/images/strips.gif")
        self.copyright_img = Label(self, image=self.logo)
        self.copyright_img.grid(row=0, column=2, sticky=NE)

        controller.title("Strip's TESTER")

        self.after(10,self.check_after)


        if self.controller.userdata.tester_init == True:
            self.show_gui()
        else:
            self.error = Label(self, text="Povezujem na {}:{}...".format(self.controller.userdata.address,self.controller.userdata.port),font=("Verdana", 14), padding=(0,0,0,20))
            self.error.grid(row=1,column=0,sticky="news")

    def show_gui(self):
        self.sep = []

        # [task]
        # make task counter
        # every time [task] comes, increase task counter by 1
        # make gui for that task

        # [task-update]
        # get task id number
        # check if task exists
        # update gui based on task (color, text?)

        # [text]
        # update messager with that text


        # wait for client
        # get client tasks data
        # based on tasks data, build gui

        self.lbl1 = Label(self, text="Identifikacija: {}\nTestiranje: {}\nTip serije: {}".format(self.controller.userdata.id_num,self.controller.userdata.test_num,self.controller.userdata.type_num))
        self.lbl1.grid(row=1,column=0,sticky="news")

        self.lbl2 = Label(self, text="FAZA TESTIRANJA",font=("Verdana", 14))
        self.lbl2.grid(row=2,column=0,sticky="w",pady=10)

        self.task_frame = Frame(self)
        self.task_frame.grid(row=3,column=0,sticky="news")
        self.task_frame.config(borderwidth=2, relief="groove")
        self.show_tasks()

        self.lbl3 = Label(self, text="INFORMACIJE",font=("Verdana", 14))
        self.lbl3.grid(row=2,column=1,sticky="w",pady=10)

        self.txt = Text(self)
        self.txt.tag_config('red', foreground="red")
        self.txt.tag_config('green', foreground="green")
        self.txt.tag_config('yellow', foreground="yellow")
        self.txt.tag_config('blue', foreground="blue")
        self.txt.tag_config('purple', foreground="magenta")
        self.txt.tag_config('black', foreground="black")
        self.txt.tag_config('grey', foreground="grey")
        self.txt.grid(row=3,column=1,sticky="news",padx=5,rowspan=2)

        self.show_messages()

        self.lbl4 = Label(self, text="STATISTIKA",font=("Verdana", 14),anchor="w")
        self.lbl4.grid(row=2,column=2,sticky="w",pady=10)

        self.stats_frame = Frame(self)
        self.stats_frame.grid(row=3,column=2,sticky="nw")

        self.labelframe = LabelFrame(self.stats_frame, text="Kosi")
        self.labelframe.grid(row=0,column=0,sticky="new",padx=5)
        self.labelframe.config(borderwidth=2,relief="groove")

        self.lbl5 = Label(self.labelframe, text="Dobri: {}".format(self.controller.userdata.good_count))
        self.lbl5.grid(row=0, column=0, sticky=NW, padx=10, pady=5)

        self.lbl6 = Label(self.labelframe, text="Slabi: {}".format(self.controller.userdata.bad_count))
        self.lbl6.grid(row=1, column=0, sticky=NW, padx=10, pady=5)

        self.lbl7 = Label(self.labelframe, text="Skupaj: {}".format(self.controller.userdata.bad_count + self.controller.userdata.good_count))
        self.lbl7.grid(row=2, column=0, sticky=NW, padx=10, pady=5)

        self.labelframe2 = LabelFrame(self.stats_frame, text="Ostalo")
        self.labelframe2.grid(row=1,column=0,sticky="new",padx=5,pady=10)
        self.labelframe2.config(borderwidth=2,relief="groove")

        self.lbl8 = Label(self.labelframe2, text="Št. ciklov do servisa: {}".format(self.controller.userdata.service))
        self.lbl8.grid(row=3, column=0, sticky=NW, padx=10, pady=5)

        while not self.queue.empty(): # Delete all from queue
            self.queue.get()

    def show_tasks(self): # Show tasks when GUI init
        for task_number in range(len(self.controller.userdata.task)):
            self.make_task(task_number)

    def make_task(self,task_number): # Show new task when GUI active
        if self.controller.userdata.task[task_number]['task_state'] == "fail":
            bg_color = "red"
        elif self.controller.userdata.task[task_number]['task_state'] == "ok":
            bg_color = "green"
        else:
            bg_color = "grey"

        self.task_frame.columnconfigure(0, weight=1)
        self.sep.append(Label(self.task_frame, text=self.controller.userdata.task[task_number]['task_name'], borderwidth=2, relief="groove",justify="center",padding=(20, 10, 20, 10),background=bg_color))
        self.sep[task_number].grid(row=task_number, column=0, pady=5, padx=5,sticky="we")

    def update_task(self,task_number):  # Update task when GUI active
        if self.controller.userdata.task[task_number]['task_state'] == "fail":
            bg_color = "red"
        elif self.controller.userdata.task[task_number]['task_state'] == "ok":
            bg_color = "green"
        else:
            bg_color = "grey"

        self.sep[task_number].config(text=self.controller.userdata.task[task_number]['task_name'],background=bg_color)

    def show_messages(self): # Shows all when GUI init
        for message_number in range(len(self.controller.userdata.messager)):
            self.make_message(message_number)

    def make_message(self,message_number): # Shows when GUI running
        self.txt.configure(state='normal')
        self.txt.insert(END, self.controller.userdata.messager[message_number]['text'], self.controller.userdata.messager[message_number]['tag'])
        self.txt.configure(state='disabled')

    def check_after(self):
        self.after(10,self.check_after)

        if not self.queue.empty(): # something is in the queue
            msg = self.queue.get()
            #print(msg)

            if "tester_init" in msg: #enable tester page -> controlled by client (TN)!
                self.show_gui()

            if "text" in msg: # new text
                self.make_message(msg['text']['text_number'])

            if "task" in msg: #create new task, pridejo za tester_init
                self.make_task(msg['task']['task_number'])

            if "task_update" in msg:
                self.task_number = msg['task_update']['task_number']

                if(msg['task_update']['task_number'] >= self.controller.userdata.num_of_tasks):
                    print("TASK NOT EXIST YET")
                    return

                self.update_task(msg['task_update']['task_number'])

            if "count" in msg:
                self.lbl5.config(text="Dobri: {}".format(self.controller.userdata.good_count))
                self.lbl6.config(text="Slabi: {}".format(self.controller.userdata.bad_count))
                self.lbl7.config(text="Skupaj: {}".format(self.controller.userdata.good_count + self.controller.userdata.bad_count))




class PropertiesPage(Frame):
    def __init__(self, parent, controller, q):
        self.current_frame = "PropertiesageP"

        self.queue = q
        self.parent = parent
        self.controller = controller

        Frame.__init__(self, parent)

        self.columnconfigure(1, weight=1)
        self.grid(sticky=N+S+E+W,padx=20,pady=20)

        self.menu = Menu(self)
        self.controller.config(menu=self.menu)

        #dodaj login formo, ce ta ni izpolnjena pravilno, ostane spodnji frame zaklenjen, sicer se odklene

        self.menu.add_command(label="Vpis",command=lambda: self.controller.switch_frame(LoginPage))
        self.menu.add_command(label="Tester",command=lambda: self.controller.switch_frame(TesterPage))
        self.menu.add_command(label="Nastavitve")

        self.lbl0 = Label(self, text="Nastavitve",font=("Verdana", 14), padding=(0,0,0,20))
        self.lbl0.grid(row=0, column=0, sticky="nw")

        self.logo = PhotoImage(file="/strips_tester_project/strips_tester/images/strips.gif")
        self.copyright_img = Label(self, image=self.logo)
        self.copyright_img.grid(row=0, column=2, sticky=NE)



        self.test_device= Label(self, text="Testirna naprava:")
        self.test_device.grid(row=1, column=0, sticky="w", pady=5)

        self.test_device_entry = Entry(self, width=30)
        self.test_device_entry.insert(END, "GACS_A2 Bender")
        self.test_device_entry.grid(row=1, column=1, sticky="w")



        self.lbl2 = Label(self, text="KONFIGURACIJA", font=("Verdana", 14))
        self.lbl2.grid(row=2, column=0, sticky="w", pady=10)

        self.task_frame = Frame(self)
        self.task_frame.grid(row=3, column=0, sticky="news")

        self.td = Label(self.task_frame, text="GACS_A2 Bender")
        self.td.grid(row=0, column=0, sticky="w", pady=5)

        self.ip = Label(self.task_frame, text="IP naslov:")
        self.ip.grid(row=1, column=0, sticky="w", pady=5)

        self.ip_entry = Entry(self.task_frame, width=10)
        self.ip_entry.insert(END, self.controller.userdata.address)
        self.ip_entry.grid(row=1, column=1, sticky=E)

        self.ip = Label(self.task_frame, text="Port:")
        self.ip.grid(row=2, column=0, sticky="w", pady=5)

        self.port_entry = Entry(self.task_frame, width=10)
        self.port_entry.insert(END, self.controller.userdata.port)
        self.port_entry.grid(row=2, column=1, sticky=E)

        self.ping_message = Label(self.task_frame, text="")
        self.ping_message.grid(row=3, column=0, sticky="w", pady=5,columnspan=2)

        self.ping = Button(self.task_frame, text="Preveri povezavo",  command=self.ping_test_device)
        self.ping.grid(row=4, column=0, pady=10, sticky=W)

        self.save_test_device_button = Button(self.task_frame, text="Shrani nastavitve",  command=self.save_test_device_settings)
        self.save_test_device_button.grid(row=5, column=0, pady=10, sticky=W)

        self.lbl3 = Label(self, text="TESTIRNA NAPRAVA", font=("Verdana", 14))
        self.lbl3.grid(row=2, column=1, sticky="w", pady=10)




        if self.controller.userdata.tester_init == True:
            #Connected to test device
            pass
        else:
            print("ni povezave na TN")





        self.lbl4 = Label(self, text="LOKALNO", font=("Verdana", 14), anchor="w")
        self.lbl4.grid(row=2, column=2, sticky="w", pady=10)

        self.stats_frame = Frame(self)
        self.stats_frame.grid(row=3, column=2, sticky="nw")

        self.labelframe = LabelFrame(self.stats_frame, text="Kosi")
        self.labelframe.grid(row=0, column=0, sticky="new", padx=5)
        self.labelframe.config(borderwidth=2, relief="groove")

        self.lbl5 = Label(self.labelframe, text="Dobri: {}".format(self.controller.userdata.good_count))
        self.lbl5.grid(row=0, column=0, sticky=NW, padx=10, pady=5)

        self.lbl6 = Label(self.labelframe, text="Slabi: {}".format(self.controller.userdata.bad_count))
        self.lbl6.grid(row=1, column=0, sticky=NW, padx=10, pady=5)

        self.lbl7 = Label(self.labelframe, text="Skupaj: {}".format(
            self.controller.userdata.bad_count + self.controller.userdata.good_count))
        self.lbl7.grid(row=2, column=0, sticky=NW, padx=10, pady=5)

        self.labelframe2 = LabelFrame(self.stats_frame, text="Ostalo")
        self.labelframe2.grid(row=1, column=0, sticky="new", padx=5, pady=10)
        self.labelframe2.config(borderwidth=2, relief="groove")

        self.lbl8 = Label(self.labelframe2,
                          text="Št. ciklov do servisa: {}".format(self.controller.userdata.service))
        self.lbl8.grid(row=3, column=0, sticky=NW, padx=10, pady=5)




        #self.lbl1 = Label(self, text="Število ciklov do servisa:")
        #self.lbl1.grid(row=1, column=0, sticky=E, pady=5)
#
        #self.ent1 = Entry(self, width=10)
        #self.ent1.insert(END, self.controller.userdata.service)
        #self.ent1.grid(row=1, column=1, sticky=W)
#
        #self.lbl2 = Label(self, text="")
        #self.lbl2.grid(row=1, column=2, sticky=W, padx=10, pady=5)
#
        #self.startBtn = Button(self, text="Tovarniške nastavitve", command=self.factory_reset)
        #self.startBtn.grid(row=2, column=0, pady=20, sticky=W)
#
        #self.startBtn = Button(self, text="Shrani",  command=self.save)
        #self.startBtn.grid(row=3, column=0, pady=5, sticky=W)
#
        #self.startBtn = Button(self, text="Odjava",  command=self.logout)
        #self.startBtn.grid(row=4, column=0, pady=5, sticky=W)

        #self.after(10, self.redirect)


    def save_test_device_settings(self):
        pass

    def ping_test_device(self):
        # send ping socket
        # if get response - in after - (name of device) OK else not OK
        #self.ping_message.config(text="Povezava uspešna!",foreground="green")
        self.ping_message.config(text="Povezava ni uspešna!",foreground="red")
        pass




    def save(self):
        self.controller.userdata.service = self.ent1.get()

        self.lbl2.config(text="Shranjeno")

    def logout(self):
        self.controller.userdata.admin_logged = False

        self.controller.switch_frame(PropertiesLoginPage)

    def redirect(self):
        # Return to login page if admin is not logged.
        if(self.controller.userdata.admin_logged == False):
            self.controller.switch_frame(PropertiesLoginPage)

    def factory_reset(self):
        self.ent1.delete(0, END)
        self.ent1.insert(0, self.controller.userdata.default_service)

        #add text that all values will be reset



class PropertiesLoginPage(Frame):
    def __init__(self, parent, controller, q):
        self.current_frame = "PropertiesLoginPage"

        Frame.__init__(self, parent)

        self.queue = q
        self.parent = parent
        self.controller = controller

        self.columnconfigure(2, weight=1)
        self.rowconfigure(3, weight=1)
        self.grid(sticky=N+S+E+W,padx=20,pady=20)

        self.menu = Menu(self)
        self.controller.config(menu=self.menu)

        #dodaj login formo, ce ta ni izpolnjena pravilno, ostane spodnji frame zaklenjen, sicer se odklene

        self.menu.add_command(label="Vpis",command=lambda: self.controller.switch_frame(LoginPage))
        self.menu.add_command(label="Tester",command=lambda: self.controller.switch_frame(TesterPage))
        self.menu.add_command(label="Nastavitve")

        self.lbl0 = Label(self, text="Nastavitve",font=("Verdana", 14), padding=(0,0,0,20))
        self.lbl0.grid(row=0, column=0, sticky=W)

        self.lbl1 = Label(self, text="Za nadaljevanje se morate prijaviti.")
        self.lbl1.grid(row=1, column=0, sticky=W, pady=5,columnspan=2)

        self.lbl2 = Label(self, text="Geslo:")
        self.lbl2.grid(row=2, column=0, sticky=W, pady=5)

        self.ent1 = Entry(self, width=10)
        self.ent1.insert(END, "")
        self.ent1.grid(row=2, column=1, sticky=W)

        self.lbl3 = Label(self, text="")
        self.lbl3.grid(row=2, column=2, sticky=W, padx=20, pady=5)

        self.startBtn = Button(self, text="Prijava",  command=self.userLogin)
        self.startBtn.grid(row=4, column=0, pady=20, sticky=W)

        self.logo = PhotoImage(file="/strips_tester_project/strips_tester/images/strips.gif")
        self.copyright_img = Label(self, image=self.logo)
        self.copyright_img.grid(row=0, column=2, sticky=NE)


    def userLogin(self):
        password = self.ent1.get()

        if(password == self.controller.userdata.admin_pass):
            #self.lbl2.config(text="Geslo OK!",foreground="green")
            self.controller.userdata.admin_logged = True
            self.controller.switch_frame(PropertiesPage)
        else:
            self.lbl3.config(text="Nepravilno geslo!",foreground="red")



class UserData():
    # Dodaj privzete vrednosti in jih podvoji z zacetnimi... ko uporabnik klikne factory reset, se vrednosti ponastavijo

    def __init__(self):
        self.current_frame = "LoginPage"

        self.id_num = 0
        self.test_num = 0
        self.type_num = 0
        self.good_count = 0
        self.bad_count = 0
        self.service = 0

        self.address = "127.0.0.1"
        self.port = 1234

        self.admin_pass = "strips"
        self.admin_logged = False

        self.default_id_num = 0
        self.default_test_num = 0
        self.default_type_num = 0
        self.default_good_count = 0
        self.default_bad_count = 0
        self.default_service = 999

        self.tester_init = False

        self.messager = {}
        self.task = {}

        self.num_of_messager = 0
        self.num_of_tasks = 0



# INTERPROCESS COMMUNICATION
class IPCThread(threading.Thread):
    """"""
    # ----------------------------------------------------------------------
    def __init__(self,queue,controller):
        """Initialize"""
        threading.Thread.__init__(self)

        self.queue = queue
        self.controller = controller

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Setup TCP socket
        try:
            self.socket.bind((self.controller.userdata.address, self.controller.userdata.port))

            self.socket.listen(5)
            self.setDaemon(True)
            self.start()

            print("TCP Server started!")

        except Exception as error:
            print(error)
    # ----------------------------------------------------------------------
    def run(self):
        while True:
            try:
                client, addr = self.socket.accept()

                ready = select.select([client, ], [], [], 2)
                if ready[0]:
                    msg = json.loads(client.recv(1024).decode())

                    # print(msg)

                    if "tester_init" in msg:  # enable tester page -> controlled by client (TN)!
                        if self.controller.userdata.tester_init == False:
                            self.controller.userdata.tester_init = True

                    if "text" in msg:  # update text
                        self.add_message(msg['text']['text'], msg['text']['tag'])
                        msg['text']['text_number'] = self.controller.userdata.num_of_messager - 1

                    if "task" in msg:  # create new task, pridejo za tester_init
                        self.add_task(msg['task']['task_name'], msg['task']['task_state'])
                        msg['task']['task_number'] = self.controller.userdata.num_of_tasks - 1

                    if "task_update" in msg:
                        self.task_number = msg['task_update']['task_number']

                        if (self.task_number >= self.controller.userdata.num_of_tasks):
                            print("TASK NOT EXIST YET")
                            return

                        if "task_state" in msg['task_update']:
                            self.controller.userdata.task[self.task_number]['task_state'] = msg['task_update']['task_state']

                        if "task_name" in msg['task_update']:
                            self.controller.userdata.task[self.task_number]['task_name'] = msg['task_update'][
                                'task_name']

                    if "count" in msg:
                        self.controller.userdata.good_count = int(msg['count']['good'])
                        self.controller.userdata.bad_count = int(msg['count']['bad'])

                    self.queue.put(msg) # Forward to GUI

            except socket.error as msg:
                print("Socket error! {}" .format(msg))
                break

        # shutdown the socket
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except:
            pass

        self.socket.close()

    def add_message(self,messager_text,messager_tag):
        self.controller.userdata.messager[self.controller.userdata.num_of_messager] = {}

        self.controller.userdata.messager[self.controller.userdata.num_of_messager]['text'] = messager_text
        self.controller.userdata.messager[self.controller.userdata.num_of_messager]['tag'] = messager_tag

        self.controller.userdata.num_of_messager = self.controller.userdata.num_of_messager + 1

    def add_task(self,task_name,task_state):
        self.controller.userdata.task[self.controller.userdata.num_of_tasks] = {}

        self.controller.userdata.task[self.controller.userdata.num_of_tasks]['task_name'] = task_name
        self.controller.userdata.task[self.controller.userdata.num_of_tasks]['task_state'] = task_state

        self.controller.userdata.num_of_tasks = self.controller.userdata.num_of_tasks + 1


class Program(Tk):
    def __init__(self,queue):
        Tk.__init__(self)

        self.container = Frame(self)
        self.container.pack(fill=BOTH,expand=True)
        self.container.columnconfigure(0, weight=1)
        self.queue = queue

        self.userdata = UserData()
        self.ipc = IPCThread(self.queue,controller=self)

        self._frame = LoginPage(parent=self.container, controller=self,q=self.queue)

        self.geometry("1024x600+300+300")

    def switch_frame(self, frame_class):
        """Destroys current frame and replaces it with a new one."""
        new_frame = frame_class(parent=self.container, controller=self,q=self.queue)
        self._frame.destroy()
        self._frame = new_frame

def main():
    q = Queue(0)

    app = Program(q)

    app.mainloop()



if __name__ == '__main__':
    main()
