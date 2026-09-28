import serial
import serial.tools.list_ports
import ipywidgets as widgets

from labintfactory.utils.interface_widgets import AButton

class OutputWidget:
    def __init__(self):
        self.__output_window=widgets.Output(layout={'border': '2px solid black'})
        self.__clean=self._clean_interface_widget()

        
    
        
    @property
    def output_window(self):
        return self.__output_window

    def _clean_interface_widget(self):
        def cleanUp(p):
            self.__output_window.clear_output()
        clean_button=AButton(description='Clear',
                             callback=cleanUp,
                             icon='snowplow',
                             disabled=False)
        return {'clean_button':clean_button}
    
    
    def render_interface(self):
        return widgets.VBox([self.__output_window,self.__clean['clean_button']])