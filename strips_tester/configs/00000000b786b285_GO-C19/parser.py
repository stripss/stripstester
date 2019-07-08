import strips_tester
import gui_web
import pymongo


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
            print("Program of GO-C19 set to {}".format(message['value']))

            strips_tester.data['program_number'] = message['value']

            gui_web.send({"command": "title", "value": "GO-C19 ({})".format(strips_tester.data['program_number'])})

    def welcome(self, client):
        gui_web.sendTo(client, {"command": "new"})  # Redirect to new GUI
        gui_web.sendTo(client, {"command": "title", "value": "GO-C19 ({})".format(strips_tester.data['program_number'])})