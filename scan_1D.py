import numpy as np
from time import sleep
import grafica # https://github.com/SengerM/grafica
from lgadtools.LGADSignal import LGADSignal # https://github.com/SengerM/lgadtools
from data_processing_bureaucrat.Bureaucrat import Bureaucrat, TelegramReportingInformation # https://github.com/SengerM/data_processing_bureaucrat
from progressreporting.TelegramProgressReporter import TelegramReporter # https://github.com/SengerM/progressreporting
from pathlib import Path
from plotting_scripts.plot_everything_from_1D_scan import script_core as plot_everything_from_1D_scan
import datetime
import pandas

TIMES_AT = [10,20,30,40,50,60,70,80,90]

def script_core(
		measurement_name: str, 
		bias_voltage: float,
		laser_DAC: float,
		positions: list, # This is a list of iterables with 3 floats, each element of the form (x,y,z).
		the_setup,
		n_triggers: int = 1,
		acquire_channels = [1,2,3,4],
		two_pulses = False,
	):
	bureaucrat = Bureaucrat(
		str(Path(f'C:/Users/tct_cms/Desktop/TCT_measurements_data/{measurement_name}')),
		variables = locals(),
		new_measurement = True,
	)
	
	data_file_path = bureaucrat.processed_data_dir_path/Path('measured_data.fd')
	
	if two_pulses:
		the_setup.configure_oscilloscope_for_two_pulses()
	
	print('Configuring laser...')
	the_setup.laser_DAC = laser_DAC
	the_setup.laser_status = 'on'
	
	print('Setting bias voltage...')
	the_setup.bias_voltage = bias_voltage
	
	data_frame_columns = ['n_position','n_trigger','n_channel','n_pulse']
	data_frame_columns += ['x (m)','y (m)','z (m)','When','Bias voltage (V)','Bias current (A)','Laser DAC']
	data_frame_columns += ['Amplitude (V)','Noise (V)','Rise time (s)','Collected charge (V s)','Time over noise (s)']
	for pp in TIMES_AT:
		data_frame_columns += [f't_{pp} (s)']
	measured_data_df = pandas.DataFrame(columns = data_frame_columns)
	
	reporter = TelegramReporter(
		telegram_token = TelegramReportingInformation().token, 
		telegram_chat_id = TelegramReportingInformation().chat_id,
	)
	with reporter.report_for_loop(len(positions)*n_triggers, f'{bureaucrat.measurement_name}') as reporter:
		for n_position, target_position in enumerate(positions):
			the_setup.move_to(*target_position)
			sleep(0.1)
			position = the_setup.position
			for n_trigger in range(n_triggers):
				plot_this_trigger = np.random.rand() < 20/(len(positions)*n_triggers)
				print(f'Measuring: n_position={n_position}/{len(positions)-1}, n_trigger={n_trigger}/{n_triggers-1}...')
				the_setup.wait_for_trigger()
				signals = {}
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
						measure_bias_IV_in_thi_iteration = False
						if 'last_time_bias_IV_was_measured' not in locals() or (datetime.datetime.now()-last_time_bias_IV_was_measured).seconds >= 11:
							measure_bias_IV_in_thi_iteration = True
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
							'Bias voltage (V)': the_setup.bias_voltage if measure_bias_IV_in_thi_iteration else float('NaN'),
							'Bias current (A)': the_setup.bias_current if measure_bias_IV_in_thi_iteration else float('NaN'),
							'Laser DAC': the_setup.laser_DAC,
							'Amplitude (V)': signal.amplitude,
							'Noise (V)': signal.noise,
							'Rise time (s)': signal.rise_time,
							'Collected charge (V s)': signal.collected_charge,
							'Time over noise (s)': signal.time_over_noise,
						}
						for pp in TIMES_AT:
							measured_data_dict[f't_{pp} (s)'] = signal.time_at_rising_edge(pp)
						measured_data_df = measured_data_df.append(measured_data_dict, ignore_index = True)
						if 'last_time_data_was_saved' not in locals() or (datetime.datetime.now()-last_time_data_was_saved).seconds >= 30:
							measured_data_df.reset_index().to_feather(data_file_path)
							last_time_data_was_saved = datetime.datetime.now()
						if plot_this_trigger:
							fig = grafica.new(
								title = f'Signal at n_position {n_position} n_trigger {n_trigger} n_channel {n_channel} n_pulse {n_pulse}',
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
	measured_data_df.reset_index().to_feather(data_file_path)
	print('Finished measuring! :)')
	print('Doing plots...')
	plot_everything_from_1D_scan(directory = bureaucrat.measurement_base_path)
	print('Finished plotting!')
	
	return bureaucrat.measurement_base_path

########################################################################

if __name__ == '__main__':
	from TheSetup import TheSetup
	
	X_MIDDLE = -911.62e-6
	Y_MIDDLE = 9.567177734374999e-3
	Z_FOCUS = 52.32e-3
	STEP_SIZE = 5e-6
	SWEEP_LENGTH = 250e-6
	
	y_positions = np.linspace(-SWEEP_LENGTH/2,SWEEP_LENGTH/2,int(SWEEP_LENGTH/STEP_SIZE)) + Y_MIDDLE
	x_positions = y_positions*0 + X_MIDDLE
	z_positions = y_positions*0 + Z_FOCUS
	
	script_core(
		measurement_name = input('Measurement name? ').replace(' ', '_'),
		the_setup = TheSetup(),
		bias_voltage = 200,
		laser_DAC = 2000,
		positions = list(zip(x_positions,y_positions,z_positions)),
		n_triggers = 2,
		acquire_channels = [1,2],
		two_pulses = True,
	)

