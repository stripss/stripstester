import os
import time

# # update all
os.system("sudo apt-get update")
os.system("sudo apt-get upgrade -y")
#
# # install python virtual venv
os.system("sudo apt-get -y install python3-venv")
os.system("sudo python3 -m venv /venv_strips_tester")
os.system("virtualenv -p /venv_strips_tester/bin/python3.4 /venv_strips_tester")
os.system("sudo chown -R pi /venv_strips_tester/")

# ###hidapi dependencies
os.system("sudo apt-get install -y libusb-1.0-0-dev")
os.system("sudo apt-get install -y python-dev")
os.system("sudo apt-get install -y libudev-dev")
os.system("sudo apt-get install -y libtool")

# ### build shared library
os.system("sudo apt-get install -y autoconf")
os.system("sudo apt-get install -y build-essential")
os.system("sudo apt-get install -y libpq-dev")
os.system("git clone https://github.com/signal11/hidapi.git /home/pi/Desktop/hidapi")
os.chdir("/home/pi/Desktop/hidapi")
os.system("/bin/bash /home/pi/Desktop/hidapi/bootstrap")
os.system("/bin/bash /home/pi/Desktop/hidapi/configure")
os.system("sudo make")
os.system("sudo make install")

# # QR code
os.system("sudo apt-get install -y libdmtx0a")

# ## I2C
os.system("sudo apt-get install -y i2c-tools")
os.system("/venv_strips_tester/bin/python -m pip install smbus2") # todo to requirements
#
# ### postgresql
os.system("sudo apt-get install -y libpq-dev")
os.system("sudo apt-get install -y postgresql-9.4")
#
# # python
os.system("/venv_strips_tester/bin/python -m pip install pip -UI")
os.system("/venv_strips_tester/bin/python -m pip install setuptools -UI")
os.system("/venv_strips_tester/bin/python -m pip install -r /strips_tester_project/initial_setup/requirements.txt")
os.system("sudo cp /strips_tester_project/initial_setup/python-sudo.sh /venv_strips_tester/bin/")

# rpi files config
#os.system("sudo systemctl stop serial-getty@ttyS0.service")
#os.system("sudo systemctl disable serial-getty@ttyS0.service")
os.system("sudo rm /boot/cmdline.txt")
os.system("sudo cp /strips_tester_project/initial_setup/cmdline.txt /boot/cmdline.txt")
os.system("sudo rm /boot/config.txt")
os.system("sudo cp /strips_tester_project/initial_setup/config.txt /boot/config.txt")

# postgresql
# allow postgres access from outside
os.system("sudo rm /etc/postgresql/9.4/main/pg_hba.conf")
os.system("sudo cp /strips_tester_project/initial_setup/pg_hba.conf /etc/postgresql/9.4/main/pg_hba.conf")
os.system("sudo rm /etc/postgresql/9.4/main/postgresql.conf")
os.system("sudo cp /strips_tester_project/initial_setup/postgresql.conf /etc/postgresql/9.4/main/postgresql.conf")
os.system("sudo iw wlan0 set power_save off")
#I2C module
os.system("sudo cp /strips_tester_project/initial_setup/modules /etc/modules")
# check if survived :)
time.sleep(20)
os.system("sudo reboot")