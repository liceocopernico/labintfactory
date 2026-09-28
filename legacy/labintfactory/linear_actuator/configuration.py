import ipywidgets as widgets # type: ignore
from labintfactory.utils.interface_widgets import AButton,ADropdown,ASelectMultiple,AIntSlider,AFloatSlider
from labintfactory.linear_actuator.actuator import LinearActuator
from loguru import logger
from labintfactory.setup import instrument_configuration

logger.disable(__name__)

class ConfigurationWidget:
    device_name='linear_actuator'
    
    def __init__(self,*,setup,output):
        self.__subwidgets=[]
        self.__setup=setup
        self.__output=output
        self.__linear_actuator=LinearActuator(self.__setup.microcontroller)
        self.__actions=self._actions_grid()
        self.__positioning=self._set_working_position()
        instrument_configuration.add_device(self.device_name,'actuator',['range_start','range_stop','position','max_position','motor_enabled'])
        

    @property
    def linear_actuator(self):
        return self.__linear_actuator
 

    def _set_working_position(self):
        elements={}
        def move_to_position(position):
            instrument_configuration.device[self.device_name].set('position',elements['position_slider'].value)
            self.__linear_actuator.move_to_position(elements['position_slider'].value)

        def set_limits(e=None):
            
            elements['position_slider'].max=self.__linear_actuator.max_position
            instrument_configuration.device[self.device_name].set('max_position',self.__linear_actuator.max_position)
            elements['position_slider'].value=self.__linear_actuator.position
            print(f"New limits {elements['position_slider'].value} {elements['position_slider'].max}")
                
        def set_range_start(e):
            
            
            instrument_configuration.device[self.device_name].set('range_start',elements['position_slider'].value)
            
            elements['position_slider'].min=elements['position_slider'].value

        def set_range_stop(e):
            
            instrument_configuration.device[self.device_name].set('range_stop',elements['position_slider'].value)
            elements['position_slider'].max=elements['position_slider'].value
            
            
        def reset_ranges(e):
            instrument_configuration['linear_actuator_range'].set('start',0.0)
            instrument_configuration['linear_actuator_range'].set('stop',0.0)
            elements['position_slider'].max=self.__linear_actuator.max_position
            elements['position_slider'].min=0.0
            
            
                    
        elements['position_slider']=AFloatSlider(
                                        value=0.0,
                                        min=0.0,
                                        max=10.0,
                                        step=0.1,
                                        description='Actuator position (mm):',
                                        disabled=False,
                                        style='large',
                                        setup_callback=set_limits)
        
        elements['move_button'] =  AButton(
                description='Move',
                disabled=True, 
                tooltip='Move to selected position',
                icon='luggage-cart',
                callback=move_to_position)
        
        elements['start_position']=AButton(description='Set Start',
                                           disabled=True,
                                           tooltip="Set start position",
                                           icon='flag-checkered',
                                           callback=set_range_start)
        
        elements['stop_position']=AButton(description='Set Stop',
                                           disabled=True,
                                           tooltip="Set stop position",
                                           icon='stop',
                                           callback=set_range_stop)
        
        elements['reset_ranges']=AButton(description='Reset Ranges',
                                           disabled=True,
                                           tooltip="Reset start stop ranges",
                                           icon='sliders',
                                           callback=reset_ranges)
        
        for index,element in elements.items():
            self.__subwidgets.append(elements[index])
        
        return elements
        
    
    def enable(self):
        print("Enable linear configuration interface")
        
        actuator_status=self.__linear_actuator.send_command('print_data')
        
        actuator_status=actuator_status.split("\n")
        
        actuator_status={x.split(":")[0]:x.split(":")[1] for x in actuator_status}
        
        
        print(f"Actuator {actuator_status}")
        for widget in self.__subwidgets:
            widget.update()
            widget.disabled=False

    def disable(self):
        for widget in self.__subwidgets:
            widget.disabled=True
                    
    def _actions_grid(self):

        commands={ self.__linear_actuator.commands[command]['description']:command for command in self.__linear_actuator.commands}
        
        def execute_command(p):
            command=commands[p.description]
            self.__linear_actuator.send_command(command)
        
        rows=4
        columns=3
        grid=widgets.GridspecLayout(rows,columns,width='500px')
        index=0
        for command in self.__linear_actuator.commands:
            if self.__linear_actuator.commands[command]['display']:
               
                grid[index%rows,index%columns]=AButton(description=self.__linear_actuator.commands[command]['description'],
                                                       callback=execute_command,
                                                       icon=self.__linear_actuator.commands[command]['icon'],
                                                       disabled=True)
                self.__subwidgets.append(grid[index%rows,index%columns])
                index+=1
        return grid
        
    def render_interface(self):
        
        position=widgets.VBox([self.__positioning['position_slider'],self.__positioning['move_button'],
                               self.__positioning['start_position'],self.__positioning['stop_position'],self.__positioning['reset_ranges']])
        
        actions=widgets.VBox([self.__actions])
        
        interface = widgets.Accordion(children=[position,actions], titles=('Linear movement range definition', 'Actions'))

        

        return interface

    
         