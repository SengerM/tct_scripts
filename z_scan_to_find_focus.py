import numpy as np
from scan_1D import script_core as linear_scan, post_process
from TheSetup import TheSetup
import pandas
from pathlib import Path
from bureaucrat.Bureaucrat import Bureaucrat
import tct_scripts_config
from grafica.plotly_utils.utils import line as grafica_line

STEP_SIZE = 22e-6
SWEEP_LENGTH = 8e-3/5
Z_MIDDLE = 71.41470703125e-3

the_setup = TheSetup()

current_position = the_setup.position

z_positions = np.linspace(-SWEEP_LENGTH/2,SWEEP_LENGTH/2,int(SWEEP_LENGTH/STEP_SIZE)) + Z_MIDDLE
x_positions = z_positions*0 + current_position[0]
y_positions = z_positions*0 + current_position[1]

measurement_base_path = linear_scan(
	measurement_name = input('Measurement name? ').replace(' ', '_'),
	the_setup = the_setup,
	bias_voltage = 111,
	laser_DAC = 633,
	positions = list(zip(x_positions,y_positions,z_positions)),
	n_triggers = 2,
	acquire_channels = [2,3],
)
post_process(measurement_base_path, silent=False)

bureaucrat = Bureaucrat(
	Path(measurement_base_path),
	variables = locals(),
	new_measurement = False,
)

data_df = pandas.read_feather(bureaucrat.processed_by_script_dir_path('parse_waveforms_from_scan_1D.py')/Path('data.fd'))

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
	labels = {
		'z (m) mean': 'z (m)',
		'Collected charge (V s) mean': 'Collected charge (V s)'
	},
)
fig.write_html(str(bureaucrat.processed_data_dir_path/Path('collected_charge_vs_z.html')), include_plotlyjs='cdn')
