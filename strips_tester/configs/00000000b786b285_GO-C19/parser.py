import strips_tester
import gui_web

class Parser:
    def __init__(self,clients):
        self.clients = clients
        print("Parsing...")

    def parse(self, message):
        if "sht" in message['command']:
            print("HELLO RECEIVED! :)")
            strips_tester.data['program_number'] = "S003"

            gui_web.send({"command": "html_clean", "value": ""})

            with open(strips_tester.settings.test_dir + '/custom.html', 'r') as myfile:
                gui_web.send({"command": "html_append", "value": myfile.read()})

            return ""

        if "set_program" in message['command']:
            print("Program of GO-C19 set to {}" . format(message['value']))

            strips_tester.data['program_number'] = message['value']

            gui_web.send({"command": "title", "value": "GO-C19 ({})".format(strips_tester.data['program_number'])})

        if "save_worker_data" in message['command']:
            print("Worker data updated.")

            strips_tester.data['worker_id'] = message['worker_id'];
            strips_tester.data['worker_type'] = message['worker_type'];

    def welcome(self):
        # Send custom HTML page based on GO-C19 page
        with open(strips_tester.settings.test_dir + '/custom.html', 'r') as custom_html:
            gui_web.send({"command": "html_append", "value": custom_html.read()})

        gui_web.send({"command": "title", "value": "GO-C19 ({})".format(strips_tester.data['program_number'])})

