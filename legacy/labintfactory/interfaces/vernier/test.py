import time
from data_interface import instrumentsInterface


hall_sensor=instrumentsInterface('magnetic field')

hall_sensor.connect_interface()

hall_sensor.enable_sensors([1,2,3])

readings=hall_sensor.get_reading(500,10)

print(readings)

hall_sensor.disconnect_interface()

