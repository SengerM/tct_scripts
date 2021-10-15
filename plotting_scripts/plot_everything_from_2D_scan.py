from data_processing_bureaucrat.Bureaucrat import Bureaucrat
import numpy as np
from pathlib import Path
import pandas
import grafica

def script_core(directory):
	bureaucrat = Bureaucrat(
		directory,
		variables = locals(),
	)
	
	try:
		data_df = pandas.read_feather(bureaucrat.processed_by_script_dir_path('scan_2D.py')/Path('measured_data.fd'))
	except FileNotFoundError:
		data_df = pandas.read_csv(bureaucrat.processed_by_script_dir_path('scan_2D.py')/Path('measured_data.csv'))
	
	n_positions_1 = [n for n in range(max(data_df['n_position_1']))]
	n_positions_2 = [n for n in range(max(data_df['n_position_2']))]
	
	for column in data_df:
		if column in {'n_position_1', 'n_position_2', 'n_trigger', 'n_channel', 'n_pulse'}:
			continue
		# For each column, plot the mean and the std as scatter plots ---
		for n_pulse in sorted(set(data_df['n_pulse'])):
			for stat in {'mean','std'}:
				for package in {'matplotlib', 'plotly'}:
					for n_channel in sorted(set(data_df['n_channel'])):
						this_channel_this_pulse_df = data_df[(data_df['n_channel']==n_channel)&(data_df['n_pulse']==n_pulse)]
						if stat == 'mean':
							pivottable_for_one_channel_one_pulse = pandas.pivot_table(this_channel_this_pulse_df, values=column, index='n_position_2', columns='n_position_1', aggfunc=np.nanmean)
						elif stat == 'std':
							pivottable_for_one_channel_one_pulse = pandas.pivot_table(this_channel_this_pulse_df, values=column, index='n_position_2', columns='n_position_1', aggfunc=np.nanstd)
						else:
							raise ValueError(f'Dont know what is stat {repr(stat)}.')
						fig = grafica.new(
							title = f'{column[:column.find("(")][:-1]} {stat} n_channel {n_channel} n_pulse {n_pulse}',
							subtitle = f'Data set: {bureaucrat.measurement_name}',
							xlabel = 'x (m)',
							ylabel = 'y (m)',
							plotter_name = package,
							aspect = 'equal',
						)
						fig.heatmap(
							x = sorted(set(data_df['x (m)'])),
							y = sorted(set(data_df['y (m)'])),
							z = pivottable_for_one_channel_one_pulse,
							zlabel = column,
						)
					grafica.save_unsaved(mkdir = bureaucrat.processed_data_dir_path/Path('png' if package=='matplotlib' else 'html'))
	
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

