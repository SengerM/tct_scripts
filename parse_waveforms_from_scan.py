import numpy as np
import pandas
from pathlib import Path
from bureaucrat.Bureaucrat import Bureaucrat # https://github.com/SengerM/bureaucrat
import plotly.express as px
from signals.PeakSignal import PeakSignal, draw_in_plotly
import sqlite3

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

def calculate_1D_scan_distance_from_list_of_positions(positions):
	"""positions: List of positions, e.g. [(1, 4, 2), (2, 5, 2), (3, 7, 2), (4, 9, 2)].
	returns: List of distances starting with 0 at the first point and assuming linear interpolation."""
	return [0] + list(np.cumsum((np.diff(positions, axis=0)**2).sum(axis=1)**.5))

def generate_column_with_distances(df):
	if df.index.name != 'n_position':
		raise ValueError(f'`df` must have as index `n_position`.')
	x = df.groupby(df.index).mean()[f'x (m)']
	y = df.groupby(df.index).mean()[f'y (m)']
	z = df.groupby(df.index).mean()[f'z (m)']
	distances_df = pandas.DataFrame(
		{
			'n_position': [i for i in range(len(set(df.index)))], 
			'Distance (m)': calculate_1D_scan_distance_from_list_of_positions(list(zip(x,y,z)))
		}
	)
	return distances_df.set_index('n_position')

def script_core(directory: Path, silent: bool = True):
	if not isinstance(silent, bool):
		raise ValueError(f'`silent` must be of type {repr(type(True))}, received object of type {repr(type(silent))}.')
	
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
	COPY_THESE_COLUMNS = ['n_position', 'n_trigger', 'n_channel', 'n_pulse', 'x (m)', 'y (m)', 'z (m)', 'When', 'Bias voltage (V)','Bias current (A)', 'Laser DAC', 'Temperature (°C)', 'Humidity (%RH)']
	data_frame_columns += COPY_THESE_COLUMNS
	data_df = pandas.DataFrame(columns = data_frame_columns)
	
	sqlite3_connection_output = sqlite3.connect(Quique.processed_data_dir_path/Path('data.sqlite'))
	sqlite3_connection_waveforms = sqlite3.connect(Quique.processed_by_script_dir_path('scan_1D.py')/Path('waveforms.sqlite'))
	
	with Quique.verify_no_errors_context():
		waveforms_df = pandas.read_sql_query('SELECT * from `waveforms`', sqlite3_connection_waveforms)
		number_of_waveforms_to_process = len(set(waveforms_df['n_waveform']))
		for n_waveform in set(waveforms_df['n_waveform']): # We have to process each waveform one by one, there is no alternative. This will take time...
			if not silent:
				print(f'Processing n_waveform {n_waveform} out of {number_of_waveforms_to_process-1}...')
			this_waveform_rows = waveforms_df['n_waveform'] == n_waveform
			signal = PeakSignal(
				time = waveforms_df.loc[this_waveform_rows,'Time (s)'],
				samples = waveforms_df.loc[this_waveform_rows,'Amplitude (V)'],
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
			parsed_data_dict = {
				**parsed_data_dict, 
				**waveforms_df.loc[this_waveform_rows, COPY_THESE_COLUMNS].iloc[0].to_dict()
			}
			
			data_df = data_df.append(pandas.Series(parsed_data_dict), ignore_index = True)
			
			if len(data_df.index) > 1e6 or n_waveform == number_of_waveforms_to_process-1:
				data_df.to_sql('parsed_data', sqlite3_connection_output, index=False, if_exists='append')
				data_df = pandas.DataFrame()
		
		# Add the column `Distance (m)` to the data so it does not has to be calculated later on...
		data_df = pandas.read_sql_query('SELECT * from `parsed_data`', sqlite3_connection_output)
		data_df = data_df.set_index('n_position')
		data_df['Distance (m)'] = generate_column_with_distances(data_df)['Distance (m)']
		data_df = data_df.reset_index()
		data_df.to_sql('parsed_data', sqlite3_connection_output, index=False, if_exists='replace')
			
		if not silent:
			print('Finished processing!')
		
	return Quique.measurement_base_path

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
	script_core(Path(args.directory), silent=False)
