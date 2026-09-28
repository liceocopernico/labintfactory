import ipywidgets as widgets # type: ignore
from IPython.display import display,update_display
import matplotlib.pyplot as plt
from loguru import logger
import datetime
import asyncio
import time
import json
import csv

logger.disable(__name__)


from labintfactory.utils.interface_widgets import AButton,AText,AFloatText

class MeasureWidget:
    def __init__(self,configuration):
        
            
        self.__experiment_mol=[]
        self.__experiment_react=[] 
        self.__photometer=configuration.photometer
        self.__configuration=configuration
        self.__graph_output=widgets.Output(layout={'border': '2px solid black'})
        self.__deltaT:float=400.0  # type: ignore
        self.__reaction=[]
        self.__graphs=self._reaction_graph()
        
        self.__reaction_active=False
        self.__reaction_samples=AText(
                value='0',
                placeholder='Samples',
                description='Number of measured samples',
                disabled=False,
        )         
     
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
    
    
                
        
    
    def measure_reaction(self,*,deltat):
            
            asyncio.create_task(self.reaction_loop(deltat=deltat))

 
    def plot(self,deltat,sample_n):
        logger.debug("Sample {} integration time {} delta t {} ",self.samples,self.integration_time,deltat)
        light=self.photometer.get_light_reading(n_samples=self.samples,int_time=self.integration_time)
        self.__reaction.append([time.monotonic(),light[0],self.photometer.absorbance()])
        times=[measure[0]-self.__reaction[0][0] for measure in self.__reaction]
        absorbance=[measure[2] for measure in self.__reaction]
        ax=self.graphs['axis']
        ax.set_xlim(min(times), max(times)+1)
        ax.set_ylim(0.9*min(absorbance),1.1*max(absorbance))
        self.graphs['scatter'].set_data(times,absorbance)
        self.graph_output.clear_output(wait=True)
        with self.graph_output:
            self.graph_output.clear_output(wait=True)
            display(self.graphs['figure'])
            self.__reaction_samples.value=str(sample_n)
            
        return True
        
    async def reaction_loop(self,*,deltat):
        sample_n=0
        while self.__reaction_active:
            """ logger.debug("Sample {} integration time {} delta t {} ",self.samples,self.integration_time,deltat)
            light=self.photometer.get_light_reading(n_samples=self.samples,int_time=self.integration_time)
            self.__reaction.append([time.monotonic(),light[0],self.photometer.absorbance()])
            times=[measure[0]-self.__reaction[0][0] for measure in self.__reaction]
            absorbance=[measure[2] for measure in self.__reaction]
            ax=self.graphs['axis']
            ax.set_xlim(min(times), max(times)+1)
            ax.set_ylim(min(absorbance)-0.2,max(absorbance)+0.1)
            self.graphs['scatter'].set_data(times,absorbance)
            self.graph_output.clear_output(wait=True)
            with self.graph_output:
                self.graph_output.clear_output(wait=True)
                display(self.graphs['figure'])
                self.__test.value=str(sample_n)
                sample_n+=1 """
                
            self.plot(deltat,sample_n)
            sample_n+=1
                
            await asyncio.sleep(deltat)
            
 
    def _save_reaction_widget(self,e=None):
        
        def update_graph(change):
         with self.graph_output:
                self.graph_output.clear_output(wait=True)
                display(self.graphs['figure'])   
        
        def save_reaction_data(e):
            reaction_data={'measures':self.__reaction,
                            'zil':self.photometer.zil,
                            'reaction':reaction_desc.value,
                            'led_power':self.__configuration.power.value,
                            'led_color':self.__configuration.leds['widget'].value}
            
            json_str = json.dumps(reaction_data, indent=4)
            
            with open(f"{reaction_desc.value}_{datetime.datetime.now()}.csv", 'w', newline='') as csvfile:
                            data_writer = csv.writer(csvfile, delimiter=',',
                            quotechar='|', quoting=csv.QUOTE_MINIMAL)
                            data_writer.writerow(['t(s)','illuminance(lux)','absorbance'])
                            for measure in self.__reaction:
                                data_writer.writerow(measure)
            
            with open(f"{reaction_desc.value}_{datetime.datetime.now()}.json", "w") as f:
                    f.write(json_str)
                    
                    
        def update_deltat(change):
            self.__deltaT=change.new
            if self.__deltaT<self.__configuration.integration_time.value:
                delta_t.value=self.__configuration.integration_time.value
                self.__deltaT=self.__configuration.integration_time.value
        
        def clear_reaction_data(e):
            if not self.__reaction_active:
                self.__reaction=[]
                self.graphs['scatter'].set_data([],[])
                with self.graph_output:
                    self.graph_output.clear_output()
                    display(self.graphs['figure'])
        
        reload_button=AButton(description='Reload data',
                       disabled=False,
                       tooltip='Reload measured data',
                       icon='repeat',
                       callback=update_graph)
                

        reaction_desc=AText(
                value='Simple reaction',
                placeholder='Insert reaction name',
                description='Reaction name:',
                disabled=False   
        )         
        save_button = AButton(
                description='Save data',
                disabled=False,
                style='large', 
                tooltip='Save reaction in json format',
                icon='save',
                callback=save_reaction_data
            )
        
        clear_button = AButton(
                description='Clear measure',
                disabled=False,
                style='large', 
                tooltip='Clear data',
                icon='trash',
                callback=clear_reaction_data
            )
        
        
        delta_t=AFloatText(
                        value=self.__deltaT,
                        description='Δt (ms)',
                        disabled=False,
                        callback=update_deltat) 
        
        
        
        self.__experiment_react.append(save_button)
        self.__experiment_react.append(reaction_desc)
        self.__experiment_react.append(delta_t)
        self.__experiment_react.append(clear_button)
        self.__experiment_react.append(reload_button)
        return {'button':save_button,'description':reaction_desc,'delta_t':delta_t,'clear_button':clear_button,'reload_button':reload_button}
    
    def _start_reaction_widget(self):
        
        def start_reaction(b):
            
            if self.__reaction_active:
                logger.debug("Already sampling")
                return
            self.__reaction_active=True
            logger.debug("Start reaction")
            
            
            if self.__deltaT <self.__configuration.integration_time.value:
                self.__deltaT=self.__configuration.integration_time.value
                logger.debug("Measure interval < integration time")
 
            self.measure_reaction(deltat=self.__deltaT/1000.0)
   
          
            
        button=AButton(description='Start reaction',
                           disabled=True,
                           tooltip='Start reaction absorbance measurement',
                           icon='play',
                           callback=start_reaction)
        
        self.__experiment_react.append(button)
        return {'button':button}
    
    def _stop_reaction_widget(self):
        def stop_reaction(b):
            with self.graph_output:
                self.graph_output.clear_output(wait=True)
                display(self.graphs['figure'])
            
            logger.debug("Stop reaction")
            if self.__reaction_active:
                self.__reaction_active=False
            else:
                logger.debug("Not sampling")
            
            
            
            
        button=AButton(description='Stop reaction',
                       disabled=True,
                       tooltip='Stop reaction absorbance measurement',
                       icon='stop',
                       callback=stop_reaction)
        
        self.__experiment_react.append(button)
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
            
            self.__experiment_mol.append(button)
            return {'button':button,'data':molarity}

    def _reaction_graph(self):
             
        with self.graph_output:
            
            
            with plt.ioff():
                regfigure,ax= plt.subplots(figsize=[30,15])
                
            
            regscatter, = ax.plot([], [], 'bo', label='Time vs Absorbance')
            ax.axes.get_xaxis().set_visible(False)
            #setup reg lines and plot intervals
            ax.legend()
            ax.set_title('Time vs Absorbance ')
            ax.grid(axis='both')
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Absorbance')
            regfigure.set_visible(False)
        
        return {'figure':regfigure,'axis':ax,'scatter':regscatter}

    def show_graph(self):
        self.graphs['figure'].set_visible(True)
        self.graph_output.clear_output(wait=True)
        self.graphs['axis'].axes.get_xaxis().set_visible(True)
        with self.graph_output:
                  display(self.graphs['figure'])

    def update(self):
        for widget in self.__experiment_mol:
            if self.__configuration.photometer.is_calibrated:
                widget.disabled=False
            else:
                widget.disabled=True

        for widget in self.__experiment_react:
            if self.__configuration.photometer.zil>0:
                widget.disabled=False
            else:
                widget.disabled=True    

    
    def render_interface(self):
        
        start_reaction=self._start_reaction_widget()
        stop_reaction=self._stop_reaction_widget()
        save_reaction=self._save_reaction_widget()
        measure=self._measure_widget()
        absorbance_measure=widgets.HBox([measure['button'],measure['data']])
        reaction_commands=widgets.HBox([start_reaction['button'],stop_reaction['button'],save_reaction['button'],
                                        save_reaction['clear_button'],
                                        save_reaction['description'],
                                        save_reaction['delta_t'],self.__reaction_samples,save_reaction['reload_button']])
        reaction=widgets.VBox([reaction_commands,self.graph_output])
        graph = widgets.Accordion(children=[absorbance_measure,reaction], titles=('Molarity measure','Reaction absorbance',))
        
        return graph