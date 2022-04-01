import numpy as np
from time import sleep
from signals.PeakSignal import PeakSignal, draw_in_plotly # https://github.com/SengerM/signals
from bureaucrat.Bureaucrat import Bureaucrat # https://github.com/SengerM/bureaucrat
from progressreporting.TelegramProgressReporter import TelegramReporter # https://github.com/SengerM/progressreporting
import my_telegram_bots
from pathlib import Path
from plotting_scripts.plot_everything_from_1D_scan import script_core as plot_everything_from_1D_scan
import pandas
import datetime
import utils
import tct_scripts_config
import plotly.graph_objects as go

TIMES_AT = [10,20,30,40,50,60,70,80,90]

def draw_times_at(fig, signal):
	MARKERS = { # https://plotly.com/python/marker-style/#custom-marker-symbols
		10: 'circle',
		20: 'square',
		30: 'diamond',
		40: 'cross',
		50: 'x',
		60: 'star',
		70: 'hexagram',
		80: 'star-triangle-up',
		90: 'star-triangle-down',
	}
	for pp in TIMES_AT:
		try:
			fig.add_trace(
				go.Scatter(
					x = [signal.find_time_at_rising_edge(pp)], 
					y = [signal(signal.find_time_at_rising_edge(pp))],
					mode = 'markers',
					name = f'Time at {pp} %',
					marker=dict(
						color = 'rgba(0,0,0,.5)',
						size = 11,
						symbol = MARKERS[pp]+'-open-dot',
						line = dict(
							color = 'rgba(0,0,0,.5)',
							width = 2,
						)
					),
				)
			)
		except KeyboardInterrupt:
			raise KeyboardInterrupt
		except:
			pass

def script_core(
		measurement_name: str, 
		bias_voltage: float,
		laser_DAC: float,
		positions: list, # This is a list of iterables with 3 floats, each element of the form (x,y,z).
		the_setup,
		n_triggers: int = 1,
		acquire_channels = [1,2,3,4],
		two_pulses = True,
		external_Telegram_reporter=None,
	):
	bureaucrat = Bureaucrat(
		str(tct_scripts_config.DATA_STORAGE_DIRECTORY_PATH/Path(measurement_name)),
		variables = locals(),
		new_measurement = True,
	)
	PLOTS_DIR_PATH = bureaucrat.processed_data_dir_path/Path('some_random_processed_signals_plots')
	PLOTS_DIR_PATH.mkdir(parents=True, exist_ok=True)
	
	with bureaucrat.verify_no_errors_context():
		if two_pulses:
			the_setup.configure_oscilloscope_for_two_pulses()
		
		print('Configuring laser...')
		the_setup.laser_DAC = laser_DAC
		the_setup.laser_status = 'on'
		
		print('Setting bias voltage...')
		the_setup.bias_voltage = bias_voltage
		the_setup.bias_output_status = 'on'
		
		data_frame_columns = ['n_position','n_trigger','n_channel','n_pulse']
		data_frame_columns += ['x (m)','y (m)','z (m)','When','Bias voltage (V)','Bias current (A)','Laser DAC','Temperature (°C)','Humidity (%RH)']
		data_frame_columns += ['Amplitude (V)','Noise (V)','Rise time (s)','Collected charge (V s)','Time over noise (s)']
		for pp in TIMES_AT:
			data_frame_columns += [f't_{pp} (s)']
		measured_data_df = pandas.DataFrame(columns = data_frame_columns)
		
		reporter = TelegramReporter(
			telegram_token = my_telegram_bots.robobot.token, 
			telegram_chat_id = my_telegram_bots.chat_ids['Robobot TCT setup'],
		)
		
		with reporter.report_for_loop(len(positions)*n_triggers, f'{bureaucrat.measurement_name}') as reporter:
			for n_position, target_position in enumerate(positions):
				the_setup.move_to(*target_position)
				sleep(0.1)
				position = the_setup.position
				for n_trigger in range(n_triggers):
					plot_this_trigger = np.random.rand() < 20/(len(positions)*n_triggers)
					print(f'Measuring: n_position={n_position}/{len(positions)-1}, n_trigger={n_trigger}/{n_triggers-1}...')
					# Acquire data for this trigger --------------------
					utils.wait_for_nice_trigger_without_EMI(the_setup, acquire_channels)
					this_trigger_signals_df = pandas.DataFrame()
					for n_channel in acquire_channels:
						try:
							raw_data = the_setup.get_waveform(channel = n_channel)
						except Exception as e:
							print(f'Cannot get data from oscilloscope, reason: {e}')
						raw_data_each_pulse = {}
						if not two_pulses:
							raw_data_each_pulse[1] = raw_data
						else:
							for n_pulse in [1,2]:
								raw_data_each_pulse[n_pulse] = {}
								for variable in ['Time (s)','Amplitude (V)']:
									if n_pulse == 1:
										raw_data_each_pulse[n_pulse][variable] = raw_data[variable][:int(len(raw_data[variable])/2)]
									if n_pulse == 2:
										raw_data_each_pulse[n_pulse][variable] = raw_data[variable][int(len(raw_data[variable])/2):]
								this_trigger_signals_df = this_trigger_signals_df.append(
									{
										'n_channel': n_channel,
										'n_pulse': n_pulse,
										'signal': PeakSignal(
											time = raw_data_each_pulse[n_pulse]['Time (s)'],
											samples = raw_data_each_pulse[n_pulse]['Amplitude (V)'],
										)
									},
									ignore_index = True,
								)
					this_trigger_signals_df = this_trigger_signals_df.astype({'n_channel': int, 'n_pulse': int})
					this_trigger_signals_df = this_trigger_signals_df.set_index(['n_channel','n_pulse'])
					# Process data for this trigger --------------------
					for n_channel,n_pulse in this_trigger_signals_df.index:
						signal = this_trigger_signals_df.loc[(n_channel,n_pulse),'signal']
						# Because measuring bias voltage and current takes a long time, I do the following ---
						measure_bias_IV_in_this_iteration = False
						if 'last_time_bias_IV_was_measured' not in locals() or (datetime.datetime.now()-last_time_bias_IV_was_measured).seconds >= 11:
							measure_bias_IV_in_this_iteration = True
							last_time_bias_IV_was_measured = datetime.datetime.now()
						measured_data_dict = {
							'n_position': n_position,
							'n_trigger': n_trigger,
							'n_channel': n_channel,
							'n_pulse': n_pulse,
							'x (m)': position[0],
							'y (m)': position[1],
							'z (m)': position[2],
							'When': datetime.datetime.now(),
							'Bias voltage (V)': the_setup.bias_voltage if measure_bias_IV_in_this_iteration else float('NaN'),
							'Bias current (A)': the_setup.bias_current if measure_bias_IV_in_this_iteration else float('NaN'),
							'Laser DAC': the_setup.laser_DAC,
							'Temperature (°C)': the_setup.temperature,
							'Humidity (%RH)': the_setup.humidity,
							'Amplitude (V)': signal.amplitude,
							'Noise (V)': signal.noise,
							'Rise time (s)': signal.rise_time,
							'Collected charge (V s)': signal.peak_integral,
							'Time over noise (s)': signal.time_over_noise,
						}
						for pp in TIMES_AT:
							try:
								_time = signal.find_time_at_rising_edge(pp)
							except KeyboardInterrupt:
								raise KeyboardInterrupt
							except Exception as e:
								_time = float('NaN')
							measured_data_dict[f't_{pp} (s)'] = _time
						measured_data_df = measured_data_df.append(measured_data_dict, ignore_index = True)
						
						# Save data and do some plots ------------------
					if 'last_time_data_was_saved' not in locals() or (datetime.datetime.now()-last_time_data_was_saved).seconds >= 60*5:
						measured_data_df.reset_index().to_feather(bureaucrat.processed_data_dir_path/Path('measured_data.fd'))
						last_time_data_was_saved = datetime.datetime.now()
					if plot_this_trigger:
						for n_channel,n_pulse in this_trigger_signals_df.index:
							signal = this_trigger_signals_df.loc[(n_channel,n_pulse),'signal']
							fig = draw_in_plotly(signal)
							plot_name = f'n_position {n_position} n_trigger {n_trigger} n_channel {n_channel} n_pulse {n_pulse}'
							fig.update_layout(
								title = f'Signal {plot_name} <br><sup>Measurement: {bureaucrat.measurement_name}</sup>',
								xaxis_title = 'Time (s)',
								yaxis_title = 'Amplitude (V)',
							)
							draw_times_at(fig, signal)
							fig.write_html(
								str(PLOTS_DIR_PATH/Path(f'{plot_name}.html')),
								include_plotlyjs = 'cdn',
							)
					reporter.update(1)
					try:
						external_Telegram_reporter.update(1)
					except:
						pass
		# Save remaining data ---
		print('Finished measuring! :)')
		print('Saving data...')
		measured_data_df.reset_index().to_feather(bureaucrat.processed_data_dir_path/Path('measured_data.fd'))
		print('Doing plots...')
		plot_everything_from_1D_scan(directory = bureaucrat.measurement_base_path)
		print('Finished plotting!')
		
		return bureaucrat.measurement_base_path

########################################################################

if __name__ == '__main__':
	from TheSetup import TheSetup
	
	CENTER = {'x': -5.21759765625e-3, 'y': 0.992265625e-3, 'z': 71.41140625e-3}
	
	STEP = 1e-6 # meters
	SCAN_LENGTH = 250e-6 # meters
	
	x = np.arange(CENTER['x'] - SCAN_LENGTH/2, CENTER['x'] + SCAN_LENGTH/2, STEP)
	y = CENTER['y'] + 0*x
	z = CENTER['z'] + 0*x
	positions = []
	for i in range(len(y)):
		positions.append( [ x[i],y[i],z[i] ] )
	
	script_core(
		measurement_name = input('Measurement name? ').replace(' ', '_'),
		the_setup = TheSetup(),
		bias_voltage = 530,
		laser_DAC = 630,
		positions = positions,
		n_triggers = 333,
		acquire_channels = [1,2],
		two_pulses = True,
	)

