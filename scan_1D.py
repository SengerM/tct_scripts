from TheSetup import TheSetup
from time import sleep
from bureaucrat.Bureaucrat import Bureaucrat # https://github.com/SengerM/bureaucrat
from progressreporting.TelegramProgressReporter import TelegramReporter # https://github.com/SengerM/progressreporting
import my_telegram_bots
from pathlib import Path
import pandas
import datetime
import utils
import tct_scripts_config
from parse_waveforms_from_scan_1D import script_core as parse_waveforms
from plotting_scripts.plot_everything_from_1D_scan import script_core as plot_measurement
import sqlite3

def post_process(measurement_base_path: Path, silent=True):
	if not silent:
		print(f'Launching post-processing of {measurement_base_path.parts[-1]}...')
	parse_waveforms(measurement_base_path, silent=silent)
	if not silent:
		print(f'Plotting {measurement_base_path.parts[-1]}...')
	plot_measurement(measurement_base_path)
	if not silent:
		print(f'Post-processing of {measurement_base_path.parts[-1]} finished!')

def script_core(
		measurement_name: str, 
		bias_voltage: float,
		laser_DAC: float,
		positions: list, # This is a list of iterables with 3 floats, each element of the form (x,y,z).
		the_setup: TheSetup,
		n_triggers: int = 1,
		acquire_channels = [1,2,3,4],
	):
	Raúl = Bureaucrat(
		tct_scripts_config.DATA_STORAGE_DIRECTORY_PATH/Path(measurement_name),
		variables = locals(),
		new_measurement = True,
	)
	
	reporter = TelegramReporter(
		telegram_token = my_telegram_bots.robobot.token, 
		telegram_chat_id = my_telegram_bots.chat_ids['Robobot TCT setup'],
	)
	
	with Raúl.verify_no_errors_context():
		print('Configuring acquisition system...')
		the_setup.configure_oscilloscope_for_two_pulses()
		
		print('Configuring laser...')
		the_setup.laser_DAC = laser_DAC
		the_setup.laser_status = 'on'
		
		print('Setting bias voltage...')
		the_setup.bias_voltage = bias_voltage
		the_setup.bias_output_status = 'on'
		
		sqlite3_connection = sqlite3.connect(Raúl.processed_data_dir_path/Path('waveforms.sqlite'))
		waveforms_df = pandas.DataFrame()
		
		with reporter.report_for_loop(len(positions)*n_triggers, f'{Raúl.measurement_name}') as reporter:
			n_waveform = 0
			for n_position, target_position in enumerate(positions):
				the_setup.move_to(*target_position)
				sleep(0.1) # Wait for any transient after moving the motors.
				position = the_setup.position
				for n_trigger in range(n_triggers):
					print(f'Measuring: n_position={n_position}/{len(positions)-1}, n_trigger={n_trigger}/{n_triggers-1}...')
					utils.wait_for_nice_trigger_without_EMI(the_setup, acquire_channels)
					for n_channel in acquire_channels:
						try:
							raw_data = the_setup.get_waveform(channel = n_channel)
						except Exception as e:
							print(f'Cannot get data from oscilloscope, reason: {e}')
							break
						raw_data_each_pulse = {}
						for n_pulse in [1,2]:
							raw_data_each_pulse[n_pulse] = {}
							for variable in ['Time (s)','Amplitude (V)']:
								if n_pulse == 1:
									raw_data_each_pulse[n_pulse][variable] = raw_data[variable][:int(len(raw_data[variable])/2)]
								if n_pulse == 2:
									raw_data_each_pulse[n_pulse][variable] = raw_data[variable][int(len(raw_data[variable])/2):]
							
							# Because measuring bias voltage and current takes a long time (don't know why), I do the following ---
							measure_slow_things_in_this_iteration = False
							if 'last_time_slow_things_were_measured' not in locals() or (datetime.datetime.now()-last_time_slow_things_were_measured).seconds >= 11:
								measure_slow_things_in_this_iteration = True
								last_time_slow_things_were_measured = datetime.datetime.now()
							
							waveforms_df = pandas.concat(
								[
									waveforms_df, # First dataframe.
									pandas.DataFrame( # Second dataframe.
										{
											'n_position': n_position,
											'n_trigger': n_trigger,
											'n_channel': n_channel,
											'n_pulse': n_pulse,
											'n_waveform': n_waveform,
											'x (m)': position[0],
											'y (m)': position[1],
											'z (m)': position[2],
											'When': datetime.datetime.now(),
											'Bias voltage (V)': the_setup.bias_voltage if measure_slow_things_in_this_iteration else float('NaN'),
											'Bias current (A)': the_setup.bias_current if measure_slow_things_in_this_iteration else float('NaN'),
											'Laser DAC': the_setup.laser_DAC,
											'Temperature (°C)': the_setup.temperature if measure_slow_things_in_this_iteration else float('NaN'),
											'Humidity (%RH)': the_setup.humidity if measure_slow_things_in_this_iteration else float('NaN'),
											'Time (s)': raw_data_each_pulse[n_pulse]['Time (s)'],
											'Amplitude (V)': raw_data_each_pulse[n_pulse]['Amplitude (V)'],
										},
									),
								],
								ignore_index = True,
							)
							n_waveform += 1
					if len(waveforms_df.index) > 1e6 or (n_position == len(positions)-1 and n_trigger == n_triggers-1):
						print(f'Saving data into database...')
						waveforms_df.to_sql('waveforms', sqlite3_connection, index=False, if_exists='append')
						waveforms_df = pandas.DataFrame()
					reporter.update(1)
		
	return Raúl.measurement_base_path

########################################################################

# The following things are defined here such that they can be imported from other scripts.

DEVICE_CENTER = {
	# The values here are those shown in the graphic interface.
	'x': -5.453974609375e-3, 
	'y': 1.0010644531250001e-3, 
	'z': 71.41140625e-3
}
SCAN_STEP = 1e-6 # meters
SCAN_LENGTH = 270e-6 # meters
SCAN_ANGLE_DEG = 0 # deg
LASER_DAC = 630
N_TRIGGERS_PER_POSITION = 333

if __name__ == '__main__':
	import numpy as np
	
	x = DEVICE_CENTER['x'] + np.arange(-SCAN_LENGTH/2,SCAN_LENGTH/2, SCAN_STEP)*np.cos(SCAN_ANGLE_DEG*np.pi/180)
	y = DEVICE_CENTER['y'] + np.arange(-SCAN_LENGTH/2,SCAN_LENGTH/2, SCAN_STEP)*np.sin(SCAN_ANGLE_DEG*np.pi/180)
	z = DEVICE_CENTER['z'] + 0*x + 0*y
	positions = []
	for i in range(len(y)):
		positions.append( [ x[i],y[i],z[i] ] )
	
	print('Connecting with the instruments...')
	the_setup = TheSetup()
	
	measurement_base_path = script_core(
		measurement_name = input('Measurement name? ').replace(' ', '_'),
		the_setup = the_setup,
		bias_voltage = 222,
		laser_DAC = LASER_DAC,
		positions = positions,
		n_triggers = N_TRIGGERS_PER_POSITION,
		acquire_channels = [1,2],
	)
	post_process(measurement_base_path, silent=False)
