import strips_tester
import gui_web
import pymongo
import glob
import os

###

# Parser script - every TN has its own parser so it can handle custom JSON commands.
# Global JSON commands are saved in gui_web.py script

###


class Parser:
    def __init__(self):
        pass

    def parse(self, client, message):
        if "set_program" in message['command']:
            #print("Program of GAHF set to {}".format(message['value']))

            strips_tester.data['program'] = message['value']
            gui_web.save_variable_to_db("program", message['value'])

            gui_web.send(message)  # Broadcast new program

            params = [s for s in strips_tester.data['program'].split("_")]
            gui_web.send({"command": "title", "value": "GAHF UI ({})".format(params[0])})  # Broadcast new title

        # Enumerate all hex files accessible
        if "get_program_list" in message['command']:
            files = glob.glob(strips_tester.settings.test_dir + "/bin/*.hex")

            # Show only filenames without path
            for file in range(len(files)):
                files[file] = os.path.basename(files[file])
                files[file] = os.path.splitext(files[file])[0]
            gui_web.sendTo(client, {"command": "program_list", "value": files})

            try:
                gui_web.sendTo(client, {"command": "set_program", "value": strips_tester.data['program']})
            except KeyError:  # Program is not defined yet
                gui_web.sendTo(client, {"command": "status", "value": "Za začetek testiranja nastavi programsko opremo."})
                for nest in range(2):
                    gui_web.sendTo(client, {"command": "semafor", "nest": nest, "value": (0, 0, 0), "blink": (0, 1, 0)})

        # Enable camera calibration mode
        if "camera_calibration" in message['command']:

            strips_tester.data['camera_calibration'] = message['value']

            for nest in range(2):
                if strips_tester.data['camera_calibration']:
                    gui_web.sendTo(client, {"command": "semafor", "nest": nest, "value": (0, 0, 0), "blink": (0, 1, 0)})
                else:
                    gui_web.sendTo(client, {"command": "semafor", "nest": nest, "value": (0, 0, 0), "blink": (0, 0, 0)})




    def welcome(self, client):

        try:
            params = [s for s in strips_tester.data['program'].split("_")]
            gui_web.sendTo(client, {"command": "title", "value": "GAHF UI ({})".format(params[0])})  # Broadcast new title

        except Exception:  # Program is not defined yet
            gui_web.sendTo(client, {"command": "title", "value": "GAHF UI"})