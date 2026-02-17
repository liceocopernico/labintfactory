import ipywidgets as widgets

from labintfactory.generic.setup import SetupWidget
from labintfactory.interfaces.vernier.data_interface import InstrumentsInterface
from labintfactory.utils.interface_widgets import AButton


class MagneticSetupWidget(SetupWidget):
    def __init__(self,*,output):
        super().__init__(output)
        self.__hall_sensor=self._hall_sensor_widget()
        self.__vernier=InstrumentsInterface('magnetic field')
        self.__magnetic_connection=False
        
     
    @property
    def magnetic_connection(self):
        return self.__magnetic_connection
    
    @property
    def vernier(self):
        return self.__vernier
        
    @property
    def hall_sensor(self):
        return self.__hall_sensor
        
    def _hall_sensor_widget(self):
        def connect_hall_sensor(b):           
            with self.output:
                print("interface connection")
                self.vernier.connect_interface()
                self.__magnetic_connection=True
                b.button_style='info'
                
        hall_connect_button=AButton(description='Hall Sensor',style='large',callback=connect_hall_sensor,disabled=False)
        
        return hall_connect_button
    
    def render_interface(self):
           interface=widgets.HBox([self.com_port,self.microcontroller_connection,self.handshake,self.hall_sensor])
           return interface