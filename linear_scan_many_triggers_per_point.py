import numpy as np
from time import sleep
import grafica # https://github.com/SengerM/grafica
from lgadtools.LGADSignal import LGADSignal # https://github.com/SengerM/lgadtools
from data_processing_bureaucrat.Bureaucrat import Bureaucrat, TelegramReportingInformation # https://github.com/SengerM/data_processing_bureaucrat
from progressreporting.TelegramProgressReporter import TelegramReporter # https://github.com/SengerM/progressreporting
from pathlib import Path
from plotting_scripts.plot_everything_from_linear_scan import script_core as plot_everything_from_linear_scan
from TheSetup import TheSetup

TIMES_AT = [10,20,30,40,50,60,70,80,90]

def script_core(
	measurement_name: str, 
	bias_voltage: float,
	laser_DAC: float,
	x_start: float, 
	x_end: float, 
	y_start: float, 
	y_end: float, 
	z_focus: float, 
	n_steps: int, 
	n_triggers: int = 1,
	acquire_channels = [1,2,3,4],
):
	for var in [x_start, x_end, y_start, y_end, z_focus]:
		if var**2 > 1: 
			raise ValueError(f'Check the values of x_start, x_end, y_start, y_end and z_focus. One of them is {var} which is more than one meter, this has to be wrong.')
	bureaucrat = Bureaucrat(
		str(Path(f'C:/Users/tct_cms/Desktop/TCT_measurements_data/{measurement_name}')),
		variables = locals(),
		new_measurement = True,
	)
	
	the_setup = TheSetup()
	
	the_setup.laser_DAC = laser_DAC
	the_setup.laser_status = 'on'
	
	print('Moving to start position...')
	the_setup.move_to(
		x = x_start,
		y = y_start,
		z = z_focus,
	)
	
	print('Setting bias voltage...')
	the_setup.bias_voltage = bias_voltage
	
	ofile_path = bureaucrat.processed_data_dir_path/Path('measured_data.csv')
	with open(ofile_path, 'w') as ofile:
		string = f'n_position\tn_trigger\tx (m)\ty (m)\tz (m)\tn_channel\tAmplitude (V)\tNoise (V)\tRise time (s)\tCollected charge (V s)\tTime over noise (s)'
		for pp in TIMES_AT:
			string += f'\tt_{pp} (s)'
		print(string, file = ofile)
	
	x_positions = np.linspace(x_start,x_end,n_steps)
	y_positions = np.linspace(y_start,y_end,n_steps)
	reporter = TelegramReporter(
		telegram_token = TelegramReportingInformation().token, 
		telegram_chat_id = TelegramReportingInformation().chat_id,
	)
	with reporter.report_for_loop(n_steps*n_triggers, f'{bureaucrat.measurement_name}') as reporter:
		with open(ofile_path, 'a') as ofile:
			for n_pos,xy_position in enumerate([(x,y) for x,y in zip(x_positions,y_positions)]):
				the_setup.move_to(
					x = xy_position[0],
					y = xy_position[1],
				)
				sleep(0.1)
				position = the_setup.position
				for n in range(n_triggers):
					print(f'Measuring: n_position={n_pos}, n_trigger={n}...')
					the_setup.wait_for_trigger()
					signals = {}
					for n_ch in acquire_channels:
						raw_data = the_setup.get_waveform(channel = n_ch)
						signals[n_ch] = LGADSignal(
							time = raw_data['Time (s)'],
							samples = raw_data['Amplitude (V)'],
						)
						string = f'{n_pos}\t{n}\t{position[0]:.6e}\t{position[1]:.6e}\t{position[2]:.6e}\t{n_ch}'
						string += f'\t{signals[n_ch].amplitude:.6e}\t{signals[n_ch].noise:.6e}\t{signals[n_ch].rise_time:.6e}\t{signals[n_ch].collected_charge:.6e}\t{signals[n_ch].time_over_noise:.6e}'
						for pp in TIMES_AT:
							try:
								string += f'\t{signals[n_ch].find_time_at_rising_edge(pp):.6e}'
							except:
								string += f'\t{float("NaN")}'
						print(string, file = ofile)
					if np.random.rand() < 20/n_steps/n_triggers:
						for n_ch in acquire_channels:
							fig = grafica.new(
								title = f'Signal at {n_pos:05d} n_trigg {n} n_ch {n_ch}',
								subtitle = f'Measurement: {bureaucrat.measurement_name}',
								xlabel = 'Time (s)',
								ylabel = 'Amplitude (V)',
								plotter_name = 'plotly',
							)
							signals[n_ch].plot_grafica(fig)
							for pp in TIMES_AT:
								try:
									fig.plot(
										[signals[n_ch].find_time_at_rising_edge(pp)],
										[signals[n_ch].signal_at(signals[n_ch].find_time_at_rising_edge(pp))],
										marker = 'x',
										linestyle = '',
										label = f'Time at {pp} %',
										color = (0,0,0),
									)
								except:
									pass
							grafica.save_unsaved(mkdir=bureaucrat.processed_data_dir_path/Path('some_random_processed_signals_plots'))
					reporter.update(1)
	print('Finished measuring! :)')
	print('Doing plots...')
	plot_everything_from_linear_scan(directory = bureaucrat.measurement_base_path)
	print('Finished plotting!')

########################################################################

if __name__ == '__main__':
	
	Y_START = 5.186806640625e-3 - 200e-6
	Y_STOP = Y_START + 2*200e-6
	X_FIXED = 1.238369140625e-3
	STEP_SIZE = 9e-6
	
	script_core(
		measurement_name = input('Measurement name? ').replace(' ', '_'),
		bias_voltage = 99,
		laser_DAC = 222,
		x_start = X_FIXED,
		x_end = X_FIXED,
		y_start = Y_START,
		y_end = Y_STOP,
		n_steps = int(((Y_STOP-Y_START)**2)**.5/STEP_SIZE),
		z_focus = 52.71626953125e-3,
		n_triggers = 4,
		acquire_channels = [1,2],
	)

