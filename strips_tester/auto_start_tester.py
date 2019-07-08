# get currently connected wifi
# if wifi is StripsTester - Auto-start tester.py
# if wifi is LabTest - No auto-start of tester.py
import subprocess
import time
import sys

wifi_found = False

while not wifi_found:
    try:
        wifi = subprocess.check_output(['iwgetid']).decode()  # Get SSID name

        if "StripsTester" in wifi:
            p = subprocess.Popen(["/venv_strips_tester/bin/python-sudo.sh", "/strips_tester_project/strips_tester/tester.py"] + sys.argv[1:])
            # TN is running in production mode
            print("Production mode (Found StripsTester)")
            print("Auto-start initializing...")

            while p.poll() is None:
                # print('Still sleeping')
                time.sleep(1)

            wifi_found = True

        elif "LabTest1" in wifi:
            print("Debug mode (Found LabTest1)")
            print("Auto-start canceled.")
            wifi_found = True

        time.sleep(1)

    except Exception:  # WiFi not found or it is not initialised yet
        time.sleep(1)
