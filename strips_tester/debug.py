import utils
import time
# from smbus2 import SMBusWrapper
#
# class IRTemperatureSensor():
#     MLX90615_I2C_ADDR = 0x5B
#     MLX90615_REG_TEMP_AMBIENT = 0x26
#     MLX90615_REG_TEMP_OBJECT = 0x27
#
#     def __init__(self, delay: int = 1):
#         pass
#         #self.bus = SMBus(1)
#
#     def get_value(self):
#         with SMBusWrapper(1) as bus:
#             block = bus.read_i2c_block_data(IRTemperatureSensor.MLX90615_I2C_ADDR,
#                                                  IRTemperatureSensor.MLX90615_REG_TEMP_OBJECT,
#                                                  2)
#         temperature = (block[0] | block[1] << 8) * 0.02 - 273.15
#         return temperature
#
#     def close(self):
#         #self.bus.close()
#         pass
#
# # my_camera = utils.Camera()
# # my_camera.start_preview()
# # time.sleep(1000)
# while True:
#     temp = IRTemperatureSensor().get_value()
#     print(temp)

# my_camera = utils.Camera()
# my_camera.start_preview()
# time.sleep(1000)



# import os
#
# while True:
#     print(time.time())
#     os.system('sudo /home/pi/Desktop/YVoltage VOLTAGE1-A953A.voltage1 get_currentValue')
#     print(time.time())

from pytz import timezone
import datetime
import pytz

utc = pytz.utc
#tz = utils.get_time_zone()
lj_tz = timezone('Europe/Ljubljana')
my_time = lj_tz.localize(datetime.datetime.now()).astimezone(utc)
print(my_time)
print(my_time.tzinfo)
print(my_time.astimezone(lj_tz))
