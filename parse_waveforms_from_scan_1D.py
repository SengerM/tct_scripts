import numpy as np
import pandas
from pathlib import Path
from bureaucrat.Bureaucrat import Bureaucrat # https://github.com/SengerM/bureaucrat
import plotly.graph_objects as go
from signals.PeakSignal import PeakSignal, draw_in_plotly
import sqlite3
from contextlib import ExitStack # https://stackoverflow.com/a/34798330/8849755
import warnings

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
	try:
		for pp in TIMES_AT:
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
	except Exception as e:
		warnings.warn(f'Cannot execute `draw_times_at`, reason: {e}')

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

def human_readable(num, suffix="B"):
	# https://stackoverflow.com/a/1094933/8849755
	for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
		if abs(num) < 1024.0:
			return f"{num:3.1f} {unit}{suffix}"
		num /= 1024.0
	return f"{num:.1f} Yi{suffix}"

def script_core(directory: Path, delete_waveform_file_if_it_is_bigger_than_bytes: float=0, silent: bool = True, telegram_reporter_data_dict: dict = None):
	"""
	Parameters
	----------
	directory: Path
		Path to directory of measurement to which apply this script.
	delete_waveform_file_if_it_is_bigger_than_bytes: float, default 0
		If the file that contains the measured waveforms is larger than
		this number, in bytes, it will be deleted. Otherwise, nothing
		is done. Default value is `0` so it will delete the file no matter
		its size.
	silent: bool, default True
		If `False` messages are print showing the progress.
	telegram_reporter_data_dict
		A dictionary of the form
		```
		{'token': str, 'chat_id': str}
		```
		If `None` then it is not used.
	"""
	if not isinstance(silent, bool):
		raise ValueError(f'`silent` must be of type {repr(type(True))}, received object of type {repr(type(silent))}.')
	if not isinstance(delete_waveform_file_if_it_is_bigger_than_bytes, (int, float)):
		raise TypeError(f'`delete_waveform_file_if_it_is_bigger_than_bytes` must be a float number, received object of type {type(delete_waveform_file_if_it_is_bigger_than_bytes)}.')
	
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
	
	TEMPORARY_DATABASE_WHILE_PROCESSING_PATH = Quique.processed_data_dir_path/Path('data.sqlite')
	sqlite3_connection_temporary_database = sqlite3.connect(TEMPORARY_DATABASE_WHILE_PROCESSING_PATH)
	WAVEFORMS_DATABASE_PATH = Quique.processed_by_script_dir_path('scan_1D.py')/Path('waveforms.sqlite')
	sqlite3_connection_waveforms = sqlite3.connect(WAVEFORMS_DATABASE_PATH)
	
	if telegram_reporter_data_dict is not None:
		from progressreporting.TelegramProgressReporter import TelegramReporter # https://github.com/SengerM/progressreporting
		telegram_reporter = TelegramReporter(telegram_token=telegram_reporter_data_dict['token'], telegram_chat_id=telegram_reporter_data_dict['chat_id'])
	
	with Quique.verify_no_errors_context():
		# Because the file may be too large (several GB) we process the waveforms in batches.
		if not silent:
			print(f'Reading the total number of waveforms to process...')
		sqlite3_cursor_waveforms = sqlite3_connection_waveforms.cursor()
		sqlite3_cursor_waveforms.execute('SELECT max(n_waveform) from waveforms')
		number_of_waveforms_to_process = sqlite3_cursor_waveforms.fetchone()[0]
		
		NUMBER_OF_WAVEFORMS_IN_EACH_BATCH = 3333 # This depends on the amount of memory you want to use...
		number_of_batches = number_of_waveforms_to_process//NUMBER_OF_WAVEFORMS_IN_EACH_BATCH + 1 if number_of_waveforms_to_process%NUMBER_OF_WAVEFORMS_IN_EACH_BATCH != 0 else 0
		
		if not silent:
			print(f'A total of {number_of_waveforms_to_process} waveforms will be processed in {number_of_batches} batches.')
		
		with telegram_reporter.report_for_loop(number_of_waveforms_to_process-1, f'Waveforms parsing for measurement {Quique.measurement_name}') if telegram_reporter_data_dict is not None else ExitStack() as telegram_reporter:
			highest_n_waveform_already_processed = -1
			for n_batch in range(number_of_batches):
				if not silent:
					print(f'Reading waveforms for n_batch {n_batch}...')
				waveforms_df = pandas.read_sql_query(f'SELECT * from waveforms where (n_waveform>{highest_n_waveform_already_processed} and n_waveform<={highest_n_waveform_already_processed+NUMBER_OF_WAVEFORMS_IN_EACH_BATCH})', sqlite3_connection_waveforms)
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
					
					if np.random.rand() < 40/number_of_waveforms_to_process: # Produce a control plot for the current waveform...
						fig = draw_in_plotly(signal)
						fig.update_layout(
							title = f'Control plot n_waveform {n_waveform}, n_position {parsed_data_dict["n_position"]}, n_trigger {parsed_data_dict["n_trigger"]}, n_pulse {parsed_data_dict["n_pulse"]}, n_channel {parsed_data_dict["n_channel"]}<br><sup>Measurement: {Quique.measurement_name}</sup>',
							xaxis_title = "Time (s)",
							yaxis_title = "Amplitude (V)",
						)
						draw_times_at(fig=fig, signal=signal)
						CONTROL_PLOTS_FOR_SIGNAL_PROCESSING_DIR_PATH = Quique.processed_data_dir_path/Path('plots with a random selection of the waveforms')
						CONTROL_PLOTS_FOR_SIGNAL_PROCESSING_DIR_PATH.mkdir(exist_ok=True)
						fig.write_html(
							str(CONTROL_PLOTS_FOR_SIGNAL_PROCESSING_DIR_PATH/Path(f'n_waveform {n_waveform}.html')),
							include_plotlyjs = 'cdn',
						)
					
					highest_n_waveform_already_processed = waveforms_df['n_waveform'].max()
					if telegram_reporter_data_dict is not None:
						telegram_reporter.update(1)
					
					if len(data_df.index) > 10e3 or n_waveform == number_of_waveforms_to_process-1:
						if not silent:
							print('Saving parsed data...')
						data_df.to_sql('parsed_data', sqlite3_connection_temporary_database, index=False, if_exists='append')
						data_df = pandas.DataFrame()
		
		# Add the column `Distance (m)` to the data so it does not has to be calculated later on...
		if not silent:
			print('Calculating `Distance (m)` column and adding it to the parsed data...')
		data_df = pandas.read_sql_query('SELECT * from `parsed_data`', sqlite3_connection_temporary_database)
		data_df = data_df.set_index('n_position')
		data_df['Distance (m)'] = generate_column_with_distances(data_df)['Distance (m)']
		data_df = data_df.reset_index()
		data_df.reset_index(drop=True).to_feather(Quique.processed_data_dir_path/Path('data.fd'))
		TEMPORARY_DATABASE_WHILE_PROCESSING_PATH.unlink() # Delete it now.
				
		if not silent:
			print('Finished processing!')
		
		if WAVEFORMS_DATABASE_PATH.stat().st_size >= delete_waveform_file_if_it_is_bigger_than_bytes:
			if not silent:
				print(f'Deleting the waveforms database file which has a size of {human_readable(WAVEFORMS_DATABASE_PATH.stat().st_size)}')
			with open(WAVEFORMS_DATABASE_PATH.parent/Path('README.md'), 'a') as ofile:
				print(f'In this directory there was a file `{WAVEFORMS_DATABASE_PATH.parts[-1]}` with all the waveforms. It was deleted after parsing all the waveforms (see results in "{Quique.processed_data_dir_path}") because its size was too big ({human_readable(WAVEFORMS_DATABASE_PATH.stat().st_size)}).', file=ofile)
			WAVEFORMS_DATABASE_PATH.unlink()
		
	return Quique.measurement_base_path

if __name__ == '__main__':
	import argparse
	import my_telegram_bots

	parser = argparse.ArgumentParser()
	parser.add_argument('--dir',
		metavar = 'path',
		help = 'Path to the base measurement directory.',
		required = True,
		dest = 'directory',
		type = str,
	)
	args = parser.parse_args()
	script_core(
		Path(args.directory), 
		silent = False,
		telegram_reporter_data_dict = {'token': my_telegram_bots.robobot.token, 'chat_id': my_telegram_bots.chat_ids['Robobot TCT setup']}
	)
