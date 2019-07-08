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
        pass

    def welcome(self, client):
        gui_web.sendTo(client, {"command": "title", "value": "Photointerrupter"})