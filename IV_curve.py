from data_processing_bureaucrat.Bureaucrat import Bureaucrat
from pathlib import Path
from time import sleep
import pandas
from TheSetup import TheSetup
import plotly.express as px
import datetime
from utils import DataFrameDumper
from grafica.plotly_utils.utils import line

def script_core(
	directory, # Where to store the measured data. A new directory will be created.
	voltages: list, # List of float numbers specifying the voltage points to measure.
	current_compliance_amperes: float, # Compliance to set to the output, in amperes.
	n_triggers: int, # Number of measurements to do at each voltage.
	time_between_each_measurement: .5, # Minimum number of seconds between two consecutive readings.
	the_setup,
):
	bureaucrat = Bureaucrat(
		directory,
		new_measurement = True,
		variables = locals(),
	)
	
	the_setup.laser_status = 'off' # Just in case, make sure the laser is off.
	current_current_compliance = the_setup.current_compliance
	try:
		the_setup.current_compliance = current_compliance_amperes
		measured_data_df = pandas.DataFrame(columns = {'n_voltage','n_trigger','When','Bias voltage (V)','Bias current (A)'})
		measured_data_df_dumper = DataFrameDumper(
			bureaucrat.processed_data_dir_path/Path('measured_data.fd'),
			measured_data_df,
		)
		for n_voltage, v in enumerate(voltages):
			for n_trigger in range(n_triggers):
				print(f'Measuring n_voltage={n_voltage}/{len(voltages)-1} n_trigger={n_trigger}/{n_triggers-1}')
				the_setup.bias_voltage = v
				sleep(time_between_each_measurement)
				measured_data_df = measured_data_df.append(
					{
						'n_voltage': n_voltage,
						'n_trigger': n_trigger,
						'When': datetime.datetime.now(),
						'Bias voltage (V)': the_setup.bias_voltage,
						'Bias current (A)': the_setup.bias_current,
					},
					ignore_index = True,
				)
			measured_data_df = measured_data_df_dumper.dump_to_disk(measured_data_df)
		measured_data_df_dumper.end(measured_data_df)
		measured_data_df = pandas.read_feather(measured_data_df_dumper.file_path)
		mean_measured_data_df = measured_data_df.groupby(by='n_voltage').mean()
		mean_measured_data_df['Bias current std (A)'] = measured_data_df.groupby(by='n_voltage').std()['Bias current (A)']
		mean_measured_data_df['Bias current (A)'] *= -1 # So the logarithmic plot don't fails.
		mean_measured_data_df['Bias voltage (V)'] *= -1 # So the curve is in the positive quadrant.
		fig = line(
			data_frame = mean_measured_data_df,
			x = 'Bias voltage (V)',
			y = 'Bias current (A)',
			error_y = 'Bias current std (A)',
			error_y_mode = 'band',
			title = f'IV curve<br><sup>Measurement: {bureaucrat.measurement_name}</sup>',
			markers = '.',
			log_y = True,
		)
		fig.write_html(str(bureaucrat.processed_data_dir_path/Path(f'IV_curve.html')), include_plotlyjs='cdn')
	except Exception as e:
		raise e
	finally:
		the_setup.current_compliance = current_current_compliance
	
if __name__ == '__main__':
	import numpy as np
	script_core(
		directory = Path('C:/Users/tct_cms/Desktop/IV_curves')/Path(input('Measurement name? ').replace(' ','_')),
		voltages = list(np.linspace(1,111,44)) + list(np.linspace(1,111,44))[::-1],
		current_compliance_amperes = 33e-6,
		n_triggers = 11,
		time_between_each_measurement = .1,
		the_setup = TheSetup(),
	)
