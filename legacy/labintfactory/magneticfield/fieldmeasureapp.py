
import ipywidgets as widgets # type: ignore
from labintfactory.utils import debug
from labintfactory.magneticfield.setup import MagneticSetupWidget
from labintfactory.magneticfield.configuration import ConfigurationWidget
from labintfactory.magneticfield.measure import MeasureWidget
from labintfactory.setup import instrument_configuration



class FieldMeasureApp:
    def __init__(self):
        
        instrument_configuration.app_name='fieldmeasureapp'
        self.__debug=debug.OutputWidget()
        self.__setup=MagneticSetupWidget(output=self.__debug.output_window)
        self.__configuration=ConfigurationWidget(setup=self.__setup)
        self.__measure=MeasureWidget(self.__configuration)
        
        
    def render_interface(self):
        def handle_tab_change(e):
               match e.new:
                   case 1:
                       self.__configuration.enable()
                       
                   case 2:
                        self.__measure.show_graph()
                        self.__measure.update()
                        
                   
                    
        tab_contents = ['Setup','Configuration','Measure','Debug output']
        setup=self.__setup.render_interface()
        configuration=self.__configuration.render_interface()
        measure=self.__measure.render_interface()
        debug=self.__debug.render_interface()
        
        
        children = [setup,configuration,measure,debug]
        tab = widgets.Tab()
        tab.children = children
        tab.titles = tab_contents
        tab.observe(handle_tab_change, names='selected_index')
        
        
        
        return tab    

