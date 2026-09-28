class LinearActuator:
    def __init__(self,microcontroller):
        self.__microcontroller=microcontroller
        self.__resolution=1.25e-3
        self.__commands={'handshake':{'description':'Handshake','tooltip':'Handshake','command':'h','icon':'handshake','display':True},
                         'motor_home':{'description':'Motor home','tooltip':'Motor home','command':'w','icon':'house','display':True},
                         'end_home':{'description':'Motor home','tooltip':'End home','command':'x','icon':'flag-checkered','display':True},
                         'calibrate':{'description':'Calibrate','tooltip':'Calibrate homes','command':'c','icon':'gear','display':True},
                         'ping':{'description':'Ping','tooltip':'Ping microcontroller','command':'p','icon':'reply','display':True},
                         'forward1':{'description':'Forward 1','tooltip':'Forward 1 turn','command':'f','icon':'forward','display':True},
                         'backward1':{'description':'Backward 1','tooltip':'Backward 1 turn','command':'b','icon':'backward','display':True},
                         'get_pos':{'description':'Get pos','tooltip':'Get Position','command':'g','icon':'asterisk','display':True},
                         'stop_status':{'description':'Stop status','tooltip':'Get stop status','command':'e','icon':'stop','display':True},
                         'max_pos':{'description':'Max pos','tooltip':'Get Max Position','command':'a','icon':'maximize','display':True},
                         'move_pos':{'description':'Move to position','tooltip':'Move to  position','command':'u','icon':'maximize','display':False},
                         'clear_buffer':{'description':'Clear buffer','tooltip':'Clear microcontroller buffer','command':'y','icon':'snowplow','display':True},
                         'is_calibrated':{'description':'Calibration status','tooltip':'Check calibration status','command':'r','icon':'maximize','display':False},
                         'print_data':{'description':'Display conf','tooltip':'Display actuator status','command':'j','icon':'info','display':True},
                         'set_speed':{'description':'Set speed','tooltip':'Set actuator speed','command':'s','icon':'maximize','display':False},
                         'get_speed':{'description':'Get speed','tooltip':'Get actuator speed','command':'i','icon':'maximize','display':False},
                         'disable':{'description':'Disable motor','tooltip':'Disable motor ','command':'n','icon':'maximize','display':False},
                         'enable':{'description':'Enable motor','tooltip':'Enable motor ','command':'o','icon':'maximize','display':False}}
        
        
        if self.__microcontroller.connected:
            self.__max_ticks=int(self.send_command('max_pos'))
        else:
            self.__max_ticks=-100
                         
    @property
    def commands(self):
        return self.__commands
    
    @property
    def resolution(self):
        return self.__resolution

    @property
    def position(self):

        if self.__max_ticks>0:
            return  self.resolution*int(self.send_command('get_pos'))
        else:
            return 0
    
    @property
    def is_connected(self):
        if self.__microcontroller.connected:
            return bool(self.send_command('is_calibrated'))
        else:
            return False
    

    @property
    def max_position(self):
        if self.__max_ticks>0:
            return  self.resolution*self.__max_ticks
        elif self.__max_ticks <0 and self.__microcontroller:
            self.__max_ticks=int(self.send_command('max_pos'))
            return self.resolution*self.__max_ticks
        else:
            return 0

    
    
    def get_ticks(self):
        return {'current_ticks':int(self.send_command('get_pos')),'max_ticks':int(self.send_command('max_pos'))}
    
    def move_to_position(self,position):
        new_position=int(position/self.resolution)
        print(self.send_command("move_pos",argument=str(new_position))  )
    
    def send_command(self,command,*,argument=None):
        if command in self.__commands:
            if not argument:
                print(self.__commands[command]['command'])
                return self.__microcontroller.send_command(self.__commands[command]['command'])
            else:
                print(self.__commands[command]['command']+argument)
                return self.__microcontroller.send_command(self.__commands[command]['command']+argument)
        else:
            raise ValueError(f"Command {self.__commands[command]['command']} not defined")
    