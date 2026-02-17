import time
import statistics
import serial
import serial.tools.list_ports
import ipywidgets as widgets
import ipysheet



class Microcontroller:

    def __init__(self,com="/dev/ttyACM0",*,baudrate=115200,timeout=0.1):
        self.__device=None
        self.__com=com
        self.__baud=baudrate
        self.__timeout=timeout
        self.__connected=False

    @property
    def connected(self):
       return self.__connected 
        

    def handshake(self,sleep_time=1):
        self.flush_buffer()
        self.send_command('y')
        handshake_response=self.send_command('h')
        return handshake_response

       
    def connect(self,*,com="/dev/ttyACM0",baudrate=115200,timeout=1):
        self.__com=com
        self.__baud=baudrate
        self.__timeout=timeout
        
        try:
            self.__device=serial.Serial(self.__com, baudrate=self.__baud, timeout=self.__timeout, dsrdtr=False)
            self.__connected=True
            
        except Exception as e:
             print(e)
             return False
        return True

    def flush_buffer(self):
        timeout = self.__device.timeout
        out_message=''
        self.__device.timeout = 2
        while (self.__device.in_waiting < 0):
            pass
        while True:
            response= self.__device.read_until()
            if not response:
                break
            
    
    def send_command(self,command):
        timeout = self.__device.timeout
        out_message=''
        self.__device.timeout = 2
        self.__device.write(command.encode())
        while (self.__device.in_waiting < 0):
            pass
        
        while True:
            response= self.__device.read_until()
            time.sleep(0.1)
            if  response.decode().strip()=='executed':
                break
            out_message+=response.decode().strip()
            if len(response.decode().strip())>0:
                print(response.decode().strip())
            else:
                print("- ")
        self.__device.timeout = timeout
        return out_message