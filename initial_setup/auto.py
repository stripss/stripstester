#!/usr/bin/python3
# get currently connected wifi
# if wifi is StripsTester - Auto-start tester.py
# if wifi is LabTest - No auto-start of tester.py
import subprocess
import time
import sys
import os
import filecmp

wifi_found = False

def get_ip_address():
    ip = subprocess.check_output(['hostname', '-I']).decode()
    ip = ip.split(" ")
    return ip[0] # Return first IP in IP list

while not wifi_found:
    try:
        wifi = subprocess.check_output(['iwgetid']).decode()  # Get SSID name

        print("WiFi found")
        print("IP Address of TN: {}" . format(get_ip_address()))
        # Git commands to update StripsTester to latest version
        os.chdir("/")  # Root cd

        if "debug" not in wifi:  # Debug AP found, skip the install
            if os.path.isdir("/strips_tester_project"):  # StripsTester already exists
                print("StripsTester found")
                os.chdir("/strips_tester_project")

                # Remove master remote refs (prevent git error if master file is corrupted)
                os.system("sudo rm -rf /strips_tester_project/.git/refs/remotes/origin/master")

                os.system("sudo git reset --hard")
                #os.system("sudo git checkout master")

                # Uncheck if unlock refs error
                #os.system("sudo git remote prune origin")
                os.system("sudo git remote remove origin")
                os.system("sudo git remote add origin http://deploy:stripsdeploy@git.strips.eu/production/tester.py.git")

                os.system("sudo git config --global user.name 'StripsTester'")
                os.system("sudo git config --global user.email '<>'")

                os.system("sudo git clean -d -f")
                os.system("sudo git commit")

                os.system("sudo git pull origin master")
            else:  # StripsTester was not found - clone it from GitHub repository
                print("StripsTester NOT found")
                os.system("sudo git clone http://deploy:stripsdeploy@git.strips.eu/production/tester.py.git /strips_tester_project")

            # Add all privileges to strips_tester_project
            os.system("sudo chmod 777 -R /strips_tester_project")
            os.system("sudo chmod 777 /auto.py")

            # Move system files from initial setup to the right location

            # Check if auto scripts is the same
            if not filecmp.cmp('/strips_tester_project/initial_setup/auto.py', '/auto.py'):
                # Files are not the same - update WiFi networks
                os.system("sudo rm -rf /auto.py")
                os.system("sudo cp /strips_tester_project/initial_setup/auto.py /auto.py")
                print("Auto script updated!")
            else:
                print("Auto script already updated.")

            # Check if wpa_supplicant is the same (WiFi hotspots)
            if not filecmp.cmp('/strips_tester_project/initial_setup/wpa_supplicant.conf', '/etc/wpa_supplicant/wpa_supplicant.conf'):
                # Files are not the same - update WiFi networks
                os.system("sudo rm -rf /etc/wpa_supplicant/wpa_supplicant.conf")
                os.system("sudo cp /strips_tester_project/initial_setup/wpa_supplicant.conf /etc/wpa_supplicant/wpa_supplicant.conf")
                print("WiFi networks updated!")
            else:
                print("WiFi networks already updated.")

        # Auto-start StripsTester if WiFi is detected

        if "StripsTester" in wifi or "STRIPS-HOME" in wifi or "debug" in wifi:
            p = subprocess.Popen(["/venv_strips_tester/bin/python-sudo.sh", "/strips_tester_project/strips_tester/tester.py"] + sys.argv[1:])
            # TN is running in production mode
            print("Production mode (Found StripsTester) - Auto-start initializing...")

            while p.poll() is None:
                # print('Still sleeping')
                time.sleep(1)

            wifi_found = True

        elif "LabTest1" in wifi:
            print("Debug mode (Found LabTest1) - Auto-start canceled.")
            wifi_found = True

        time.sleep(0.5)

    except Exception as e:  # WiFi not found or it is not initialised yet
        time.sleep(0.5)
