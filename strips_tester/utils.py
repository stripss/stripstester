#!/usr/bin/python
import logging
import os
import datetime
import picamera
import time
import hid
import numpy as np

module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

def get_cpu_serial() -> str:
    # Extract serial from cpuinfo file
    cpuserial = "0000000000000000"
    try:
        f = open('/proc/cpuinfo', 'r')
        for line in f:
            if line[0:6] == 'Serial':
                cpuserial = line[10:26]
        f.close()
    except:
        cpuserial = "ERROR000000000"
    return cpuserial