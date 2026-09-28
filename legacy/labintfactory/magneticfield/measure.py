from labintfactory.setup import instrument_configuration
import ipywidgets as widgets # type: ignore
from IPython.display import display
from labintfactory.utils.interface_widgets import AButton,ADropdown
import matplotlib.pyplot as plt
import time
from loguru import logger


logger.disable(__name__)


class MeasureWidget:
    def __init__(self,configuration):
              
        self.__subwidgets=[]
        self.__linear_actuator=configuration.linear_actuator
        self.__hall_sensor=configuration.hall_sensor
        self.__configuration=configuration
        self.__graph_output=widgets.Output(layout={'border': '2px solid black'})
        self.__graphs=self._magnetic_field_graph()
        self.__step_size=0.1
        self.__magnetic_field=[]
        self.__component='z'

        
    @property
    def graphs(self):
        return self.__graphs
    
    @property
    def magnetic_field(self):
        return self.__magnetic_field
    
    
    @property
    def graph_output(self):
        return self.__graph_output
    
    
    def _magnetic_field_graph(self):
        components_graphs={'x':[], 'y':[],'z':[]}    
             
        with self.graph_output:
            with plt.ioff():
                for component in components_graphs:
                    regfigure,ax= plt.subplots(figsize=[30,15])
                    components_graphs[component]=[regfigure,ax]
            
            for component in components_graphs:
                regfigure,ax=components_graphs[component]
                regscatter, = ax.plot([], [], 'bo', label=f'Magnetic field {component} ')
                components_graphs[component].append(regscatter)
                regfigure.set_visible(False)
                ax.axes.get_xaxis().set_visible(False)
                #setup reg lines and plot intervals
                ax.legend()
                ax.set_title(f"Position vs Magnetic field {component}")
                ax.grid(axis='both')
                ax.set_xlabel('Position (mm)')
                ax.set_ylabel('Magnetic field (mT)')
                regfigure.set_visible(False)
        
            
        
        return components_graphs
    
   
    def measure_interface(self):
        def set_step_size(e):
            self.__step_size=float(e.new)
            
        def set_component(e):
            self.__component=e.new
        
        def start_data_collection(e):
            
            self.__magnetic_field=[]
            
            
            if instrument_configuration.has('linear_actuator'):
                
                if instrument_configuration.device['linear_actuator'].get('range_start')<instrument_configuration.device['linear_actuator'].get('range_stop'):
                    self.__linear_actuator.move_to_position( instrument_configuration.device['linear_actuator'].get('range_start'))
                    steps=int((instrument_configuration.device['linear_actuator'].get('range_stop')-instrument_configuration.device['linear_actuator'].get('range_start') ) /self.__step_size  )
                    for i in range(steps):
                        position=instrument_configuration.device['linear_actuator'].get('range_start')+self.__step_size*i
                        self.__linear_actuator.move_to_position( position)
                        readings=self.__hall_sensor.read(instrument_configuration.device['hall_sensor'].get('measure_interval'),
                                                       instrument_configuration.device['hall_sensor'].get('samples'))
                        
                        print([position]+readings)
                        
                        self.__magnetic_field.append([position]+readings)
                        
                        self.plot()
                        
                        time.sleep(0.2)
            
        
        interface={}
        
        interface['component']=ADropdown(options=['x','y','z'],
                            description='Field component',
                            value='z',
                            disabled=False,
                            style='large',
                            callback=set_component   )
        
        interface['resolution']=ADropdown(options=[0.01*pow(10,i) for i in range(4) ],
                            description='Step size',
                            disabled=False,
                            style='large',
                            callback=set_step_size)
        interface['start']=AButton(description='Start',style='large',callback=start_data_collection,disabled=False)
        
        return interface
    
    def plot(self):
        components={'x':1,'y':2,'z':3}
        positions=[magnetic_field[0] for magnetic_field in self.magnetic_field]
        for component in components:
            
            
            field_component=[magnetic_field[components[component]] for magnetic_field in self.magnetic_field]
            
            ax=self.graphs[component][1]
            ax.set_xlim(min(positions), max(positions))
            
            ax.set_ylim(1.2*min(field_component),1.2*max(field_component))
            
            self.graphs[component][2].set_data(positions,field_component)
            self.graph_output.clear_output(wait=True)
            with self.graph_output:
                self.graph_output.clear_output(wait=True)
                display(self.graphs[component][0])
            
            
        return True
    
    def show_graph(self):
        for component in self.graphs:
            figure,axis,scatter=self.graphs[component]
            figure.set_visible(True)
            self.graph_output.clear_output(wait=True)
            axis.axes.get_xaxis().set_visible(True)
            with self.graph_output:
                    display(figure)

                
    def update(self):
        pass
        
    def render_interface(self):
        exp_interface=self.measure_interface()
        commands=widgets.HBox([exp_interface['start'],exp_interface['resolution'],exp_interface['component']])
        graph=widgets.Accordion(children=[self.graph_output], titles=('X Component',))
        field=widgets.VBox([commands,graph])
        
        return field