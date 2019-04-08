import socket
import json
import time
import threading
import multiprocessing


def simulate():
    send({"command": "title", "value": "TN GO-C19"})

    for i in range(2):
        send({"command": "semafor", "which": i + 1, "value": (0, 0, 0)})
        send({"command": "blink", "which": i + 1, "value": (0, 0, 0)})

    send({"command": "status", "value": "Za začetek testiranja zapri pokrov."})
    time.sleep(4)

    for i in range(2):
        send({"command": "semafor", "which": i + 1, "value": (0, 1, 0)})
        send({"command": "blink", "which": i + 1, "value": (0, 1, 0)})

    send({"command": "status", "value": "Testiranje 5V..."})
    time.sleep(0.5)
    send({"command": "status", "value": "Testiranje R1..."})
    time.sleep(0.5)
    send({"command": "status", "value": "Testiranje R2..."})
    time.sleep(0.5)
    send({"command": "status", "value": "Testiranje R3..."})
    time.sleep(2)
    send({"command": "status", "value": "Testiranje R5..."})
    time.sleep(0.5)
    send({"command": "status", "value": "Testiranje R6..."})
    time.sleep(0.5)
    send({"command": "status", "value": "Programiranje..."})
    time.sleep(2)

    send({"command": "status", "value": "Vizualni test..."})
    time.sleep(2)

    send({"command": "status", "value": "Za konec testa odpri pokrov."})
    time.sleep(2)

    send({"command": "status", "value": "Testiranje končano."})

    for i in range(2):
        send({"command": "blink", "which": i + 1, "value": (0, 0, 0)})

    send({"command": "semafor", "which": 1, "value": (1, 0, 0)})
    send({"command": "semafor", "which": 2, "value": (0, 0, 1)})


def send(data, HOST='127.0.0.1', PORT=1234):
    create_socket(data, HOST, PORT)
    return

    thread = threading.Thread(target=create_socket, args=(data, HOST, PORT))
    thread.setDaemon(True)
    thread.start()
    # thread.join()


def create_socket(data, HOST, PORT):
    data = json.dumps(data)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            s.sendall(data.encode())
    except Exception as ee:
        # Error if GUI not present
        pass

