import numpy as np
import pandas
from pathlib import Path
from bureaucrat.Bureaucrat import Bureaucrat # https://github.com/SengerM/bureaucrat
import plotly.express as px
from signals.PeakSignal import PeakSignal, draw_in_plotly
from utils import DataFrameDumper

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

def script_core(directory: Path):
	Quique = Bureaucrat( # Quique is the friendly alias to the name Enrique (at least in Argentina).
		directory,
		variables = locals(),
	)
	
	if not Quique.job_successfully_completed_by_script('scan_1D.py'):
		raise RuntimeError(f'I cannot find a successful of the script `scan_1D.py` for the measurement {Quique.measurement_name} in order to process the waveforms.')
	
	data_frame_columns = ['n_waveform']
	data_frame_columns += ['Amplitude (V)','Noise (V)','Rise time (s)','Collected charge (V s)','Time over noise (s)']
	for pp in TIMES_AT:
		data_frame_columns += [f't_{pp} (s)']
	parsed_data_df = pandas.DataFrame(columns = data_frame_columns)
	parsed_data_df_dumper = DataFrameDumper(Quique.processed_data_dir_path/Path('parsed_data.fd'), parsed_data_df)
	
	measured_data_df = pandas.DataFrame(columns = ['n_position', 'n_trigger', 'n_channel', 'n_pulse','n_waveform', 'x (m)', 'y (m)', 'z (m)', 'When', 'Bias voltage (V)','Bias current (A)', 'Laser DAC', 'Temperature (°C)', 'Humidity (%RH)'])
	measured_data_df_dumper = DataFrameDumper(Quique.processed_data_dir_path/Path('measured_data.fd'), measured_data_df)
	
	with Quique.verify_no_errors_context():
		for fpath in sorted((Quique.processed_by_script_dir_path('scan_1D.py')/Path('measured_waveforms')).iterdir()):
			some_waveforms_df = pandas.read_feather(fpath)
			for n_waveform in set(some_waveforms_df['n_waveform']): # We have to process each waveform one by one, there is no alternative...
				this_waveform_rows = some_waveforms_df['n_waveform'] == n_waveform
				signal = PeakSignal(
					time = some_waveforms_df.loc[this_waveform_rows,'Time (s)'],
					samples = some_waveforms_df.loc[this_waveform_rows,'Amplitude (V)'],
				)
				
				parsed_data_dict = {
					'n_waveform': n_waveform,
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
					parsed_data_dict[f't_{pp} (s)'] = _time
				
				parsed_data_df = parsed_data_df.append(pandas.Series(parsed_data_dict), ignore_index = True)
				parsed_data_df = parsed_data_df_dumper.dump_to_disk(parsed_data_df)
				
				measured_data_df = measured_data_df.append(
					some_waveforms_df.loc[this_waveform_rows, measured_data_df.columns].iloc[0],
					ignore_index = True,
				)
				measured_data_df = measured_data_df_dumper.dump_to_disk(measured_data_df)
				
				print(f'n_waveform {n_waveform} was processed!')
		parsed_data_df_dumper.end(parsed_data_df)
		measured_data_df_dumper.end(measured_data_df)
		
		parsed_data_df_path = Quique.processed_data_dir_path/Path('parsed_data.fd')
		parsed_data_df = pandas.read_feather(parsed_data_df_path) # This is the whole dataframe, not the fragments we got from before...
		parsed_data_df = parsed_data_df.astype({'n_waveform': int})
		
		measured_data_df_path = Quique.processed_data_dir_path/Path('measured_data.fd')
		measured_data_df = pandas.read_feather(measured_data_df_path) # This is the whole dataframe, not the fragments we got from before...
		
		parsed_data_df = parsed_data_df.set_index('n_waveform')
		measured_data_df = measured_data_df.set_index('n_waveform')
		all_data_df = pandas.concat([parsed_data_df, measured_data_df], axis=1)
		all_data_df = all_data_df.reset_index()
		
		all_data_df.reset_index(drop=True).to_feather(Quique.processed_data_dir_path/Path('data.fd'))
		
		for fpath in [parsed_data_df_path, measured_data_df_path]:
			fpath.unlink()

if __name__ == '__main__':
	import argparse

	parser = argparse.ArgumentParser()
	parser.add_argument('--dir',
		metavar = 'path',
		help = 'Path to the base measurement directory.',
		required = True,
		dest = 'directory',
		type = str,
	)
	args = parser.parse_args()
	script_core(Path(args.directory))
