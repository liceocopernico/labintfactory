import ipywidgets as widgets # type: ignore
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression # type: ignore
import ipysheet # type: ignore
import numpy as np
import asyncio
import time

from labintfactory.utils.interface_widgets import AButton

class MeasureWidget:
    def __init__(self,configuration):
        self.__subwidgets=[]
        self.__photometer=configuration.photometer
        self.__configuration=configuration
        self.__graph_output=widgets.Output(layout={'border': '2px solid black'})
        self._measure=self._measure_widget()
        self.__graphs=self._reaction_graph()
        self.__start_reaction=self._start_reaction_widget()
        self.__stop_reaction=self._stop_reaction_widget()
        self.__reaction_active=False

    @property
    def graphs(self):
        return self.__graphs


    @property
    def graph_output(self):
        return self.__graph_output
    
    @property
    def photometer(self):
        return self.__photometer

    @property
    def samples(self):
        return self.__configuration.samples.value

    @property
    def integration_time(self):
        return self.__configuration.integration_time.value
    
    
    
    async def measure_reaction(self,*,deltat):
            
            while self.__reaction_active:
                await asyncio.sleep(deltat)
                light=self.photometer.get_light_reading(n_samples=self.samples,int_time=self.integration_time)
                print(light)
    
    def _start_reaction_widget(self):
        def start_reaction(b):
            self.__reaction_active=True
            asyncio.create_task(self.measure_reaction(deltat=2))
        button=AButton(description='Start reaction',
                           disabled=True,
                           tooltip='Start reaction absorbance measurement',
                           icon='sun',
                           callback=start_reaction)
        
        self.__subwidgets.append(button)
        return {'button':button}
    
    def _stop_reaction_widget(self):
        def stop_reaction(b):
            self.__reaction_active=False
        
        button=AButton(description='Stop reaction',
                           disabled=True,
                           tooltip='Stop reaction absorbance measurement',
                           icon='sun',
                           callback=stop_reaction)
        
        self.__subwidgets.append(button)
        return {'button':button}

    
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


    def _reaction_graph(self):
             
        with self.graph_output:
            regfigure,ax= plt.subplots(figsize=[30,15])
            regscatter, = ax.plot([], [], 'bo', label='Time vs Absorbance')
            ax.axes.get_xaxis().set_visible(False)
            #setup reg lines and plot intervals
            regline1, = ax.plot([], [], 'r', label='Reaction absorbance in time')
            ax.legend()
            ax.set_title('Time vs Absorbance ')
            ax.grid(axis='both')
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Absorbance')
            regfigure.set_visible(False)
        
        return {'figure':regfigure,'axis':ax,'scatter':regscatter,'line':regline1}


    def show_graph(self):
        self.graphs['figure'].set_visible(True)
        self.graph_output.clear_output(wait=True)
        self.graphs['axis'].axes.get_xaxis().set_visible(True)
        with self.graph_output:
                  display(self.graphs['figure'])

    def enable(self):
        for widget in self.__subwidgets:
            widget.disabled=False

    def disable(self):
        for widget in self.__subwidgets:
            widget.disabled=True
    
    def render_interface(self):
        absorbance_measure=widgets.HBox([self._measure['button'],self._measure['data'],
                                         self.__start_reaction['button'],
                                         self.__stop_reaction['button']])
        reaction_graph=widgets.HBox([self.graph_output])
        return widgets.VBox([absorbance_measure,reaction_graph])