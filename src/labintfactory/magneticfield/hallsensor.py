class HallSensor:
    def __init__(self,*,setup):
        self.__interface=setup.vernier
        self.__sensors=[]
        self.__setup=setup
        self.__sensors_unit=[]
        self.__labels=[]



    @property
    def labels(self):
        return self.__labels
        
    @property
    def sensors(self):
        return self.__sensors

    @property
    def sensors_unit(self):
        return self.__sensors_unit

    
    @sensors.setter
    def sensors(self,available):
        self.__sensors=available
        if available:
            self.__interface.enable_sensors(available)
            
   
    
    def getDeviceInfo(self,p=None):
            if self.__setup.magnetic_connection:
                for myinfo in self.__interface.get_device_informations():
                    print(myinfo)
            else:
                    print("Device not connected")
    
    def getSensorsInfo(self,p=None):
        available_sensors=[]
        self.__labels=[]
        if self.__setup.magnetic_connection:
                for i,sensor in enumerate(self.__interface.get_device_sensors()):
                        info=sensor['description']
                        available_sensors.append((info,i+1))
                        self.__labels.append(info)
                        self.__sensors_unit.append(sensor['unit']) 
        return available_sensors

    
    def read(self,duration=100,samples=1):
        return self.__interface.get_reading(duration,samples)