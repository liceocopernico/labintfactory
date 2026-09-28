from godirect import GoDirect
import statistics

import time

class InstrumentsInterface:
    def __init__(self,sensor_type:str):
        self.sensor_type = sensor_type
        self.usb_interface=None
        self.devices=[]
        self.current_device=None
       
    def connect_interface(self):
        
        self.usb_interface=GoDirect(use_ble=False, use_usb=True)
        self.devices=self.usb_interface.list_devices()
        self.current_device=None
        
        for device in self.devices:
            
            device.open()
            #get sensors type
            for id,sensor in device.list_sensors().items():
                
               if self.sensor_type in sensor.sensor_description:
                   self.current_device=device
            
            print(self._get_device_properties())
            
            device.close()
        return True if self.current_device is not None else False
  
    def disconnect_interface(self):
        if self.current_device is not None:
           if self.current_device.is_connected():
            self.current_device.close()
           self.current_device=None
           return True
        else:
            return False
    
    
    def _get_device_properties(self):
        device_info=[]
        device_info.append(self.current_device._name)
        device_info.append(self.current_device._description)
        device_info.append(self.current_device._name)
        device_info.append(self.current_device._description)
        device_info.append(self.current_device._battery_level_percent) 
        charger_state = ["Idle", "Charging", "Complete", "Error"]  
        device_info.append(charger_state[self.current_device._charger_state])
        device_info.append(self.current_device._rssi)
        return device_info
    
    def get_device_informations(self):
        
        self.current_device.open()
        device_info=self._get_device_properties()
        self.current_device.close()
        return device_info
    
    def get_device_sensors(self):
        self.current_device.open()
        sensors=self.current_device.list_sensors()
        self.current_device.close()
        return [{'description':sensor.sensor_description,'unit':sensor.sensor_units} for id,sensor in sensors.items()]

    def get_enabled_sensors(self):
        return self.current_device.get_enabled_sensors()

    def disable_sensors(self):
        self.current_device.open()
        for sensor in self.current_device.get_enabled_sensors():
            sensor.enabled=False
        self.current_device.close()
    
    def enable_sensors(self,sensors_list:list|tuple):
       
        self.disable_sensors()
        self.current_device.open()
        self.current_device.enable_sensors(sensors_list)
        self.current_device.close()
        

        
    def get_sensors_unit(self):
        enabled_sensors=self.get_enabled_sensors()
        return [sensor.sensor_units for sensor in enabled_sensors]
        
    def get_reading(self,duration:int,samples:int):
        period=round(duration/samples)
        self.current_device.open()
        enabled_sensors=self.get_enabled_sensors()
        print(f"Sensors to enable {enabled_sensors}")
        values=[]
        self.current_device.start(period)
        for i in range(samples):
            time.sleep(float(period/1000))
            self.current_device.read()
            
        measurement=[]
        
        for sensor in enabled_sensors:
                measurement.append(sensor.values)
           
        self.current_device.stop()
        self.current_device.close()
        return [statistics.mean(ax) for ax in measurement]