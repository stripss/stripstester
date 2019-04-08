import tkinter as tk
import json
import threading
import socket

class Page(tk.Frame):
    def __init__(self, *args, **kwargs):
        tk.Frame.__init__(self, *args, **kwargs)

    def show(self):
        self.lift()

class Page2(Page):
    def __init__(self, *args, **kwargs):
        Page.__init__(self, *args, **kwargs)
        self.grid_columnconfigure(1, weight=1)
        #self.grid_rowconfigure(0, weight=1)

        self.title = tk.Label(self, text="Uporabniški vmesnik",font=(None, 30, "bold"), justify="center")
        self.title.grid(row=0,column=1,sticky="news")

        self.semafor1 = Semafor(self,0,1)
        self.semafor2 = Semafor(self,2,1)

        self.status = Status(self,1,1)
        self.status.set_status("TESTIRANJE V TEKU...")

        self.counter1 = Counter(self,1,2)

    def simulation(self, phase):
        time = 0

        if phase == 0:
            self.semafor1.signal(1,0,0)
            self.semafor2.signal(1,0,0)

            self.status.set_status("Povezovanje...")
            self.semafor1.set_blink(1,0,0)
            self.semafor2.set_blink(1,0,0)
            time = 3

        elif phase == 1:
            self.semafor1.signal(1,1,0)
            self.semafor2.signal(1,1,0)

            self.semafor1.set_blink(0,0,0)
            self.semafor2.set_blink(0,0,0)

            self.status.set_status("Povezano!")
            time = 5
        elif phase == 2:
            self.status.set_status("Testiranje v teku...")
            self.semafor1.signal(0,1,0)
            self.semafor2.signal(0,1,0)
            time = 5
        elif phase == 3:
            self.status.set_status("Testiranje OK!")
            self.semafor1.signal(0,0,1)
            self.semafor2.signal(0,0,1)

            self.counter1.set_good(self.counter1.good + 2)

        if time:
            phase += 1
            self.timer = threading.Timer(time, self.simulation, [phase])
            self.timer.start()
        else:
            phase = 0



class Interface:
    def __init__(self, main, root):
        self.root = root
        self.main = main

        self.server_thread = threading.Thread(target=self.start_server, args=("127.0.0.1",1234))
        self.server_thread.setDaemon(True)

    def start_server(self,host,port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))

            s.listen()
            self.main.p2.status.set_status("Listening...")
            while True:
                conn, addr = s.accept()

                with conn:
                    while True:
                        data = conn.recv(512)

                        if not data:
                            break

                        self.recieve_message(json.loads(data.decode()))


    def connect_to_tn(self):
        self.main.p2.semafor1.signal(not self.main.p2.semafor1.red,0,0)
        self.main.p2.semafor2.signal(not self.main.p2.semafor2.red,1,0)

        self.recieve_message("status")

    def recieve_message(self, message):
        if message['command'] == "status":
            self.main.p2.status.set_status(message['value'])

        if message['command'] == "good_count":
            self.main.p2.counter1.set_good(message['value'])

        if message['command'] == "bad_count":
            self.main.p2.counter1.set_bad(message['value'])

        if message['command'] == "semafor":
            if message['which'] == 1:
                self.main.p2.semafor1.signal(*message['value'])
            elif message['which'] == 2:
                self.main.p2.semafor2.signal(*message['value'])

        if message['command'] == "blink":
            if message['which'] == 1:
                self.main.p2.semafor1.set_blink(*message['value'])
            elif message['which'] == 2:
                self.main.p2.semafor2.set_blink(*message['value'])

        if message['command'] == "title":
            self.main.p2.title.configure(text=message['value'])
            self.root.title(message['value'])

class Semafor:
    def __init__(self, parent,x,y):
        self.size = 100
        self.offset = 10
        self.red = 0
        self.yellow = 0
        self.green = 0

        self.blink_red = 0
        self.blink_yellow = 0
        self.blink_green = 0

        self.container = tk.Frame(parent, background="#4c4c4c")
        self.red_light = tk.Frame(self.container, background="#770000", width=self.size,height=self.size)
        self.yellow_light = tk.Frame(self.container, background="#776100", width=self.size,height=self.size)
        self.green_light = tk.Frame(self.container, background="#074f00", width=self.size,height=self.size)

        self.container.grid(column=x,row=y)

        self.red_light.grid(row=0,column=0,padx=self.offset,pady=self.offset)
        self.yellow_light.grid(row=1,column=0,padx=self.offset,pady=self.offset)
        self.green_light.grid(row=2,column=0,padx=self.offset,pady=self.offset)

        # Initiate blink
        self.blink()

    def signal(self, red, yellow, green):
        self.red = red
        self.yellow = yellow
        self.green = green

        if red:
            self.red_light.configure(background="red")
        else:
            self.red_light.configure(background="#770000")

        if yellow:
            self.yellow_light.configure(background="yellow")
        else:
            self.yellow_light.configure(background="#776100")

        if green:
            self.green_light.configure(background="#22e800")
        else:
            self.green_light.configure(background="#074f00")

    def set_blink(self, red, yellow, green):
        self.blink_red = red
        self.blink_yellow = yellow
        self.blink_green = green

    def blink(self):
        blink_freq = 0.2  # 1s

        if self.blink_red:
            self.signal(not self.red,self.yellow,self.green)

        if self.blink_yellow:
            self.signal(self.red,not self.yellow,self.green)

        if self.blink_green:
            self.signal(self.red,self.yellow,not self.green)

        self.blink_timer = threading.Timer(blink_freq, self.blink, [])
        self.blink_timer.start()

class Counter:
    def __init__(self, parent,x,y):
        self.size = 10
        self.offset = 5
        self.good = 0
        self.bad = 0

        self.container = tk.Frame(parent, width=self.size, height=self.size)
        self.good_count = tk.Label(self.container, font=(None, 20, "bold"), justify="center")
        self.bad_count = tk.Label(self.container, font=(None, 20, "bold"), justify="center")

        self.container.grid(column=x,row=y)

        self.good_count.grid(row=0,column=0,padx=self.offset,pady=self.offset,sticky="news")
        self.bad_count.grid(row=0,column=1,padx=self.offset,pady=self.offset,sticky="news")

        self.set_good(0)
        self.set_bad(0)

    def set_good(self, count):
        self.good = count

        self.good_count.configure(text="OK: {}".format(self.good))

    def set_bad(self, count):
        self.bad = count

        self.bad_count.configure(text="FAIL: {}" . format(self.bad))

class Status:
    def __init__(self, parent,x,y):
        self.size = 10
        self.offset = 5
        self.status = ""

        self.container = tk.Frame(parent, width=self.size, height=self.size)
        self.label = tk.Label(self.container, text=self.status, background="#d3d3d3",font=(None, 20, "bold"), justify="center")

        self.container.grid(column=x,row=y,sticky="news")

        self.label.grid(row=0,column=0,padx=self.offset,pady=self.offset,sticky="news")
        self.container.grid_columnconfigure(0,weight=1)
        self.container.grid_rowconfigure(0,weight=1)

    def set_status(self, status):
        self.status = status

        self.label.configure(text=status)



class MainView(tk.Frame):
    def __init__(self, root):
        self.interface = Interface(self,root)

        tk.Frame.__init__(self)

        self.p2 = Page2(self)

        buttonframe = tk.Frame(self)
        container = tk.Frame(self, background="#d3d3d3")
        buttonframe.pack(side="top", fill="x", expand=False)
        container.pack(side="top", fill="both", expand=True)

        self.p2.place(in_=container, x=0, y=0, relwidth=1, relheight=1)

        #b1 = tk.Button(buttonframe, text="Connect", command=lambda: self.interface.connect_to_tn())
        #b2 = tk.Button(buttonframe, text="GUI", command=self.p2.lift)
        b3 = tk.Button(buttonframe, text="Simulate", command=lambda: self.p2.simulation(0))

        #b1.pack(side="left")
        #b2.pack(side="left")
        b3.pack(side="left")

        self.p2.show()
        self.interface.server_thread.start() # Start server thread


if __name__ == "__main__":
    root = tk.Tk()
    main = MainView(root)

    main.pack(side="top", fill="both", expand=True)
    root.title("TN GUI")
    root.wm_geometry("800x600")
    #root.state('zoomed')
    root.mainloop()

