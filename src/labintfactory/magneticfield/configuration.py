import ipywidgets as widgets
from labintfactory.magneticfield.setup import MagneticSetupWidget
from labintfactory.utils.interface_widgets import AButton,ADropdown,ASelectMultiple,AIntSlider
from labintfactory.utils.debug import OutputWidget
from labintfactory.magneticfield.hallsensor import HallSensor
from labintfactory.linear_actuator.configuration import ConfigurationWidget as LAConfigurationWidget

class ConfigurationWidget:
    def __init__(self,*,setup:MagneticSetupWidget):
        self.__subwidgets=[]
        self.__hall_sensor=HallSensor(setup=setup)
        self.__setup=setup
        self.__hall_sensor_interface=self._hall_sensor_widget()
        self.__selected_hall_sensors=[]
        self.__test_output=OutputWidget()
        self.__linear_actuator_interface=LAConfigurationWidget(setup=setup,output=self.__test_output)

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
            print(int(p.new/10))
            elements['samples_number'].max=int(p.new/10)
            
        def addMeasureSensor(p):
            self.__selected_hall_sensors=p.new
            print(self.selected_hall_sensors)
            self.hall_sensor.sensors=self.selected_hall_sensors
            
        def getFieldValue(p):
            
            readings=self.hall_sensor.read(elements['measure_interval'].value,elements['samples_number'].value)
            with self.__test_output.output_window:
                print(readings)
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
        elements['samples_number']=AIntSlider(value=1,min_value=1,max_value=int(elements['measure_interval'].value/10),description='Samples number')


        for index,element in elements.items():
            self.__subwidgets.append(elements[index])
        
        return elements


        
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
            magnetic_interface=widgets.HBox([widget for widget in self.__hall_sensor_interface.values()])
            linear_actuator_interface=self.__linear_actuator_interface.render_interface()
            interface=widgets.VBox([magnetic_interface,linear_actuator_interface,self.__test_output.render_interface()])
        
            return interface