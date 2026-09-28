import serial # type: ignore
import serial.tools.list_ports # type: ignore
import ipywidgets as widgets # type: ignore
import ipysheet # type: ignore
from labintfactory.interfaces.microcontroller import Microcontroller
from labintfactory.utils.interface_widgets import AButton,ADropdown

class SetupWidget:
    
    def __init__(self,output:widgets.Output):
        self.__microcontroller=Microcontroller()
        self.__com_port=self._com_port_widget()
        self.__microcontroller_connection=self._microcontroller_connection_widget()
        self.__handshake=self._handshake_widget()
        self.__output=output
        self.__is_ready=False

    @property
    def is_ready(self):
        return self.__is_ready
    
    @property
    def output(self):
        return self.__output
         
    @property
    def microcontroller_connection(self):
        return self.__microcontroller_connection

    @property
    def handshake(self):
        return self.__handshake
    
    @property
    def microcontroller(self):
        return self.__microcontroller

    
    @microcontroller.setter
    def microcontroller(self, micro):
        self.__microcontroller=micro
        
    @property
    def com_port(self):
        return self.__com_port

    def _com_port_widget(self):
        def handle_com_change(change):
            
            self.__microcontroller_connection.disabled=False
            print(change)
            
        com_ports=serial.tools.list_ports.comports()
        
        com_port=ADropdown(options=[p.device for p in com_ports if "USB" in p.device or "ACM" in p.device or "COM" in p.device],
                            description='Virtual serial device:',
                            disabled=False,
                            style='large',
                            callback=handle_com_change)
        
        com_speed=ADropdown(options=['9600','115200'],
                            description='Serial speed',
                            disabled=False,
                            style='large',)
        
        return [com_port,com_speed]
    
    
    def _handshake_widget(self):
                def handshake(b):
                    with self.__output:
                        print(self.microcontroller.handshake())
                        self.__is_ready=True
                handshake_button=AButton(description='Handshake',
                                         style='large',
                                         tooltip='Microcontroller handshake',
                                         icon='handshake',
                                         callback=handshake)
                             
                return handshake_button

    def _microcontroller_connection_widget(self):
            def connect_microcontroller(b):           
                if self.microcontroller.connect(com=self.com_port[0].value, baudrate=int(self.com_port[1].value), timeout=1):
                    with self.output:
                        print("Microcontroller connected")
                        self.handshake.disabled=False
                        self.is_connected=True
                else:
                    with self.output:
                        print("Cannot connect to microcontroller")
                        return

            microcontroller_connect_button=AButton(description='Microcontroller',
                                                    disabled=True,
                                                    tooltip='Start Microcontroller connection',
                                                    icon='plug',
                                                    style='large',
                                                    callback=connect_microcontroller)
            
            if len(self.com_port[0].options)==0: microcontroller_connect_button.disabled=True

            return microcontroller_connect_button
    
    def render_interface(self):
           interface=widgets.HBox([self.com_port[0],self.com_port[1],self.microcontroller_connection,self.handshake])
           return interface