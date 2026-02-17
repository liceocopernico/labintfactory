import ipywidgets as widgets



class AIntSlider(widgets.IntSlider):
    def __init__(self,*,value,min_value,max_value,step=1,description='',style='default',callback=None,disabled=False):
        super().__init__(value=value,
                        min=min_value,
                        max=max_value,
                        step=step,
                        description=description,
                        disabled=disabled,
                        continuous_update=False,
                        orientation='horizontal',
                        readout=True,
                        readout_format='d',
                        layout=widgets.Layout(width='75%'))

        match style:
            case 'default':
                self.layout=widgets.Layout(width='50%')
                self.style=dict(font_weight='bold',
                                 text_color='black',
                                 description_width='150px')
            case 'large':
                self.layout=widgets.Layout(width='75%')
                self.style=dict(font_weight='bold',
                                 text_color='white',
                                 description_width='150px')
    
        if callback:
            self.observe(callback, names='value')
        
    def update(self):
            pass


class AFloatSlider(widgets.FloatSlider):
    def __init__(self,*,value,min,max,step=0.1,description='',style='default',callback=None,disabled=False,setup_callback=None):
        super().__init__(value=value,
                        min=min,
                        max=max,
                        step=step,
                        description=description,
                        disabled=disabled,
                        continuous_update=False,
                        orientation='horizontal',
                        readout=True,
                        readout_format='.1f',
                        layout=widgets.Layout(width='75%'))
        self.setup_callback=setup_callback

        match style:
            case 'default':
                self.layout=widgets.Layout(width='50%')
                self.style=dict(font_weight='bold',
                                 text_color='black',
                                 description_width='150px')
            case 'large':
                self.layout=widgets.Layout(width='75%')
                self.style=dict(font_weight='bold',
                                 text_color='white',
                                 description_width='150px')
    
        if callback:
            self.observe(callback, names='value')
        
    def update(self):
            if self.setup_callback:
                self.setup_callback()





class AButton(widgets.Button):
    def __init__(self,*,description,style='default',tooltip='',icon='plug',callback=None,disabled=True):
        super().__init__(description=description,
                         disabled=disabled,
                         button_style='', 
                         tooltip='Hall Sensor informations',
                         icon=icon)

        match style:
            case 'default':
                self.style=dict(font_weight='bold',
                                 text_color='white',)
                self.button_style='primary'
            case 'large':
                self.style=dict(font_weight='bold',
                                 text_color='white',
                                 description_width='100px')
                self.button_style='primary'
               
                
        if callback:
            self.on_click(callback)
    def update(self):
        pass

class ADropdown(widgets.Dropdown):
        
        def __init__(self,*,options=[],value=None, description='',disabled=True,style='default',callback=None,options_callback=None):
                super().__init__(options=options,
                                 description=description,
                                 disabled=disabled,
                                 value=value)
                self.__options_callback=options_callback
                match style:
                    case 'default':
                        self.style=dict(font_weight='bold',
                                        description_width='50px')
                    case 'large':
                        self.style=dict(font_weight='bold',
                                        description_width='150px')
                if options_callback:
                    self.options=options_callback()
                
                if callback:
                    self.observe(callback, names='value')

        def update(self):
            if self.__options_callback:
                self.options=self.__options_callback()

class ASelectMultiple(widgets.SelectMultiple):
    def __init__(self,*,options=[],description='',disabled=True,callback=None,options_callback=None,style='default'):
        super().__init__(options=options,
                         rows=10,
                         description=description,
                         disabled=disabled,
                         layout={'width': 'max-content'})
        
        self.__options_callback=options_callback
        match style:
                    case 'default':
                        self.style=dict(font_weight='bold',
                                        description_width='50px')
                    case 'large':
                        self.style=dict(font_weight='bold',
                                        description_width='150px')

        if options_callback:
                    self.options=options_callback()
                
        if callback:
                    self.observe(callback, names='value')

    def update(self):
            if self.__options_callback:
                self.options=self.__options_callback()