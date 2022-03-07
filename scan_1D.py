import numpy as np
from time import sleep
from signals.PeakSignal import PeakSignal, draw_in_plotly # https://github.com/SengerM/signals
from data_processing_bureaucrat.Bureaucrat import Bureaucrat, TelegramReportingInformation # https://github.com/SengerM/data_processing_bureaucrat
from progressreporting.TelegramProgressReporter import TelegramReporter # https://github.com/SengerM/progressreporting
from pathlib import Path
from plotting_scripts.plot_everything_from_1D_scan import script_core as plot_everything_from_1D_scan
import pandas
import datetime
import utils
import tct_scripts_config
import plotly.graph_objects as go

TIMES_AT = [10,20,30,40,50,60,70,80,90]

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
			telegram_token = TelegramReportingInformation().token, 
			telegram_chat_id = TelegramReportingInformation().chat_id,
		)
		average_waveforms_df = pandas.DataFrame(columns={'n_position','n_channel','n_pulse','Amplitude mean (V)','Amplitude std (V)','Time (s)'})
		
		measured_data_df_dumper = utils.DataFrameDumper(bureaucrat.processed_data_dir_path/Path('measured_data.fd'), measured_data_df)
		waveforms_df_dumper = utils.DataFrameDumper(bureaucrat.processed_data_dir_path/Path('average_waveforms.fd'), average_waveforms_df)
		
		with reporter.report_for_loop(len(positions)*n_triggers, f'{bureaucrat.measurement_name}') as reporter:
			for n_position, target_position in enumerate(positions):
				the_setup.move_to(*target_position)
				sleep(0.1)
				position = the_setup.position
				this_position_signals_df = pandas.DataFrame(columns={'n_channel','n_pulse','Samples (V)','Time (s)'})
				for n_trigger in range(n_triggers):
					plot_this_trigger = np.random.rand() < 20/(len(positions)*n_triggers)
					print(f'Measuring: n_position={n_position}/{len(positions)-1}, n_trigger={n_trigger}/{n_triggers-1}...')
					utils.wait_for_nice_trigger_without_EMI(the_setup, acquire_channels)
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
						for n_pulse in raw_data_each_pulse.keys():
							signal = PeakSignal(
								time = raw_data_each_pulse[n_pulse]['Time (s)'],
								samples = -1*raw_data_each_pulse[n_pulse]['Amplitude (V)'],
							)
							# ~ fig = draw_in_plotly(signal)
							# ~ fig.write_html('deleteme.html', include_plotlyjs = 'cdn')
							# ~ input('Continue? ')
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
								except Exception as e:
									print(f'Cannot find time at rising edge for threshold {pp}, reason: {repr(e)}')
									_time = float('NaN')
								measured_data_dict[f't_{pp} (s)'] = _time
							measured_data_df = measured_data_df.append(measured_data_dict, ignore_index = True)
							
							this_position_signals_df = this_position_signals_df.append(
								pandas.DataFrame(
									{
										'n_channel': n_channel,
										'n_pulse': n_pulse,
										'Samples (V)': list(signal.samples),
										'Time (s)': list(signal.time),
									}
								),
								ignore_index = True,
							)
							# Save data and do some plots ---
							if 'last_time_data_was_saved' not in locals() or (datetime.datetime.now()-last_time_data_was_saved).seconds >= 60*5:
								measured_data_df = measured_data_df_dumper.dump_to_disk(measured_data_df)
								average_waveforms_df = waveforms_df_dumper.dump_to_disk(average_waveforms_df)
								last_time_data_was_saved = datetime.datetime.now()
							if plot_this_trigger:
								fig = draw_in_plotly(signal)
								fig.update_layout(
									title = f'Signal n_trigger {n_trigger}<br><sup>Measurement: {bureaucrat.measurement_name}</sup>',
									xaxis_title = "Time (s)",
									yaxis_title = "Amplitude (V)",
								)
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
									except Exception as e:
										print(f'Cannot plot "times at X %", reason {e}.')
								fig.write_html(str(PLOTS_DIR_PATH/Path(f'n_trigger {n_trigger}.html')))
					reporter.update(1)
					try:
						external_Telegram_reporter.update(1)
					except:
						pass
				
				this_position_mean_df = this_position_signals_df.groupby(['n_channel','n_pulse','Time (s)']).mean()
				this_position_mean_df.rename(columns={'Samples (V)': 'Amplitude mean (V)'}, inplace=True)
				this_position_mean_df['Amplitude std (V)'] = this_position_signals_df.groupby(['n_channel','n_pulse','Time (s)']).std()['Samples (V)']
				this_position_mean_df['n_position'] = n_position
				this_position_mean_df.reset_index(inplace=True)
				this_position_mean_df.set_index(['n_position','n_channel','n_pulse'], inplace=True)
				average_waveforms_df.set_index(['n_position','n_channel','n_pulse'], inplace=True)
				average_waveforms_df = average_waveforms_df.append(this_position_mean_df)
				average_waveforms_df = average_waveforms_df.reset_index()
		# Save remaining data ---
		print('Finished measuring! :)')
		print('Merging dumped dataframes...')
		measured_data_df_dumper.end(measured_data_df)
		waveforms_df_dumper.end(average_waveforms_df)
		print('Doing plots...')
		plot_everything_from_1D_scan(directory = bureaucrat.measurement_base_path)
		print('Finished plotting!')
		
		return bureaucrat.measurement_base_path

########################################################################

if __name__ == '__main__':
	from TheSetup import TheSetup
	
	STEP_SIZE = 10e-6
	SWEEP_LENGTH = 333e-6
	
	X_MIDDLE = -3.474072265625e-3
	Y_MIDDLE = 0.172451171875e-3
	Z_FOCUS = 71.40015e-3
	x_positions = X_MIDDLE + np.linspace(-SWEEP_LENGTH/2,SWEEP_LENGTH/2,int(SWEEP_LENGTH/STEP_SIZE))*np.sin(np.pi/4)
	y_positions = Y_MIDDLE - np.linspace(-SWEEP_LENGTH/2,SWEEP_LENGTH/2,int(SWEEP_LENGTH/STEP_SIZE))*np.sin(np.pi/4)
	z_positions = Z_FOCUS + x_positions*0
	
	script_core(
		measurement_name = input('Measurement name? ').replace(' ', '_'),
		the_setup = TheSetup(),
		bias_voltage = 66,
		laser_DAC = 11,
		positions = list(zip(x_positions,y_positions,z_positions)),
		n_triggers = 10,
		acquire_channels = [1,2],
		two_pulses = True,
	)

