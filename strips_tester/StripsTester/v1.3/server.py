from twisted.internet.protocol import Factory, Protocol
from twisted.protocols.basic import LineReceiver
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet import reactor
import json
from collections import OrderedDict
import datetime
from dateutil import parser
import pytz



class GUI(LineReceiver):
    def __init__(self, users, serverdata):
        self.users = users
        self.serverdata = serverdata
        self.id = None

    def connectionMade(self):
        print("connection incoming")
        # self.factory was set by the factory's default buildProtocol:

    def connectionLost(self,reason):
        if self.id in self.users:
            if self.serverdata.maintenance == self.id:  # Check if disconnected ID had maintenance
                self.serverdata.maintenance = None
                self.send_broadcast({"command": "maintenance", "status": "dropped"})
                self.send_broadcast({"command": "text", "text": "Način vzdrževanja testne naprave končan. Lahko nadaljujete testiranje.\n", "tag": "yellow"})

                # Send old task result status
                self.send_broadcast({"command": "task_result", "result": "idle"})

            # Delete user data
            del self.users[self.id]
        print("Connection with ID {} lost: {}" . format(self.id,reason))

    def send(self, message):
        print("SEND: {}" . format(message))
        self.sendLine(json.dumps(message).encode())

    def send_broadcast(self, message):
        print("SEND BROADCAST: {}" . format(message))
        for user in self.users:
            self.users[user].sendLine(json.dumps(message).encode())

    def send_broadcast_ex(self, ex_user, message):
        for user in self.users:
            if ex_user != self.users[user]:
                self.users[user].sendLine(json.dumps(message).encode())

    def lineReceived(self, line):
        message = json.loads(line.decode())
        print("RECIEVED: {}" . format(message))

        command = message['command']

        # GUI greets the server
        if command == "welcome":
            id = message['data']

            if id in self.users:
                # ID already exists, return disconnect
                self.send({"command": "user_exists"})
                print("User exists")
                self.transport.loseConnection()
            else:
                self.id = id
                self.users[self.id] = self  # Link this instance to user id

                self.send({"command": "welcome"})  # Greet new GUI
                self.send({"command": "text", "text": "Pozdravljen uporabnik {}!\n" . format(self.id), "tag": "black"})

                with open("D:/StripsTesterProject/strips_tester/configs/000000007c32abcd_GACS_A2_Bender/config.json", 'r', encoding="utf8") as f:
                    data = json.load(f, object_pairs_hook=OrderedDict)
                    self.task_execution_order = data['task_execution_order']

                    self.send({"command": "tasks", "tasks": self.task_execution_order})

                self.send({"command": "set_count", "date": self.serverdata.countdate.isoformat()})
                self.send({"command": "service", "data": self.serverdata.service})
                self.send({"command": "set_count", "date": self.serverdata.countdate.isoformat()})
                self.send({"command": "calibration", "date": self.serverdata.calibrationdate.isoformat()})

                self.send({"command": "task_update", "update": {"slug": "LockSimulator", "state": "work"}})
                self.send({"command": "task_result", "result": "work"})

                if self.serverdata.maintenance is not None:
                    self.send({"command": "maintenance", "status": "taken", "id": self.id})  # Tell new client maintenance status

        elif command == "text":  # What to do with text?
            pass

        elif command == "maintenance":
            status = message['status']

            if status == "request":  # User requests maintenance
                if self.serverdata.maintenance is None:
                    self.serverdata.maintenance = self.id  # Link user ID to maintenance

                    self.send({"command": "maintenance", "status": "ok"})  # Accept maintenance
                    self.send_broadcast({"command": "maintenance", "status": "taken", "id": self.id})  # Broadcast maintenance
                    self.send_broadcast({"command": "text", "text": "Poteka način vzdrževanja testne naprave. Trenutno ni mogoče testirati.\n", "tag": "yellow"})

                else:
                    self.send({"command": "maintenance", "status": "occupied", "id": self.serverdata.maintenance})  # Refuse maintenance

            elif status == "drop":
                self.serverdata.maintenance = None  # Maintenance not linked to any user
                self.send_broadcast({"command": "maintenance", "status": "dropped"})
                self.send_broadcast({"command": "text", "text": "Način vzdrževanja testne naprave končan. Lahko nadaljujete testiranje.\n", "tag": "yellow"})

                # Send old task result status
                self.send_broadcast({"command": "task_result", "result": "idle"})

        elif command == "set_count":
            self.serverdata.countdate = parser.parse(message['date'])  # Parse datetime string to datetime

            # Broadcast new date to all clients
            self.send_broadcast({"command": "set_count", "date": self.serverdata.countdate.isoformat()})

        elif command == "service":
            self.serverdata.service = message['data']

            # Broadcast new date to all clients
            self.send_broadcast({"command": "service", "data": self.serverdata.service})

        elif command == "calibration":
            self.serverdata.calibrationdate = parser.parse(message['date'])  # Parse datetime string to datetime

            # Broadcast new date to all clients
            self.send_broadcast({"command": "calibration", "date": self.serverdata.calibrationdate.isoformat()})

        elif command == "factory_reset":
            # Perform factory reset.. delete config_custom.json file
            try:
                os.remove("neki")

                self.send({"command": "factory_reset", "status": "ok"})
            except OSError:
                self.send({"command": "factory_reset", "status": "fail"})


        elif command == "tasks":
            # Server recieves updated tasks from GUI

            # Recreate server-like tasks

            # Broadcast updated tasks to clients
            self.send_broadcast({"command": "tasks", "tasks": self.task_execution_order})

        elif command == "file":
            pass

        elif command == "star"

        else: # Server does not recognize this command
            print("Unknown command.")


class GUIFactory(Factory):
    def __init__(self, serverdata):
        self.users = {}  # maps user names to Chat instances
        self.serverdata = serverdata

    def buildProtocol(self, addr):
        print(self.users)
        return GUI(self.users, self.serverdata)

    def startFactory(self):
        print("Server GUI ready")

class Server:
    def __init__(self):
        self.maintenance = None
        self.countdate = pytz.utc.localize(datetime.datetime.utcnow())
        self.calibrationdate = pytz.utc.localize(datetime.datetime.utcnow())
        self.service = 0

        endpoint = TCP4ServerEndpoint(reactor, 8888)
        endpoint.listen(GUIFactory(self))
        reactor.run()