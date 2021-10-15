import numpy as np
from scan_1D import script_core as linear_scan
from TheSetup import TheSetup
import pandas
from pathlib import Path
import grafica # https://github.com/SengerM/grafica
from data_processing_bureaucrat.Bureaucrat import Bureaucrat # https://github.com/SengerM/data_processing_bureaucrat

Z_MIDDLE = 52.2e-3
STEP_SIZE = 5e-6
SWEEP_LENGTH = 8e-3/9
CHANNEL = 1

setup = TheSetup()
current_position = setup.position

z_positions = np.linspace(-SWEEP_LENGTH/2,SWEEP_LENGTH/2,int(SWEEP_LENGTH/STEP_SIZE)) + Z_MIDDLE
x_positions = z_positions*0 + current_position[0]
y_positions = z_positions*0 + current_position[1]

measurement_base_path = linear_scan(
	measurement_name = input('Measurement name? ').replace(' ', '_'),
	the_setup = setup,
	bias_voltage = 99,
	laser_DAC = 2000,
	positions = list(zip(x_positions,y_positions,z_positions)),
	n_triggers = 44,
	acquire_channels = [CHANNEL],
)

bureaucrat = Bureaucrat(
		str(Path(measurement_base_path)),
		variables = locals(),
		new_measurement = False,
	)

data_df = pandas.read_csv(bureaucrat.processed_by_script_dir_path('scan_1D.py')/Path('measured_data.csv'))
z_values = data_df.loc[data_df['n_channel']==CHANNEL, ['n_position', 'z (m)']].groupby(['n_position']).mean()['z (m)']
charge_mean = data_df.loc[data_df['n_channel']==CHANNEL, ['n_position', 'Collected charge (V s)']].groupby(['n_position']).mean()['Collected charge (V s)']
charge_std = data_df.loc[data_df['n_channel']==CHANNEL, ['n_position', 'Collected charge (V s)']].groupby(['n_position']).std()['Collected charge (V s)']

fig = grafica.new(
	title = f'Collected charge vs z',
	subtitle = f'Dataset: {bureaucrat.measurement_name}',
	xlabel = 'z (m)',
	ylabel = 'Collected charge (V s)',
)
fig.errorband(
	x = z_values,
	y = charge_mean,
	higher = charge_std,
	lower = charge_std,
	marker = '.',
)
grafica.save_unsaved(mkdir=bureaucrat.processed_data_dir_path)
