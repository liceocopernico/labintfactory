import ipywidgets as widgets
import ipysheet
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
import numpy as np
import json
import datetime
import codecs


class CalibrationWidget:
    def __init__(self,configuration):
        self.__subwidgets=[]
        self.__data_sheet_dim=(10,4)
        self.__photometer=configuration.photometer
        self.__graph_output=widgets.Output(layout={'border': '2px solid black'})
        self.__zeroth_illuminance=self._zeroth_illuminance_widget()
        self.__graphs=self._absorbance_graph()
        self.__data_sheet=self._data_sheet_widget()
        self.__configuration=configuration
        self.__save_load_dialog=self._sl_calibration_widget()
          
        
    @property
    def samples(self):
        return self.__configuration.samples

    @property
    def integration_time(self):
        return self.__configuration.integration_time
    
    @property
    def photometer(self):
        return self.__photometer
    
    @property
    def graphs(self):
        return self.__graphs
    
    @property
    def data_sheet(self):
        return self.__data_sheet    
    
    @property
    def graph_output(self):
        return self.__graph_output
    
    @property 
    def zeroth_illuminance(self):
        return self.__zeroth_illuminance     

    def get_reg_coeff(self):
        
        #molarity and illuminance

        cells_data=self.data_sheet['cells_data']
        molarity_data=[measure[0] for measure in cells_data if measure[0]>0]
        absorbance_data=[measure[3] for measure in cells_data if measure[1]>0 ]
        #create  slice objects
        regd1=slice(0,len(molarity_data))

        current_fig=self.graphs['figure']
        ax=self.graphs['axis']
           
        #do the linear reg
        reg1 = LinearRegression()
        x_train1 = np.array(molarity_data[regd1]).reshape(-1, 1)
        y_train1 = np.array(absorbance_data[regd1]).reshape(-1, 1)
        reg1.fit(x_train1,y_train1)
        
        #collect results
        lines_data=[reg1.coef_[0][0],reg1.intercept_[0]]
        self.photometer.calibration_data=lines_data
        
        print(lines_data)
        
        #plot data
               
        ax.set_xlim(min(molarity_data), max(molarity_data)+1)
        ax.set_ylim(min(absorbance_data),max(absorbance_data)+1)
        self.graphs['scatter'].set_data(molarity_data,absorbance_data)
        self.graphs['line'].set_data(molarity_data, reg1.predict(np.array([entry for entry in molarity_data]).reshape(-1, 1)))
        with self.graph_output:
                    self.graph_output.clear_output(wait=True)
                    display(self.graphs['figure'])
        return lines_data

    def _zeroth_illuminance_widget(self):
            def get_reading(b):
                light=self.photometer.get_light_reading(n_samples=self.samples.value,int_time=self.integration_time.value)
                illuminance.value=light[0]
                self.photometer.zil=illuminance.value
                
            measure_button = widgets.Button(
                description='Get zeroth illuminance',
                disabled=True,
                button_style='', 
                tooltip='Get illuminance reading at solute zero molarity',
                icon='sun'
            )
                       
            illuminance=widgets.FloatText(
                    value=0.0,
                    description='Illuminance (Lux):',
                    disabled=True
                )
            illuminance.style.description_width='150px'
            measure_button.on_click(get_reading)
            self.__subwidgets.append(measure_button)
            return {'button':measure_button,'value':illuminance}


        
    def _data_sheet_widget(self):
        
        n_rows,n_columns=self.__data_sheet_dim
        
        def measure_light(change):

                if not cells[change.owner.row_start][change.owner.column_start].read_only:    
                    illuminance=self.photometer.get_light_reading(n_samples=self.samples.value,int_time=self.integration_time.value)[0]
                    
                    cells[change.owner.row_start][change.owner.column_start+1].value=illuminance
                    cells[change.owner.row_start][change.owner.column_start+2].value=self.photometer.transmittance()
                    cells[change.owner.row_start][change.owner.column_start+3].value=self.photometer.absorbance()
                    for k in range(n_columns):
                        cells_data[change.owner.row_start][k]=cells[change.owner.row_start][k].value
                    self.get_reg_coeff()    
        data_sheet=ipysheet.sheet(rows=n_rows,
                                  columns=n_columns, 
                                  column_headers=["Molarity (mol/L)","Illuminance (Lux)", "Transmittance", "Absorbance"],
                                  row_headers=False,
                                  )
        cells=[[ipysheet.cell(i,j,value=0.0,read_only=True) for j in range(n_columns)] for i in range(n_rows)]
        cells_data=[[cells[i][j].value for j in range(n_columns)] for i in range(n_rows)]
        
        for i in range(n_rows):
            cells[i][0].observe(measure_light, 'value')
            
        self.__subwidgets.append(data_sheet)
            
        return {'widget':data_sheet,'cells_data':cells_data,'cells':cells,'callback':measure_light}

    def _save_calibration(self,e=None):
        calibration_data={'measures':self.data_sheet['cells_data'],
                          'zil':self.photometer.zil,
                          'led_power':self.__configuration.power.value,
                          'calibration_curve':self.photometer.calibration_data,
                          'led_color':self.__configuration.leds['widget'].value}
        json_str = json.dumps(calibration_data, indent=4)
        with open(f"calibration_{datetime.datetime.now()}.json", "w") as f:
                f.write(json_str)

    def _clear_calibration(self):
        n_rows,n_columns=self.__data_sheet_dim
        for i in range(n_rows):
            for j in range(n_columns):
                state=self.data_sheet['cells'][i][j].read_only
                self.data_sheet['cells'][i][j].read_only=True
                self.data_sheet['cells'][i][j].value=0.0
                self.data_sheet['cells_data'][i][j]=0.0
                self.data_sheet['cells'][i][j].read_only=state
            
    def _load_calibration(self,e=None):
        self._clear_calibration()
        n_rows,n_columns=self.__data_sheet_dim
        data=e.new[0].content
        text_data=codecs.decode(data, encoding="utf-8")
        loaded_calibration=json.loads(text_data)
        self.__configuration.power.value=loaded_calibration['led_power']
        self.photometer.set_led_power(loaded_calibration['led_power'])
        
        self.photometer.zil=loaded_calibration['zil']
        self.photometer.calibration_data=loaded_calibration['calibration_curve']
        self.__configuration.leds['widget'].value=loaded_calibration['led_color']
        self.__zeroth_illuminance['value'].value=loaded_calibration['zil']

        
        for i in range(n_rows):
            for j in range(n_columns):
                self.data_sheet['cells_data'][i][j]=loaded_calibration['measures'][i][j]
                self.data_sheet['cells'][i][j].read_only=True
                self.data_sheet['cells'][i][j].value=self.data_sheet['cells_data'][i][j]
                self.data_sheet['cells'][i][j].read_only=False
        self.get_reg_coeff()
      
        
    def _sl_calibration_widget(self):
            save_button = widgets.Button(
                description='Save calibration',
                disabled=False,
                button_style='', 
                tooltip='Save calibration in json format',
                icon='save'
            )

            load_button=widgets.FileUpload(
                    accept='*.json',  
                    multiple=False,
                    description="Load calibration"
                )
                   
            save_button.on_click(self._save_calibration)
            load_button.observe(self._load_calibration, names='value')
            self.__subwidgets.append(save_button)
            self.__subwidgets.append(load_button)
            return {'save_button':save_button, 'load_button':load_button}
        
    
    def _absorbance_graph(self):
             
        with self.graph_output:
            regfigure,ax= plt.subplots(figsize=[30,15])
            regscatter, = ax.plot([], [], 'bo', label='Molarity vs Absorbance')
            ax.axes.get_xaxis().set_visible(False)
            #setup reg lines and plot intervals
            regline1, = ax.plot([], [], 'r', label='Absorbance calibration curve')
            ax.legend()
            ax.set_title('Photometer calibration curve')
            ax.grid(axis='both')
            ax.set_xlabel('Molarity (mol/L)')
            ax.set_ylabel('Absorbance')
            regfigure.set_visible(False)
        
        return {'figure':regfigure,'axis':ax,'scatter':regscatter,'line':regline1}

    def enable(self):
        for cell_row in self.data_sheet['cells']:
            for cell in cell_row:
                cell.read_only=False
        for widget in self.__subwidgets:
            widget.disabled=False
            
    def disable(self):
        for cell_row in self.data_sheet['cells']:
            for cell in cell_row:
                cell.read_only=True
        
        for widget in self.__subwidgets:
            widget.disabled=True

    def show_graph(self):
        self.graphs['figure'].set_visible(True)
        self.graph_output.clear_output(wait=True)
        self.graphs['axis'].axes.get_xaxis().set_visible(True)
        with self.graph_output:
                  display(self.graphs['figure'])
    
    def render_interface(self):
        calibration1=widgets.HBox([self.zeroth_illuminance['button'],
                                   self.zeroth_illuminance['value'],
                                   self.__save_load_dialog['save_button'],
                                   self.__save_load_dialog['load_button']])
        calibration2=widgets.VBox([self.data_sheet['widget'],self.graph_output])
        return widgets.VBox([calibration1,calibration2])