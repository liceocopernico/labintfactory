import time
import serial
import serial.tools.list_ports
import ipywidgets as widgets
import ipysheet
import matplotlib.pyplot as plt
import math
from sklearn.linear_model import LinearRegression
import numpy as np


from labintfactory.interfaces.microcontroller import Microcontroller
from labintfactory.photometer.photometer import Photometer
from labintfactory.generic.setup import SetupWidget
from labintfactory.utils.debug import OutputWidget
from labintfactory.photometer.configuration import ConfigurationWidget
from labintfactory.photometer.calibration import CalibrationWidget
from labintfactory.photometer.measure import MeasureWidget

class Absorbance:
    def __init__(self):
        self.__output=OutputWidget()
        self.__setup=SetupWidget(self.__output.output_window)
        self.__configuration=ConfigurationWidget(self.__output.output_window,self.__setup.microcontroller)
        self.__calibration=CalibrationWidget(self.__configuration)
        self.__measure=MeasureWidget(self.__configuration)
    
    def draw_interface(self):
        def handle_tab_change(e):
                print(f"is ready {self.__setup.is_ready}")
                match e.new:
                    case 1:
                        if self.__setup.is_ready:
                            self.__configuration.enable()
                        else:
                            self.__configuration.disable()
                    case 2:
                        self.__calibration.show_graph()
                        print(f"led in range {self.__configuration.photometer.led_in_range}")
                        if self.__configuration.photometer.led_in_range:
                            self.__calibration.enable()
                        else:
                            self.__calibration.disable()
                    case 3:
                        if self.__configuration.photometer.is_calibrated:
                            self.__measure.enable()
                        else:
                            self.__measure.disable()
                        
                    
        tab_contents = ['Setup','Configuration','Calibration','Measure','Debug output']
        
       
        setup=self.__setup.render_interface()
        configuration=self.__configuration.render_interface()
        calibration=self.__calibration.render_interface()
        debug=self.__output.render_interface()
        measure=self.__measure.render_interface()
        children = [setup,configuration,calibration,measure,debug]
        tab = widgets.Tab()
        tab.children = children
        tab.titles = tab_contents
        tab.observe(handle_tab_change, names='selected_index')
        
        
        
        return tab    