import os

'''
1. Image on SD card
2. Boot without screen
3. Boot with sceen
4. Allow SSH interface and set keyboard
5. Connect with wifi

6. mkdir /strips_tester_project
7. git clone repo
8. run python rpi_setup
'''




os.system("sudo apt-get update")
os.system("sudo apt-get upgrade -y")
os.system("sudo apt-get -y install python3-venv")
os.system("sudo python3 -m venv /venv_strips_tester")
os.system("virtualenv -p /venv_strips_tester/bin/python3.4 /venv_strips_tester")
os.system("sudo chown -R pi /venv_strips_tester/")
#os.system("source /venv_strips_tester/bin/activate")
os.system("/venv_strips_tester/bin/python -m pip install pip -UI")
os.system("/venv_strips_tester/bin/python -m pip install setuptools -UI")
os.system("/venv_strips_tester/bin/python -m pip install -r requirements.txt")
os.system("/venv_strips_tester/bin/python -m pip install pyserial -UI")
os.system("/venv_strips_tester/bin/python -m pip install picamera -UI")
os.system("/venv_strips_tester/bin/python -m pip install RPi.GPIO")
os.system("/venv_strips_tester/bin/python -m pip install numpy")


###hidapi dependencies
os.system("sudo apt-get install -y libusb-1.0-0-dev")
os.system("sudo apt-get install -y python-dev")
os.system("sudo apt-get install -y libudev-dev")

### build shared library
# os.system("sudo apt-get install -y autoconf")
# os.system("sudo apt-get install -y build-essential")
# os.system("sudo apt-get install -y libpq-dev")
# os.system("git clone https://github.com/signal11/hidapi.git")
# os.system("cd hidapi")
# os.system("./bootstrap")
# os.system("./configure")
# os.system("sudo make")
# os.system("sudo make install")
# os.system("/venv_strips_tester/bin/python -m pip install hidapi")

#os.system("sudo systemctl stop serial-getty@ttyS0.service")
#os.system("sudo systemctl disable serial-getty@ttyS0.service")
os.system("sudo rm /boot/cmdline.txt")
os.system("sudo cp /strips_tester_project/initial_setup/cmdline.txt /boot/cmdline.txt")
os.system("sudo rm /boot/config.txt")
os.system("sudo cp /strips_tester_project/initial_setup/config.txt /boot/config.txt")


### postgresql
os.system("sudo apt-get install -y libpq-dev")
os.system("sudo apt-get install -y")
os.system("sudo apt-get install postgresql-9.4")
os.system("/venv_strips_tester/bin/python -m pip install psycopg2")
os.system("sudo rm /etc/postgresql/9.4/main/pg_hba.conf")
os.system("sudo cp /strips_tester_project/initial_setup/pg_hba.conf /etc/postgresql/9.4/main/pg_hba.conf")
os.system("sudo rm /etc/postgresql/9.4/main/postgresql.conf")
os.system("sudo cp /strips_tester_project/initial_setup/postgresql.conf /etc/postgresql/9.4/main/postgresql.conf")
os.system("sudo iw wlan0 set power_save off")


## I2C
os.system("sudo apt-get install -y i2c-tools")
os.system("/venv_strips_tester/bin/python -m pip install smbus2")
os.system("sudo cp /strips_tester_project/initial_setup/python-sudo.sh /venv_strips_tester/bin/")
