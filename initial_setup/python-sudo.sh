#!/bin/sh
#Python Interpreter for running tests as root
# user needs sudo NOPASSWD enabled
sudo PYTHONPATH=$PYTHONPATH python "$@"