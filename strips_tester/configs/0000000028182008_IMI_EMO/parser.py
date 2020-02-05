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


            strips_tester.data['program_flash'] = message['flash']
            strips_tester.data['program_eeprom'] = message['eeprom']
            gui_web.save_variable_to_db("program_flash", message['flash'])
            gui_web.save_variable_to_db("program_eeprom", message['eeprom'])

            gui_web.send(message)  # Broadcast new program
        # Enumerate all hex files accessible
        if "get_program_list" in message['command']:
            files_flash = glob.glob(strips_tester.settings.test_dir + "/bin/*.hex")
            files_eeprom = glob.glob(strips_tester.settings.test_dir + "/bin/*.eep")

            # Show only filenames without path
            for file in range(len(files_flash)):
                files_flash[file] = os.path.basename(files_flash[file])
                files_flash[file] = os.path.splitext(files_flash[file])[0]

            # Show only filenames without path
            for file in range(len(files_eeprom)):
                files_eeprom[file] = os.path.basename(files_eeprom[file])
                files_eeprom[file] = os.path.splitext(files_eeprom[file])[0]

            gui_web.sendTo(client, {"command": "program_list", "flash": files_flash, "eeprom": files_eeprom})

            try:
                gui_web.sendTo(client, {"command": "set_program", "flash": strips_tester.data['program_flash'], "eeprom": strips_tester.data['program_eeprom']})
            except KeyError:  # Program is not defined yet
                gui_web.sendTo(client, {"command": "status", "value": "Za začetek testiranja nastavi programsko opremo."})

                gui_web.sendTo(client, {"command": "semafor", "value": (0, 0, 0), "blink": (0, 1, 0)})

    def welcome(self, client):
        gui_web.sendTo(client, {"command": "title", "value": "IMI EMO"})