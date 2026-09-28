from labintfactory.interfaces.microcontroller import Microcontroller

micro=Microcontroller()

micro.connect(com="/dev/ttyUSB0", baudrate=9600, timeout=1)


data=micro.send_command('j')

#data="valid_flag:125\ncalibration_status:1\ncurrent_position:304787\ncalibration_status:1\ncurrent_position:304787\nmax_position:304787\nspeed:3000.00\nmotor_enabled:0\nmax_position:304787\nspeed:3000.00\nmotor_enabled:0"
data=data.split("\n")

data={x.split(":")[0]:float(x.split(":")[1]) for x in data}

print(bool(data['motor_enabled']))

