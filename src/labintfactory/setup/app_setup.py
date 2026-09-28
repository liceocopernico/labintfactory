class Device:
    def __init__(self,name, device_type,device_properties:list):
        self.__name=name
        self.__device_type=device_type
        self.__device_properties=device_properties
        self.__device_state:dict={}

    @property
    def name(self):
        return self.__name

    @property
    def device_type(self):
        return self.__device_type
    
    @property
    def device_properties(self):
        return self.__device_properties
   
    def set(self,property,value):
            if property in self.__device_properties:
                self.__device_state[property]=value
    def get(self,property):
        if property in self.__device_properties:
                return self.__device_state[property]
               

class AppSetup:
    def __init__(self,app_name='not_initialized'):
            self.__app_name=app_name
            self.__devices:dict={}
    
    @property
    def app_name(self):
        return self.__app_name
    
       
    @app_name.setter
    def app_name(self, value):
        self.__app_name = value


    @property
    def device(self):
        return self.__devices
    
   
    
    def has(self,device):
        return True if device in self.__devices else False
    
    def add_device(self,device_name,device_type, device_properties:list):
        new_device=Device(device_name,device_type,device_properties)
        self.__devices[device_name]=new_device
    
    def get_device(self,name):
        return self.__devices[name]
    
    def list_devices(self):
        return self.__devices.keys()