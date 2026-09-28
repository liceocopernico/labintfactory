import ipywidgets as widgets # type: ignore
from labintfactory.photometer.photometer import Photometer
from labintfactory.utils.interface_widgets import AButton,ADropdown,AIntSlider

class ConfigurationWidget:
    
    def __init__(self,output:widgets.Output,microcontroller):
        self.__subwidgets:list=[]
        self.__microcontroller=microcontroller
        self.__photometer=Photometer(microcontroller)
        self.__samples=self._samples_widget()
        self.__integration_time=self._integration_time_widget()
        self.__gain=self._gain_widget()
        self.__leds=self._leds_widget()
        self.__power=self._power_widget()
        self.__set_power=self._set_power_widget()
        self.__get_reading=self._get_reading_widget()
        self.__output=output
        


    @property
    def photometer(self):
        return self.__photometer
    
    @property
    def microcontroller(self):
        return self.__microcontroller

    @property
    def get_reading(self):
        return self.__get_reading
    
    @property
    def set_power(self):
        return self.__set_power
    
    @property
    def power(self):
        return self.__power
    
    @property
    def leds(self):
        return self.__leds
    
    @property
    def integration_time(self):
        return self.__integration_time
    
    @property
    def gain(self):
        return self.__gain
    
    @property
    def samples(self):
        return self.__samples
    
    @property
    def output(self):
        return self.__output

    def _set_power_widget(self):
        def set_led_power(value):
            with self.output:
                print(f"Set power to: {self.power.value}")
                print(self.photometer.set_led_power(self.power.value))
                self.get_reading['button'].disabled=False
        
        power_button=AButton(description='Set power',
                            disabled=True,
                            callback=set_led_power, 
                            tooltip='Set led power',
                            icon='ruler')
        
        power_button.on_click(set_led_power)
        self.__subwidgets.append(power_button)
        return power_button
        

    def _power_widget(self):
        current_value=self.leds['leds_data'][self.leds['widget'].value][0]
        
        power_slider=AIntSlider(
                            value=current_value,
                            min_value=self.leds['leds_data'][self.leds['widget'].value][0],
                            max_value=self.leds['leds_data'][self.leds['widget'].value][1],
                            description='Led Power',
                            disabled=True,
                            style='large')
        self.__subwidgets.append(power_slider)
        return power_slider
        
    def _leds_widget(self):
        def handle_led_change(change):
            self.power.value=available_leds[leds.value][0]
            self.power.min=available_leds[leds.value][0]
            self.power.max=available_leds[leds.value][1]
        
        
        available_leds={'red':[100,4000],
                'green':[780,900],
                'blue':[780,850],
               'orange':[780,850]}

        
        leds=ADropdown(options=['red','green','blue','orange'],
                       value='red',
                       description='Led color',
                       disabled=True,
                       callback=handle_led_change,
                       style='large')
        
        

        self.__subwidgets.append(leds)
        return {'leds_data':available_leds,'widget':leds}
    
    def _integration_time_widget(self):
        def set_int_time(change):
            self.photometer.int_time=change.new
            
        integration_time=ADropdown(options=[100,200,300,400,500,600],
                                   value=100,
                                    description='Integration time (ms):',
                                    disabled=True,
                                    style='large',
                                    callback=set_int_time)
        
        self.__subwidgets.append(integration_time)
        return integration_time
    
    def _gain_widget(self):
        def set_gain(change):
            self.photometer.gain=change.new
            print(change.new)
        gain=ADropdown(options=[1,25,428,9876],
                                   value=25,
                                    description='Analog gain:',
                                    disabled=True,
                                    style='large',
                                    callback=set_gain)
        
        self.__subwidgets.append(gain)
        return gain

    def _samples_widget(self):
        
        samples=ADropdown(options=range(1,16),
                          description='Samples (number):',
                          value=1,
                          disabled=True,
                          style='large')
        
        self.__subwidgets.append(samples)
        return samples

    def _get_reading_widget(self):
            
        def get_reading(b):
            light=self.photometer.get_light_reading(n_samples=self.samples.value,int_time=self.integration_time.value)
            if light[3]:
                output_data.style.text_color='red'
                output_data.value=f"Sensor is saturated, lower led power raw visible: {light[1]} raw ir: {light[2]}"     
            else:                
                if light[0]<=0:
                    output_data.style.text_color='red'
                    output_data.value=f"No light or light too dim, raise led power"
                                
                else:
                    output_data.style.text_color='green'
                    output_data.value=f"Lux: {round(light[0],4)} raw visible: {light[1]} raw ir: {light[2]}"
                    self.photometer.led_in_range=True 
                    
                    
        measure_button=AButton(description='Test light intensity',
                                disabled=True, 
                                tooltip='Test Light intensity',
                                icon='sun',
                                callback=get_reading)
      
        
        output_data=widgets.Label(value="",style=dict(
                                                font_weight='bold',
                                                font_variant="small-caps",
                                                text_color='green',
                                                
                                                ))
        
        
        self.__subwidgets.append(measure_button)
        return {'button':measure_button,'data':output_data}

    def enable(self):
        self.power.value=self.photometer.get_led_power()
        self.photometer.read_photometer_data()
        self.integration_time.value=self.photometer.int_time
        self.gain.value=self.photometer.gain
        for widget in self.__subwidgets:
            widget.disabled=False

    def disable(self):
        for widget in self.__subwidgets:
            widget.disabled=True
            
        
    def render_interface(self):
        configuration_1=widgets.HBox([self.samples,self.integration_time,self.gain,self.leds['widget'],self.power,self.set_power])
        configuration_2=widgets.HBox([self.get_reading['button'],self.get_reading['data']])
        return widgets.VBox([configuration_1,configuration_2])
        