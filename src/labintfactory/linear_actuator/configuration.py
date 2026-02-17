import ipywidgets as widgets
from labintfactory.utils.interface_widgets import AButton,ADropdown,ASelectMultiple,AIntSlider,AFloatSlider
from labintfactory.linear_actuator.actuator import LinearActuator

class ConfigurationWidget:
    def __init__(self,*,setup,output):
        self.__subwidgets=[]
        self.__setup=setup
        self.__output=output
        self.__linear_actuator=LinearActuator(self.__setup.microcontroller)
        self.__actions=self._actions_grid()
        self.__positioning=self._set_working_position()


    def _set_working_position(self):
        elements={}
        def move_to_position(position):
            self.__linear_actuator.move_to_position(elements['position_slider'].value)

        def set_limits():
            
            elements['position_slider'].max=self.__linear_actuator.max_position
            elements['position_slider'].value=self.__linear_actuator.position
            print(f"New limits {elements['position_slider'].value} {elements['position_slider'].max}")
            
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
                icon='go',
                callback=move_to_position)
        
        elements['start_position']=AButton(description='Set Start',
                                           disabled=True,
                                           tooltip="
        
        for index,element in elements.items():
            self.__subwidgets.append(elements[index])
        
        return elements
        
    
    def enable(self):
        print("Enable linear configuration interface")
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
        position=widgets.VBox([self.__positioning['position_slider'],self.__positioning['move_button']])
        interface=widgets.VBox([self.__actions,position])
        return interface

    
         