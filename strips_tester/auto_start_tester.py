# get currently connected wifi
# if wifi is StripsTester - autostart tester
# if wifi is labtest - no auto test
import subprocess
import time
import sys

wifi_found = False
while not wifi_found:
    # Get SSID name
    wifi = subprocess.check_output(['iwgetid']).decode()

    if "StripsTester" in wifi:
        p = subprocess.Popen(["/venv_strips_tester/bin/python-sudo.sh", "/strips_tester_project/strips_tester/tester.py"] + sys.argv[1:])
        # TN is running in production mode
        print("Production mode (Found StripsTester)")

        while p.poll() is None:
            print('Still sleeping')
            time.sleep(1)

        wifi_found = True

    if "LabTest1" in wifi:
        print("Debug mode (Found StripsTester)")
        wifi_found = True

    time.sleep(3)