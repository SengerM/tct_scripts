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
		laser_DAC_values: list, # List of DAC values to measure.
		n_triggers: int = 1, # Number of triggers to acquire at each point.
		acquire_channels = [1,2,3,4], # List with the numbers of the channels to record from the oscilloscope.
	):
	bureaucrat = Bureaucrat(
		str(Path(f'C:/Users/tct_cms/Desktop/TCT_measurements_data/{measurement_name}')),
		variables = locals(),
		new_measurement = True,
	)
	
	the_setup = TheSetup()
	
	the_setup.laser_status = 'on'
	
	print('Setting bias voltage...')
	the_setup.bias_voltage = bias_voltage
	
	ofile_path = bureaucrat.processed_data_dir_path/Path('measured_data.csv')
	with open(ofile_path, 'w') as ofile:
		string = f'n_DAC,n_trigger,DAC value,x (m),y (m),z (m),n_channel,Amplitude (V),Noise (V),Rise time (s),Collected charge (V s),Time over noise (s)'
		for pp in TIMES_AT:
			string += f',t_{pp} (s)'
		print(string, file = ofile)
	
	reporter = TelegramReporter(
		telegram_token = TelegramReportingInformation().token, 
		telegram_chat_id = TelegramReportingInformation().chat_id,
	)
	with reporter.report_for_loop(len(laser_DAC_values)*n_triggers, f'{bureaucrat.measurement_name}') as reporter:
		with open(ofile_path, 'a') as ofile:
			for n_DAC, DAC in enumerate(laser_DAC_values):
				the_setup.laser_DAC = int(DAC)
				sleep(0.1)
				position = the_setup.position
				for n in range(n_triggers):
					print(f'Measuring: n_DAC={n_DAC}, n_trigger={n}...')
					the_setup.wait_for_trigger()
					signals = {}
					for n_ch in acquire_channels:
						raw_data = the_setup.get_waveform(channel = n_ch)
						signals[n_ch] = LGADSignal(
							time = raw_data['Time (s)'],
							samples = raw_data['Amplitude (V)'],
						)
						string = f'{n_DAC},{n},{the_setup.laser_DAC},{position[0]:.6e},{position[1]:.6e},{position[2]:.6e},{n_ch}'
						string += f',{signals[n_ch].amplitude:.6e},{signals[n_ch].noise:.6e},{signals[n_ch].rise_time:.6e},{signals[n_ch].collected_charge:.6e},{signals[n_ch].time_over_noise:.6e}'
						for pp in TIMES_AT:
							try:
								string += f',{signals[n_ch].find_time_at_rising_edge(pp):.6e}'
							except:
								string += f',{float("NaN")}'
						print(string, file = ofile)
					if np.random.rand() < 20/(len(laser_DAC_values)*n_triggers):
						for n_ch in acquire_channels:
							fig = grafica.new(
								title = f'Signal at n_DAC {n_DAC:05d} n_trigger {n} n_ch {n_ch}',
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

########################################################################

if __name__ == '__main__':
	
	script_core(
		measurement_name = input('Measurement name? ').replace(' ', '_'),
		bias_voltage = 55,
		laser_DAC_values = np.linspace(0,2222,int(99/2)),
		n_triggers = 1111,
		acquire_channels = [1],
	)

