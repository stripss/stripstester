import os

os.system("sudo apt-get update")
os.system("sudo apt-get upgrade -y")
os.system("sudo apt-get install python3-venv")
os.system("sudo python3 -m venv /venv_strips_tester")
os.system("sudo chown -R pi /venv_strips_tester/")
os.system("source /venv_strips_tester/bin/activate")
os.system("pip install pip -UI")
os.system("pip install setuptools -UI")
os.system("pip install -r requirements.txt")
os.system("sudo /venv_strips_tester/bin/python -m pip install pyserial -UI")
os.system("sudo /venv_strips_tester/bin/python -m pip install picamera -UI")
python_sudo_contents = '#!/bin/bash\n#Python Interpreter for running tests as root\n# user needs sudo NOPASSWD enabled\nsudo /venv_strips_tester/bin/python "$@"'
os.system("cat "+python_sudo_contents+" >> /venv_strips_tester/bin/python-sudo2.sh")



