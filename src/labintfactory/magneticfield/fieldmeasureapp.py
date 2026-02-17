import serial
import serial.tools.list_ports
import ipywidgets as widgets

import ipysheet



from labintfactory.interfaces.vernier import data_interface
from labintfactory.utils import debug
from labintfactory.magneticfield.setup import MagneticSetupWidget
from labintfactory.magneticfield.configuration import ConfigurationWidget

class FieldMeasureApp:
    def __init__(self):
        self.__debug=debug.OutputWidget()
        self.__setup=MagneticSetupWidget(output=self.__debug.output_window)
        self.__configuration=ConfigurationWidget(setup=self.__setup)

    def render_interface(self):
        def handle_tab_change(e):
               match e.new:
                   case 1:
                       self.__configuration.enable()
                       """if self.__setup.magnetic_connection:
                           self.__configuration.enable()
                       else:
                           self.__configuration.disable()"""
                   
                    
        tab_contents = ['Setup','Configuration','Debug output']
        setup=self.__setup.render_interface()
        configuration=self.__configuration.render_interface()
        debug=self.__debug.render_interface()
        
        
        children = [setup,configuration,debug]
        tab = widgets.Tab()
        tab.children = children
        tab.titles = tab_contents
        tab.observe(handle_tab_change, names='selected_index')
        
        
        
        return tab    

