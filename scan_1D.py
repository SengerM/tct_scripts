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
from parse_waveforms_from_scan import script_core as parse_waveforms
from plotting_scripts.plot_everything_from_1D_scan import script_core as plot_measurement

def post_process(measurement_base_path: Path):
	print(f'Launching post-processing of {measurement_base_path.parts[-1]}...')
	parse_waveforms(measurement_base_path, silent=True)
	plot_measurement(measurement_base_path)
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
		str(tct_scripts_config.DATA_STORAGE_DIRECTORY_PATH/Path(measurement_name)),
		variables = locals(),
		new_measurement = True,
	)
	DIRECTORY_TO_STORE_WAVEFORMS = Raúl.processed_data_dir_path/Path('measured_waveforms')
	DIRECTORY_TO_STORE_WAVEFORMS.mkdir(parents=True, exist_ok=True)
	
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
					if len(waveforms_df.index) > 1e6:
						waveforms_df.reset_index().to_feather(DIRECTORY_TO_STORE_WAVEFORMS/Path(datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')+'.fd'))
						waveforms_df = pandas.DataFrame()
					reporter.update(1)
		# Save remaining data ---
		waveforms_df.reset_index().to_feather(DIRECTORY_TO_STORE_WAVEFORMS/Path(datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')+'.fd'))
		
		return Raúl.measurement_base_path

########################################################################

# The following things are defined here such that they can be imported from other scripts.

DEVICE_CENTER = {
	# The values here are those shown in the graphic interface.
	'x': -3.7927343749999998e-3, 
	'y': 0.4559765625e-3, 
	'z': 71.41471e-3
}
SCAN_STEP = 11e-6 # meters
SCAN_LENGTH = 380e-6 # meters
SCAN_ANGLE_DEG = 45 # deg

if __name__ == '__main__':
	import numpy as np
	
	x = DEVICE_CENTER['x'] + np.arange(-SCAN_LENGTH/2,SCAN_LENGTH/2, STEP)*np.cos(SCAN_ANGLE_DEG*np.pi/180)
	y = DEVICE_CENTER['y'] + np.arange(-SCAN_LENGTH/2,SCAN_LENGTH/2, STEP)*np.sin(SCAN_ANGLE_DEG*np.pi/180)
	z = CENTER['z'] + 0*x
	positions = []
	for i in range(len(y)):
		positions.append( [ x[i],y[i],z[i] ] )
	
	measurement_base_path = script_core(
		measurement_name = input('Measurement name? ').replace(' ', '_'),
		the_setup = TheSetup(),
		bias_voltage = 111,
		laser_DAC = 630,
		positions = positions,
		n_triggers = 55,
		acquire_channels = [1,2],
	)
	post_process(measurement_base_path)
