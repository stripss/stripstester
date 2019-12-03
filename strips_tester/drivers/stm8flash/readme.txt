STM8FLASH Installation
The following steps for installing stm8flash worked for me:

clone stm8flash (https://github.com/vdudouyt/stm8flash)
provide libusb-dev (e.g. sudo apt-get install libusb-1.0-0-dev)
in the stm8flash folder, run 'make' and 'sudo make install' -> file is located at /usr/local/bin folder to use stand-alone
create /etc/udev/rules.d/99-stlinkv2.rules with contents SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="3748", MODE="0666"