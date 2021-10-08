import numpy as np
from time import sleep
import grafica # https://github.com/SengerM/grafica
from lgadtools.LGADSignal import LGADSignal # https://github.com/SengerM/lgadtools
from data_processing_bureaucrat.Bureaucrat import Bureaucrat, TelegramReportingInformation # https://github.com/SengerM/data_processing_bureaucrat
from progressreporting.TelegramProgressReporter import TelegramReporter # https://github.com/SengerM/progressreporting
from pathlib import Path
from plotting_scripts.plot_everything_from_linear_scan import script_core as plot_everything_from_linear_scan

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
	
	print('Configuring laser...')
	the_setup.laser_DAC = laser_DAC
	the_setup.laser_status = 'on'
	
	print('Setting bias voltage...')
	the_setup.bias_voltage = bias_voltage
	
	ofile_path = bureaucrat.processed_data_dir_path/Path('measured_data.csv')
	with open(ofile_path, 'w') as ofile:
		string = f'n_position,n_trigger,x (m),y (m),z (m),n_channel,n_pulse,Amplitude (V),Noise (V),Rise time (s),Collected charge (V s),Time over noise (s)'
		for pp in TIMES_AT:
			string += f',t_{pp} (s)'
		print(string, file = ofile)
	
	reporter = TelegramReporter(
		telegram_token = TelegramReportingInformation().token, 
		telegram_chat_id = TelegramReportingInformation().chat_id,
	)
	with reporter.report_for_loop(len(positions)*n_triggers, f'{bureaucrat.measurement_name}') as reporter:
		with open(ofile_path, 'a') as ofile:
			for n_position, target_position in enumerate(positions):
				the_setup.move_to(*target_position)
				sleep(0.1)
				position = the_setup.position
				for n_trigger in range(n_triggers):
					plot_this_trigger = np.random.rand() < 20/(len(positions)*n_triggers)
					print(f'Measuring: n_position={n_position}, n_trigger={n_trigger}...')
					the_setup.wait_for_trigger()
					# Esto es para sacarme de encima el ruido de mierda ---
					while True:
						the_setup.wait_for_trigger()
						try:
							_raw = the_setup.get_waveform(channel=acquire_channels[0])
						except Exception as e:
							print(f'Cannot get data from oscilloscope, reason: {e}')
							continue
						_amplitude = np.array(_raw['Amplitude (V)'])
						_time = np.array(_raw['Time (s)'])
						# ~ fig = grafica.new()
						# ~ fig.scatter(x=_time,y=_amplitude)
						# ~ fig.show()
						# ~ input('Continue?')
						samples_where_we_shoud_have_no_signal = _amplitude[(_time<220e-9)|((_time>230e-9)&(_time<320e-9))] # This is highly hardcoded here, from the previous plot!!!
						_noise = np.std(samples_where_we_shoud_have_no_signal)
						if _noise < 4e-3:
							break
					# -----------------------------------------------------
					signals = {}
					for n_ch in acquire_channels:
						try:
							raw_data = the_setup.get_waveform(channel = n_ch)
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
							string = f'{n_position},{n_trigger},{position[0]},{position[1]},{position[2]},{n_ch},{n_pulse}'
							string += f',{signal.amplitude},{signal.noise},{signal.rise_time},{signal.collected_charge},{signal.time_over_noise}'
							for pp in TIMES_AT:
								string += f',{signal.time_at_rising_edge(pp)}'
							print(string, file = ofile)
							if plot_this_trigger:
								fig = grafica.new(
									title = f'Signal at n_position {n_position} n_trigger {n_trigger} n_ch {n_ch} n_pulse {n_pulse}',
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
	print('Finished measuring! :)')
	print('Doing plots...')
	plot_everything_from_linear_scan(directory = bureaucrat.measurement_base_path)
	print('Finished plotting!')
	
	return bureaucrat.measurement_base_path

########################################################################

if __name__ == '__main__':
	from TheSetup import TheSetup
	
	X_MIDDLE = 1.141396484375e-3
	Y_MIDDLE = 9.58572265625e-3
	Z_FOCUS = 51.901474609375e-3
	STEP_SIZE = 1e-6
	SWEEP_LENGTH = 250e-6
	
	x_positions = np.linspace(-SWEEP_LENGTH/2,SWEEP_LENGTH/2,int(SWEEP_LENGTH/STEP_SIZE)) + X_MIDDLE
	y_positions = x_positions*0 + Y_MIDDLE
	z_positions = x_positions*0 + Z_FOCUS
	
	script_core(
		measurement_name = input('Measurement name? ').replace(' ', '_'),
		the_setup = TheSetup(),
		bias_voltage = 111,
		laser_DAC = 1555, # Approximately should be 5 MIPs
		positions = list(zip(x_positions,y_positions,z_positions)),
		n_triggers = 555,
		acquire_channels = [1,2],
		two_pulses = True,
	)

