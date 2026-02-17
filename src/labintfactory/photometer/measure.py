import ipywidgets as widgets
import ipysheet


from labintfactory.utils.interface_widgets import AButton
class MeasureWidget:
    def __init__(self,configuration):
        self.__subwidgets=[]
        self.__photometer=configuration.photometer
        self.__configuration=configuration
        self._measure=self._measure_widget()


    @property
    def photometer(self):
        return self.__photometer

    @property
    def samples(self):
        return self.__configuration.samples.value

    @property
    def integration_time(self):
        return self.__configuration.integration_time.value
        
        

    
    def _measure_widget(self):
            def get_reading(b):
                light=self.photometer.get_light_reading(n_samples=self.samples,int_time=self.integration_time)
                calibration=self.photometer.calibration_data
                molarity.value=(self.photometer.absorbance()-calibration[1])/calibration[0]

            button=AButton(description='Measure molarity',
                           disabled=True,
                           tooltip='Get illuminance reading',
                           icon='sun',
                           callback=get_reading)
        
            molarity=widgets.FloatText(
                        value=0,
                        description='Molarity (mol/L)',
                        disabled=True)
            molarity.style.description_width='140px'
            
            self.__subwidgets.append(button)
            return {'button':button,'data':molarity}

    def enable(self):
        for widget in self.__subwidgets:
            widget.disabled=False

    def disable(self):
        for widget in self.__subwidgets:
            widget.disabled=True
    
    def render_interface(self):
        return widgets.HBox([self._measure['button'],self._measure['data']])