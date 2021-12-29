import numpy as np
from time import sleep
import grafica # https://github.com/SengerM/grafica
from lgadtools.LGADSignal import LGADSignal # https://github.com/SengerM/lgadtools
from data_processing_bureaucrat.Bureaucrat import Bureaucrat, TelegramReportingInformation # https://github.com/SengerM/data_processing_bureaucrat
from progressreporting.TelegramProgressReporter import TelegramReporter # https://github.com/SengerM/progressreporting
from pathlib import Path
import pandas
import datetime
import utils
import tct_scripts_config
from TheSetup import TheSetup
from plotting_scripts.plot_everything_from_laser_intensity_scan import script_core as plot_everything_from_laser_intensity_scan

TIMES_AT = [10,20,30,40,50,60,70,80,90]

def script_core(
		measurement_name: str, 
		bias_voltage: float,
		laser_DAC_values: list, # List of DAC values to measure.
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
	
	if not isinstance(the_setup, TheSetup):
		raise TypeError(f'`the_setup` must be an instance of {TheSetup}, received object of type {type(the_setup)}.')
	
	if two_pulses:
		the_setup.configure_oscilloscope_for_two_pulses()
	
	print('Configuring laser...')
	the_setup.laser_status = 'on'
	
	print('Setting bias voltage...')
	the_setup.bias_voltage = bias_voltage
	the_setup.bias_output_status = 'on'
	
	data_frame_columns = ['n_DAC','n_trigger','n_channel','n_pulse']
	data_frame_columns += ['x (m)','y (m)','z (m)','When','Bias voltage (V)','Bias current (A)','Laser DAC','Temperature (°C)','Humidity (%RH)']
	data_frame_columns += ['Amplitude (V)','Noise (V)','Rise time (s)','Collected charge (V s)','Time over noise (s)']
	for pp in TIMES_AT:
		data_frame_columns += [f't_{pp} (s)']
	measured_data_df = pandas.DataFrame(columns = data_frame_columns)
	
	reporter = TelegramReporter(
		telegram_token = TelegramReportingInformation().token, 
		telegram_chat_id = TelegramReportingInformation().chat_id,
	)
	average_waveforms_df = pandas.DataFrame(columns={'n_DAC','n_channel','n_pulse','Amplitude mean (V)','Amplitude std (V)','Time (s)'})
	
	measured_data_df_dumper = utils.DataFrameDumper(bureaucrat.processed_data_dir_path/Path('measured_data.fd'), measured_data_df)
	waveforms_df_dumper = utils.DataFrameDumper(bureaucrat.processed_data_dir_path/Path('average_waveforms.fd'), average_waveforms_df)
	
	with reporter.report_for_loop(len(laser_DAC_values)*n_triggers, f'{bureaucrat.measurement_name}') as reporter:
		for n_DAC, target_DAC in enumerate(laser_DAC_values):
			the_setup.laser_DAC = int(target_DAC)
			sleep(0.1)
			position = the_setup.position
			this_position_signals_df = pandas.DataFrame(columns={'n_channel','n_pulse','Samples (V)','Time (s)'})
			for n_trigger in range(n_triggers):
				plot_this_trigger = np.random.rand() < 20/(len(laser_DAC_values)*n_triggers)
				print(f'Measuring: n_DAC={n_DAC}/{len(laser_DAC_values)-1}, n_trigger={n_trigger}/{n_triggers-1}...')
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
						signal = LGADSignal(
							time = raw_data_each_pulse[n_pulse]['Time (s)'],
							samples = raw_data_each_pulse[n_pulse]['Amplitude (V)'],
						)
						# Because measuring bias voltage and current takes a long time, I do the following ---
						measure_bias_IV_in_this_iteration = False
						if 'last_time_bias_IV_was_measured' not in locals() or (datetime.datetime.now()-last_time_bias_IV_was_measured).seconds >= 11:
							measure_bias_IV_in_this_iteration = True
							last_time_bias_IV_was_measured = datetime.datetime.now()
						measured_data_dict = {
							'n_DAC': n_DAC,
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
							'Collected charge (V s)': signal.collected_charge,
							'Time over noise (s)': signal.time_over_noise,
						}
						for pp in TIMES_AT:
							measured_data_dict[f't_{pp} (s)'] = signal.time_at_rising_edge(pp)
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
							fig = grafica.new(
								title = f'Signal at n_DAC {n_DAC} n_trigger {n_trigger} n_channel {n_channel} n_pulse {n_pulse}',
								subtitle = f'Measurement: {bureaucrat.measurement_name}',
								xlabel = 'Time (s)',
								ylabel = 'Amplitude (V)',
								plotter_name = 'plotly',
							)
							signal.plot_grafica(fig)
							for pp in TIMES_AT:
								try:
									fig.scatter(
										[signal.time_at_rising_edge(pp)],
										[signal.signal_at(signal.time_at_rising_edge(pp))],
										marker = 'x',
										linestyle = 'none',
										label = f'Time at {pp} %',
										color = (0,0,0),
									)
								except Exception as e:
									print(f'Cannot plot "times at X %", reason {e}.')
							grafica.save_unsaved(mkdir=bureaucrat.processed_data_dir_path/Path('some_random_processed_signals_plots'))
				reporter.update(1)
				try:
					external_Telegram_reporter.update(1)
				except:
					pass
			
			this_DAC_mean_df = this_position_signals_df.groupby(['n_channel','n_pulse','Time (s)']).mean()
			this_DAC_mean_df.rename(columns={'Samples (V)': 'Amplitude mean (V)'}, inplace=True)
			this_DAC_mean_df['Amplitude std (V)'] = this_position_signals_df.groupby(['n_channel','n_pulse','Time (s)']).std()['Samples (V)']
			this_DAC_mean_df['n_DAC'] = n_DAC
			this_DAC_mean_df.reset_index(inplace=True)
			this_DAC_mean_df.set_index(['n_DAC','n_channel','n_pulse'], inplace=True)
			average_waveforms_df.set_index(['n_DAC','n_channel','n_pulse'], inplace=True)
			average_waveforms_df = average_waveforms_df.append(this_DAC_mean_df)
			average_waveforms_df = average_waveforms_df.reset_index()
	# Save remaining data ---
	print('Finished measuring! :)')
	print('Merging dumped dataframes...')
	measured_data_df_dumper.end(measured_data_df)
	waveforms_df_dumper.end(average_waveforms_df)
	print('Doing plots...')
	plot_everything_from_laser_intensity_scan(directory = bureaucrat.measurement_base_path)
	print('Finished plotting!')
	
	return bureaucrat.measurement_base_path

########################################################################

if __name__ == '__main__':
	the_setup = TheSetup()
	
	center_position = utils.get_center_position_from_file()
	if center_position is not None:
		position_to_measure = np.array(center_position) + 70e-6/2**.5*np.array((1,-1,0)) # Move to the middle of the window.
		the_setup.move_to(*position_to_measure)
	
	script_core(
		measurement_name = input('Measurement name? ').replace(' ', '_'),
		the_setup = the_setup,
		bias_voltage = 99,
		laser_DAC_values = np.linspace(0,777,222),
		n_triggers = 55,
		acquire_channels = [2],
		two_pulses = True,
	)
