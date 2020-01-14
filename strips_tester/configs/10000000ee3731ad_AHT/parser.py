import strips_tester
import gui_web
import pymongo
import csv

###

# Parser script - every TN has its own parser so it can handle custom JSON commands.
# Global JSON commands are saved in gui_web.py script

###


class Parser:
    def __init__(self):
        #print("Parsing...")
        pass

    def parse(self, client, message):
        if "set_program" in message['command']:
            #print("Program of AHT set to {}".format(message['value']))

            strips_tester.data['program'] = message['value']
            gui_web.save_variable_to_db("program", message['value'])

            gui_web.send(message)  # Broadcast new program
            gui_web.send({"command": "title", "value": "AHT ({})".format(strips_tester.data['program'][2])})  # Broadcast new title

        if "get_program_list" in message['command']:
            with open(strips_tester.settings.test_dir + "/bin/meje.csv") as file:
                csv_reader = list(csv.reader(file))

                gui_web.sendTo(client, {"command": "program_list", "value": csv_reader})

            try:
                gui_web.sendTo(client, {"command": "set_program", "value": strips_tester.data['program']})
            except KeyError:  # Program is not defined yet
                gui_web.sendTo(client, {"command": "status", "value": "Za začetek testiranja nastavi parametre merjenca."})
                gui_web.sendTo(client, {"command": "semafor", "nest": 0, "value": (0, 0, 0), "blink": (0, 1, 0)})
                pass

    def welcome(self, client):
        gui_web.sendTo(client, {"command": "new"})
        gui_web.sendTo(client, {"command": "tilt", "value": True})

        try:
            gui_web.sendTo(client, {"command": "title", "value": "AHT ({})".format(strips_tester.data['program'][2])})
        except KeyError:  # Program is not defined yet
            gui_web.sendTo(client, {"command": "title", "value": "AHT"})
