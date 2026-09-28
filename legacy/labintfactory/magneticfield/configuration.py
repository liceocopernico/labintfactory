import ipywidgets as widgets # type: ignore
from labintfactory.magneticfield.setup import MagneticSetupWidget
from labintfactory.utils.interface_widgets import AButton,ADropdown,ASelectMultiple,AIntSlider
from labintfactory.utils.debug import OutputWidget
from labintfactory.magneticfield.hallsensor import HallSensor
from labintfactory.linear_actuator.configuration import ConfigurationWidget as LAConfigurationWidget

from labintfactory.setup import instrument_configuration

class ConfigurationWidget:
    device_name='hall_sensor'
    
    def __init__(self,*,setup:MagneticSetupWidget):
        self.__subwidgets:list=[]
        self.__hall_sensor=HallSensor(setup=setup)
        self.__setup=setup
        self.__hall_sensor_interface=self._hall_sensor_widget()
        self.__selected_hall_sensors:list=[]
        self.__test_output=OutputWidget()
        self.__linear_actuator_interface=LAConfigurationWidget(setup=setup,output=self.__test_output)
        self.__status:dict=self.status()
        
        instrument_configuration.add_device(self.device_name,'sensor',['samples','measure_interval','channels'])
        instrument_configuration.device[self.device_name].set('samples',5)
        instrument_configuration.device[self.device_name].set('measure_interval',10)
        
       

    @property
    def linear_actuator(self):
        return self.__linear_actuator_interface.linear_actuator
    

    @property
    def selected_hall_sensors(self):
        return self.__selected_hall_sensors
    
    @property
    def hall_sensor(self):
        return self.__hall_sensor
    
    @property
    def hall_sensor_interface(self):
        return self.__hall_sensor_interface


    def _hall_sensor_widget(self):

        def max_samples(p):
            instrument_configuration.device[self.device_name].set('measure_interval',int(p.new)) 
            elements['samples_number'].max=int(p.new/10)
        
        def set_samples_number(e):
            instrument_configuration.device[self.device_name].set('samples',int(e.new))
            
        def addMeasureSensor(p):
            self.__selected_hall_sensors=p.new
            print(self.selected_hall_sensors)
            print("Reset sensors list")
            instrument_configuration.device[self.device_name].set('channels',self.selected_hall_sensors)
            self.hall_sensor.sensors=self.selected_hall_sensors
            
        
           
            
        def getFieldValue(p):
            
            readings=self.hall_sensor.read(elements['measure_interval'].value,elements['samples_number'].value)
            with self.__test_output.output_window:
                
                for i,value in enumerate(readings):
                    print(f"{ self.hall_sensor.labels[self.hall_sensor.sensors[i]-1]} ({self.hall_sensor.sensors_unit[self.hall_sensor.sensors[i]-1]}):  {value}")

        elements={}
        
        elements['hall_sensor_info']=AButton(description='Query info',
                                 callback=self.hall_sensor.getDeviceInfo)
               
         
        elements['active_sensors']=ASelectMultiple(options_callback=self.hall_sensor.getSensorsInfo,
                                       callback=addMeasureSensor,
                                       style='large',
                                       disabled=False)
        
        elements['test_measurement']=AButton(description='Get Field',
                                 callback=getFieldValue)
      
        elements['measure_interval']=AIntSlider(value=50,min_value=100,max_value=1000,description='Measure time',callback=max_samples)
        elements['samples_number']=AIntSlider(value=1,min_value=1,
                                              max_value=int(elements['measure_interval'].value/10),
                                              description='Samples number',
                                              callback=set_samples_number)


        for index,element in elements.items():
            self.__subwidgets.append(elements[index])
        
        return elements


    def status(self):
         status={}
         connection_status=self.linear_actuator.is_connected
         status['calibrated']=widgets.Checkbox(
                                        value=connection_status,
                                        description='Calibrated!' if connection_status else 'Not calibrated!',
                                        disabled=True
                                        )   
         status['calibrated'].style=dict(font_weight='bold',
                                         text_color='red',
                                         description_width='100px')
         return status
        
    def enable(self):
            if self.__setup.magnetic_connection:
                for widget in self.__subwidgets:
                    widget.disabled=False
                    widget.update()
            if self.__setup.microcontroller.connected:    
                self.__linear_actuator_interface.enable()

    def disable(self):
            for widget in self.__subwidgets:
                widget.disabled=True
                widget.update()

    def render_interface(self):
            status_interface=widgets.HBox([widget for widget in self.__status.values()])
            
            magnetic_interface=widgets.HBox([widget for widget in self.__hall_sensor_interface.values()])
            magnetic_slice = widgets.Accordion(children=[magnetic_interface], titles=('Hall sensor',))
            
            linear_actuator_interface=self.__linear_actuator_interface.render_interface()
            interface=widgets.VBox([status_interface,magnetic_slice,linear_actuator_interface,self.__test_output.render_interface()])
        
            return interface