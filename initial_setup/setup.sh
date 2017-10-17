#!/bin/bash
echo "Staring setup"

read -p 'branch: ' branch
read -sp 'remote: ' remote

sudo mkdir /strips_tester_project
sudo chmod 777 /strips_tester_project
#git clone -b $branch $remote
git clone -b develop http://10.48.253.126:8888/peterp/strips_tester.git /strips_tester_project
#sudo cp -r /strips_tester_project/strips_tester /home/pi/Desktop
#sudo rm -r /strips_tester_project/strips_tester
#sudo cp -a /home/pi/Desktop/strips_tester /strips_tester_project
sudo chmod -R 777 /strips_tester_project/

python3 /strips_tester_project/initial_setup/rpi_setup.py

echo "Setup finished successfully :)"