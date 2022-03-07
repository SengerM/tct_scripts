from data_processing_bureaucrat.Bureaucrat import Bureaucrat, TelegramReportingInformation # https://github.com/SengerM/data_processing_bureaucrat
from pathlib import Path
import tct_scripts_config
from scan_1D import script_core as scan_1D
import numpy as np
import pandas

def script_core(
	measurement_name: str, 
	bias_voltage: float,
	laser_DAC: float,
	positions: list, # This is a list of lists of iterables with 3 floats, each element of the form (x,y,z). E.g. positions = [[(0,0,0),(1,0,0)],[(0,1,0),(0,2,0)]]
	the_setup,
	n_triggers: int = 1,
	acquire_channels = [1,2,3,4],
	two_pulses = False,
):
	bureaucrat = Bureaucrat(
		str(tct_scripts_config.DATA_STORAGE_DIRECTORY_PATH/Path(measurement_name)),
		variables = locals(),
		new_measurement = True,
	)
	
	flat_list_of_positions = []
	n_position_1 = []
	n_position_2 = []
	for n1, sublist_of_positions in enumerate(positions):
		for n2, position in enumerate(sublist_of_positions):
			flat_list_of_positions.append(position)
			n_position_1.append(n1)
			n_position_2.append(n2)
	n_positions_df = pandas.DataFrame({'n_position_1': n_position_1, 'n_position_2': n_position_2})
	
	with bureaucrat.verify_no_errors_context():
		path_to_scan_1D_data = scan_1D(
			measurement_name = measurement_name, 
			bias_voltage = bias_voltage,
			laser_DAC = laser_DAC,
			positions = flat_list_of_positions,
			the_setup = the_setup,
			n_triggers = n_triggers,
			acquire_channels = acquire_channels,
			two_pulses = two_pulses,
			external_Telegram_reporter = None,
		)
		(path_to_scan_1D_data/Path('scan_1D')).rename(bureaucrat.processed_data_dir_path/Path('scan_1D'))
		path_to_scan_1D_data.rmdir()
		
		original_data_file_path = bureaucrat.processed_data_dir_path/Path('scan_1D/measured_data.fd')
		measured_data_df = pandas.read_feather(original_data_file_path)
		for col in n_positions_df.columns:
			measured_data_df[col] = n_positions_df[col]
		measured_data_df.reset_index().to_feather(bureaucrat.processed_data_dir_path/Path('measured_data.fd'))
		original_data_file_path.unlink()
		
		return bureaucrat.measurement_base_path

########################################################################

if __name__ == '__main__':
	from TheSetup import TheSetup
	
	X_MIDDLE = -3.474072265625e-3
	Y_MIDDLE = 0.172451171875e-3
	Z_FOCUS = 71.40015e-3
	STEP_SIZE = 55e-6
	SWEEP_LENGTH_X = 2*np.sin(np.pi*45/180)*130e-6 + 30e-6
	SWEEP_LENGTH_Y = SWEEP_LENGTH_X
	
	x_positions = np.linspace(-SWEEP_LENGTH_X/2,SWEEP_LENGTH_X/2,int(SWEEP_LENGTH_X/STEP_SIZE)) + X_MIDDLE
	y_positions = np.linspace(-SWEEP_LENGTH_Y/2,SWEEP_LENGTH_Y/2,int(SWEEP_LENGTH_Y/STEP_SIZE)) + Y_MIDDLE
	
	script_core(
		measurement_name = input('Measurement name? ').replace(' ', '_'),
		the_setup = TheSetup(),
		bias_voltage = 55,
		laser_DAC = 0,
		positions = [[(x,y,Z_FOCUS) for y in y_positions] for x in x_positions],
		n_triggers = 2,
		acquire_channels = [1,2],
		two_pulses = True,
	)

