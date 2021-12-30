import numpy as np
from scan_1D import script_core as linear_scan
from TheSetup import TheSetup
import pandas
from pathlib import Path
from data_processing_bureaucrat.Bureaucrat import Bureaucrat # https://github.com/SengerM/data_processing_bureaucrat
import tct_scripts_config
from grafica.plotly_utils.utils import line as grafica_line

STEP_SIZE = 22e-6
SWEEP_LENGTH = 8e-3/5
CHANNEL = 2

the_setup = TheSetup(
	temperature_controller_Pyro_uri = tct_scripts_config.TEMPERATURE_CONTROLLER_URI,
)

with open(tct_scripts_config.CURRENT_DETECTOR_CENTER_FILE_PATH, 'r') as ifile:
	center = {}
	for line in ifile:
		center[line.split('=')[0].replace(' ','')] = float(line.split('=')[-1])
center = tuple([center[k] for k in sorted(center.keys())]) # Sorted x y z
print(f'Current position is {the_setup.position}.')
position_where_to_scan_z = np.array(center) + 55e-6*np.array((1,-1,0))/2**.5 + 22e-6/2**.5*np.array((1,1,0))
print(f'Will move to {position_where_to_scan_z}.')
the_setup.move_to(*position_where_to_scan_z)

current_position = the_setup.position

z_positions = np.linspace(-SWEEP_LENGTH/2,SWEEP_LENGTH/2,int(SWEEP_LENGTH/STEP_SIZE)) + current_position[2]
x_positions = z_positions*0 + current_position[0]
y_positions = z_positions*0 + current_position[1]

measurement_base_path = linear_scan(
	measurement_name = input('Measurement name? ').replace(' ', '_'),
	the_setup = the_setup,
	bias_voltage = 333,
	laser_DAC = 573,
	positions = list(zip(x_positions,y_positions,z_positions)),
	n_triggers = 33,
	acquire_channels = [CHANNEL],
)

bureaucrat = Bureaucrat(
	str(Path(measurement_base_path)),
	variables = locals(),
	new_measurement = False,
)

data_df = pandas.read_feather(bureaucrat.processed_by_script_dir_path('scan_1D.py')/Path('measured_data.fd'))

mean_df = data_df.groupby(by=['n_position','n_channel','n_pulse']).agg(['mean','std'])
mean_df.columns = [' '.join(col).strip() for col in mean_df.columns.values]
mean_df.reset_index(inplace=True)
fig = grafica_line(
	title = f'Collected charge vs z<br><sup>Measurement: {bureaucrat.measurement_name}</sup>',
	data_frame = mean_df,
	x = 'z (m) mean',
	y = 'Collected charge (V s) mean',
	error_y = 'Collected charge (V s) std',
	error_y_mode = 'band',
	symbol = 'n_pulse',
	color = 'n_channel',
)
fig.write_html(str(bureaucrat.processed_data_dir_path/Path('collected_charge_vs_z.html')), include_plotlyjs='cdn')
