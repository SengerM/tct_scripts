from bureaucrat.Bureaucrat import Bureaucrat # https://github.com/SengerM/bureaucrat
import numpy as np
from pathlib import Path
import plotly.express as px
import pandas
from grafica.plotly_utils.utils import line
import warnings
from scipy.stats import median_abs_deviation

def calculate_1D_scan_distance(positions):
	"""positions: List of positions, e.g. [(1, 4, 2), (2, 5, 2), (3, 7, 2), (4, 9, 2)].
	returns: List of distances starting with 0 at the first point and assuming linear interpolation."""
	return [0] + list(np.cumsum((np.diff(positions, axis=0)**2).sum(axis=1)**.5))

def calculate_1D_scan_distance_from_dataframe(df):
	x = df.groupby('n_position').mean()[f'x (m)']
	y = df.groupby('n_position').mean()[f'y (m)']
	z = df.groupby('n_position').mean()[f'z (m)']
	distances_df = pandas.DataFrame({'n_position': [i for i in range(len(set(df['n_position'])))], 'Distance (m)': calculate_1D_scan_distance(list(zip(x,y,z)))})
	distances_df.set_index('n_position')
	return distances_df

def mean_std(df, by):
	"""Groups by `by` (list of columns), calculates mean and std, and creates one column with mean and another with std for each column not present in `by`.
	Example
	-------
	df = pandas.DataFrame(
		{
			'n': [1,1,1,1,2,2,2,3,3,3,4,4],
			'x': [0,0,0,0,1,1,1,2,2,2,3,3],
			'y': [1,2,1,1,2,3,3,3,4,3,4,5],
		}
	)

	mean_df = mean_std(df, by=['n','x'])
	
	produces:
	
	   n  x    y mean     y std
	0  1  0  1.250000  0.500000
	1  2  1  2.666667  0.577350
	2  3  2  3.333333  0.577350
	3  4  3  4.500000  0.707107
	"""
	k_MAD_TO_STD = 1.4826 # https://en.wikipedia.org/wiki/Median_absolute_deviation#Relation_to_standard_deviation
	def MAD_std(x):
		return median_abs_deviation(x, nan_policy='omit')*k_MAD_TO_STD
	with warnings.catch_warnings(): # There is a deprecation warning that will be converted into an error in future versions of Pandas. When that happens, I will solve this.
		warnings.simplefilter("ignore")
		mean_df = df.groupby(by=by).agg(['mean','std',np.median,MAD_std])
	mean_df.columns = [' '.join(col).strip() for col in mean_df.columns.values]
	return mean_df.reset_index()

def calculate_normalized_collected_charge(df):
	df['Normalized collected charge'] = df['Collected charge (V s)']
	mean_df = df.groupby(by = ['n_channel','n_pulse','n_position']).mean().reset_index()
	for n_pulse in sorted(set(mean_df['n_pulse'])):
		for n_channel in sorted(set(mean_df['n_channel'])):
			mean_df.loc[(mean_df['n_pulse']==n_pulse)&(mean_df['n_channel']==n_channel), 'Normalized collected charge'] = mean_df.loc[(mean_df['n_pulse']==n_pulse)&(mean_df['n_channel']==n_channel), 'Collected charge (V s)']
			offset_factor = np.nanmin(mean_df.loc[(mean_df['n_pulse']==n_pulse)&(mean_df['n_channel']==n_channel), 'Normalized collected charge'])
			mean_df.loc[(mean_df['n_pulse']==n_pulse)&(mean_df['n_channel']==n_channel), 'Normalized collected charge'] -= offset_factor
			scale_factor = np.nanmax(mean_df.loc[(mean_df['n_pulse']==n_pulse)&(mean_df['n_channel']==n_channel), 'Normalized collected charge'])
			mean_df.loc[(mean_df['n_pulse']==n_pulse)&(mean_df['n_channel']==n_channel), 'Normalized collected charge'] /= scale_factor
			# Now I repeat for the df ---
			df.loc[(df['n_pulse']==n_pulse)&(df['n_channel']==n_channel), 'Normalized collected charge'] -= offset_factor
			df.loc[(df['n_pulse']==n_pulse)&(df['n_channel']==n_channel), 'Normalized collected charge'] /= scale_factor
	return df

PLOT_HISTOGRAMS = False
PLOT_MEAN_STD_PLOTS = False

def script_core(directory):
	bureaucrat = Bureaucrat(
		directory,
		variables = locals(),
	)
	
	data_df = pandas.read_feather(
		bureaucrat.processed_by_script_dir_path('parse_waveforms_from_scan.py')/Path('data.fd'),
	)
	
	distances_df = calculate_1D_scan_distance_from_dataframe(data_df)
	data_df.set_index('n_position', inplace=True)
	data_df = data_df.merge(distances_df, left_index=True, right_index=True)
	data_df.reset_index(inplace=True, drop=True)
	
	data_df = calculate_normalized_collected_charge(data_df)
	
	GROUP_BY = ['n_position','n_channel','n_pulse','Distance (m)']
	averaged_by_position_df = mean_std(data_df, by=GROUP_BY)
	
	if PLOT_MEAN_STD_PLOTS:
		mean_std_plots_dir_Path = bureaucrat.processed_data_dir_path/Path('mean_std_plots')
		mean_std_plots_dir_Path.mkdir(parents=True, exist_ok=True)
		for column in averaged_by_position_df:
			if column in GROUP_BY:
				continue
			fig = line(
				data_frame = averaged_by_position_df,
				x = 'Distance (m)',
				y = column,
				color = 'n_channel',
				line_dash = 'n_pulse',
				symbol = 'n_pulse',
				markers = True,
				title = f'{column}<br><sup>Measurement: {bureaucrat.measurement_name}</sup>',
			)
			fig.write_html(str(mean_std_plots_dir_Path/Path(f'{column}.html')), include_plotlyjs='cdn')
	
	error_band_plots_dir_Path = bureaucrat.processed_data_dir_path/Path('error_band_plots')
	error_band_plots_dir_Path.mkdir(parents=True, exist_ok=True)
	for column in data_df:
		if column in GROUP_BY + ['When']:
			continue
		fig = line(
			data_frame = averaged_by_position_df,
			x = 'Distance (m)',
			y = f'{column} median',
			error_y = f'{column} MAD_std',
			error_y_mode = 'band',
			color = 'n_channel',
			line_dash = 'n_pulse',
			symbol = 'n_pulse',
			markers = True,
			title = f'{column}<br><sup>Measurement: {bureaucrat.measurement_name}</sup>',
		)
		fig.write_html(str(error_band_plots_dir_Path/Path(f'{column}.html')), include_plotlyjs='cdn')
		
	n_channels = sorted(set(data_df['n_channel'])) 
	for idx,ch_A in enumerate(n_channels):
		for ch_B in n_channels[idx:]:
			if ch_A == ch_B:
				continue
			these_channels_df = data_df.loc[(data_df['n_channel']==ch_A)|(data_df['n_channel']==ch_B),['n_position','n_pulse','n_trigger','n_channel','Distance (m)','Normalized collected charge']]
			summed_df = these_channels_df.groupby(by=['n_position','n_pulse','n_trigger','Distance (m)']).sum().reset_index()
			summed_and_averaged_df = mean_std(summed_df, by=['Distance (m)','n_pulse','n_channel'])
			these_channels_df = mean_std(these_channels_df, by=['Distance (m)','n_pulse','n_channel'])
			for ch in {ch_A,ch_B}:
				these_channels_df.loc[these_channels_df['n_channel']==ch,'Channel'] = f'CH{ch}'
			summed_and_averaged_df.loc[(summed_and_averaged_df['n_channel']!=ch_A)&(summed_and_averaged_df['n_channel']!=ch_B),'Channel'] = f'CH{ch_A}+CH{ch_B}'
			df = these_channels_df.append(summed_and_averaged_df, ignore_index=True)
			fig = line(
				data_frame = df,
				x = 'Distance (m)',
				y = 'Normalized collected charge median',
				error_y = 'Normalized collected charge MAD_std',
				error_y_mode = 'band',
				color = 'Channel',
				line_dash = 'n_pulse',
				symbol = 'n_pulse',
				title = f'Total collected charge CH{ch_A} and CH{ch_B}<br><sup>Measurement: {bureaucrat.measurement_name}</sup>',
			)
			fig.write_html(str(error_band_plots_dir_Path/Path(f'Total collected charge CH{ch_A} and CH{ch_B}.html')), include_plotlyjs='cdn')
	
	# Histograms with sliders for the position ---
	if PLOT_HISTOGRAMS:
		for column in {'Amplitude (V)','Noise (V)','Rise time (s)','Collected charge (V s)','Time over noise (s)','t_10 (s)','t_50 (s)','t_90 (s)'}:
			if column in {'n_position', 'n_trigger', 'n_channel', 'n_pulse', 'x (m)', 'y (m)', 'z (m)', 'Distance (m)'}:
				continue
			figure_title = f'{column.split("(")[0]} distribution vs position'
			fig = px.histogram(
				data_df,
				x = column,
				title = f'{figure_title}<br><sup>Measurement {bureaucrat.measurement_name}</sup>',
				barmode = 'overlay',
				animation_frame = 'n_position',
				color = 'n_pulse',
				facet_row = 'n_channel',
				range_x = [min(data_df[column]), max(data_df[column])],
			)
			fig["layout"].pop("updatemenus")
			fig.update_traces(
				xbins = dict(
					start = min(data_df[column]),
					end = max(data_df[column]),
					size = (max(data_df[column])-min(data_df[column]))/99,
				),
			)
			ofilepath = bureaucrat.processed_data_dir_path/Path('histograms')/Path(figure_title+'.html')
			ofilepath.parent.absolute().mkdir(parents=True, exist_ok=True)
			fig.write_html(str(ofilepath), include_plotlyjs='cdn')
	
	try:
		average_waveforms_df = pandas.read_feather(bureaucrat.processed_by_script_dir_path('scan_1D.py')/Path('average_waveforms.fd'))
		fig = line(
			title = f'Waveforms<br><sup>Measurement {bureaucrat.measurement_name}</sup>',
			data_frame = average_waveforms_df,
			x = 'Time (s)',
			y = 'Amplitude mean (V)',
			color = 'n_pulse',
			animation_frame = 'n_position',
			facet_row = 'n_channel',
		)
		fig.update_yaxes(range=[average_waveforms_df['Amplitude mean (V)'].min(), average_waveforms_df['Amplitude mean (V)'].max()])
		fig.update_layout(transition={'duration': 1})
		fig.write_html(str(bureaucrat.processed_data_dir_path/Path('waveforms.html')), include_plotlyjs='cdn')
	except FileNotFoundError:
		pass
	
if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser(description='Plots every thing measured in an xy scan.')
	parser.add_argument(
		'--dir',
		metavar = 'path', 
		help = 'Path to the base directory of a measurement.',
		required = True,
		dest = 'directory',
		type = str,
	)
	args = parser.parse_args()
	script_core(args.directory)
