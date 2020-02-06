Welcome to StripsTester!
Made by Marcel Jancar

Git access:
Username: stripss
Password: stripstester123

Test device procedure:
- turn on test device
- test device loads raspbian
- test device checks if StripsTester already exists on filesystem
- if not, test device clone StripsTester from repository
- if yes, test device updates to the latest files (remove all other temp files)
- if StripsTester SSID is detected, test device starts tester.py automatically
- if LabTest1 SSID is detected, test device will close script and wait

If something goes wrong:
- enable VNC server: vncserver
- check terminal on VNC for errors