import time


from labintfactory.interfaces.microcontroller import Microcontroller
import statistics
import math
class Photometer:
    
    TSL2561_CLIPPING_402MS:int=65000
    TSL2561_LUX_CHSCALE:int=10
    TSL2561_LUX_RATIOSCALE:int =9
    
    def __init__(self,microcontroller):
        self.__microcontroller=microcontroller
        self.__zil=0.0
        self.__last_reading=0.0
        self.__is_calibrated=False
        self.__calibration_data=None
        self.__led_in_range=False

    @property
    def led_in_range(self):
        return self.__led_in_range

    @led_in_range.setter
    def led_in_range(self,status):
        self.__led_in_range=status
    
    @property
    def is_calibrated(self):
        return self.__is_calibrated


    @property
    def calibration_data(self):
        return self.__calibration_data

    @calibration_data.setter
    def calibration_data(self,data):
        if type(data)==list:
            self.__calibration_data=data
            self.__is_calibrated=True
        else:
            print("Invalid data")

    
    @property
    def zil(self):
        return self.__zil

    @zil.setter
    def zil(self,zeroth_illuminance):
        self.__zil=zeroth_illuminance
    
        
    @property
    def microcontroller(self):
        return self.__microcontroller

    
    def transmittance(self):
        try:
            return self.__last_reading/self.__zil
        except ZeroDivisionError:
            print("Zeroth illuminance reading is zero")
            return float('inf')
    
    def absorbance(self):
        print(f"Last reading value: {self.__last_reading}")
        try:
            return math.log10(self.__zil/self.__last_reading)
        except ZeroDivisionError:
            print("Last reading is zero")
            return float('inf')
            
    
    def _parse_raw_line(self,raw_line):
        
        data=raw_line.rstrip().split("|")
        
        if len(data)!=2:
            raise ValueError(f"Incorrect data type, received {data}")
        else:
            return int(data[0]),int(data[1])
    
    def _calculateLux(self,broadband:int,ir:int):
        clipThreshold = self.TSL2561_CLIPPING_402MS
        chScale = (1 << self.TSL2561_LUX_CHSCALE)
        channel0:int = (broadband * chScale) >> self.TSL2561_LUX_CHSCALE
        channel1:int = (ir * chScale) >> self.TSL2561_LUX_CHSCALE
        ratio:float=0
        lux:float=0
        if (channel0 != 0):
            ratio =channel1/channel0
            
        if ratio>0 and ratio <=0.5:
            lux=0.0304*channel0-0.062*channel0*pow(ratio,1.4)
        elif ratio>0.5 and ratio<=0.61:
            lux=0.0224*channel0-0.031*channel1
        elif ratio>0.61 and ratio <=0.80:
            lux=0.0128*channel0-0.0153*channel1
        elif ratio>0.80 and ratio <=1.30:
            lux=0.00146*channel0-0.00112*channel1
        elif ratio>1.30 and ratio <=3.00:
            lux=0.0
        
        return round(lux,1)

    def set_led_power(self,power):
        self.microcontroller.send_command(f"l{power}")
        
    def get_led_power(self):
        return int(self.microcontroller.send_command('i'))
    
    def get_light_reading(self,*,int_time,n_samples):
       
        broadband_readings=[]
        ir_readings=[]
        reading=0
        saturated=False
        threshold=self.TSL2561_CLIPPING_402MS
        self.microcontroller.send_command('y')
        
        while reading < n_samples:
                # send  TSL2561 data reading command
                raw=self.microcontroller.send_command('r')
            
                try:
                    broadband,ir=self._parse_raw_line(raw)
                except ValueError as e:
                    continue
                reading+=1
                broadband_readings.append(broadband)
                ir_readings.append(ir)
                time.sleep(1.5*int_time/1000)
        
        lux_data=self._calculateLux(int(statistics.mean(broadband_readings)),int(statistics.mean(ir_readings)))
        saturated=True if int(statistics.mean(broadband_readings))>threshold or int(statistics.mean(ir_readings))> threshold else False
        
        self.__last_reading=lux_data
        
        return (lux_data,int(statistics.mean(broadband_readings)),int(statistics.mean(ir_readings)),saturated)