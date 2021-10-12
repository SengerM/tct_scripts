from data_processing_bureaucrat.Bureaucrat import Bureaucrat
import numpy as np
from pathlib import Path
import grafica
import pandas

def script_core(directory):
	bureaucrat = Bureaucrat(
		directory,
		variables = locals(),
	)
	
	data = pandas.read_csv(
		bureaucrat.processed_by_script_dir_path('linear_scan_many_triggers_per_point.py')/Path('measured_data.csv'),
	)
	
	n_position = sorted(set(data['n_position']))
	distance = [None]*len(n_position)
	for n_pos in n_position:
		if n_pos == 0: 
			distance[n_pos] = 0
			continue
		distance[n_pos] = distance[n_pos-1] + np.linalg.norm(data.loc[data['n_position']==n_pos,['x (m)', 'y (m)', 'z (m)']].iloc[0]-data.loc[data['n_position']==n_pos-1,['x (m)', 'y (m)', 'z (m)']].iloc[0])
	
	for column in data:
		if column in {'n_position', 'n_trigger', 'n_channel', 'n_pulse'}:
			continue
		# For each column, plot the mean and the std as scatter plots ---
		for n_pulse in sorted(set(data['n_pulse'])):
			for stat in {'mean','std'}:
				for package in {'matplotlib', 'plotly'}:
					fig = grafica.new(
						title = f'{column[:column.find("(")][:-1]} {stat} n_pulse {n_pulse}',
						subtitle = f'Data set: {bureaucrat.measurement_name}',
						xlabel = 'Distance (m)',
						ylabel = f'{stat} {column}',
						plotter_name = package,
					)
					for ch in sorted(set(data['n_channel'])):
						data_grouped_by_n_position_for_one_channel_one_pulse = data.loc[(data['n_channel']==ch)&(data['n_pulse']==n_pulse)].groupby(['n_position'])
						if stat == 'mean':
							y_vals = data_grouped_by_n_position_for_one_channel_one_pulse.mean()[column]
						elif stat == 'std':
							y_vals = data_grouped_by_n_position_for_one_channel_one_pulse.std()[column]
						else:
							raise ValueError(f'Dont know what is stat {repr(stat)}.')
						fig.scatter(
							x = distance,
							y = y_vals,
							label = f'CH {ch}',
							marker = '.',
						)
					grafica.save_unsaved(mkdir = bureaucrat.processed_data_dir_path/Path('png' if package=='matplotlib' else 'html'))
			# Now error band plots ---
			fig = grafica.new(
				title = f'{column[:column.find("(")][:-1]} n_pulse {n_pulse}',
				subtitle = f'Data set: {bureaucrat.measurement_name}',
				xlabel = 'Distance (m)',
				ylabel = column,
				plotter_name = 'plotly',
			)
			for ch in sorted(set(data['n_channel'])):
				data_grouped_by_n_position_for_one_channel_one_pulse = data.loc[(data['n_channel']==ch)&(data['n_pulse']==n_pulse)].groupby(['n_position'])
				fig.errorband(
					distance,
					y = data_grouped_by_n_position_for_one_channel_one_pulse.mean()[column],
					lower = data_grouped_by_n_position_for_one_channel_one_pulse.std()[column],
					higher = data_grouped_by_n_position_for_one_channel_one_pulse.std()[column],
					label = f'CH {ch}',
					marker = '.',
				)
			grafica.save_unsaved(mkdir = bureaucrat.processed_data_dir_path/Path('error band plots'))
	
	# Now calculate the normalized collected charge ---
	for n_pulse in sorted(set(data['n_pulse'])):
		fig = grafica.new(
			title = f'Normalized collected charge n_pulse {n_pulse}',
			subtitle = f'Data set: {bureaucrat.measurement_name}',
			xlabel = 'Distance (m)',
			ylabel = 'Normalized collected charge',
		)
		normalized_collected_charge_df = pandas.DataFrame({'n_position': n_position})
		for ch in sorted(set(data['n_channel'])):
			data_grouped_by_n_position_for_one_channel_one_pulse = data.loc[(data['n_channel']==ch)&(data['n_pulse']==n_pulse)].groupby(['n_position'])
			normalized_collected_charge_df[f'n_channel {ch} n_pulse {n_pulse} average'] = data_grouped_by_n_position_for_one_channel_one_pulse.mean()['Collected charge (V s)']
			normalized_collected_charge_df[f'n_channel {ch} n_pulse {n_pulse} std'] = data_grouped_by_n_position_for_one_channel_one_pulse.std()['Collected charge (V s)']
			normalized_collected_charge_df[f'n_channel {ch} n_pulse {n_pulse} average'] -= normalized_collected_charge_df[f'n_channel {ch} n_pulse {n_pulse} average'].min()
			normalization_factor = normalized_collected_charge_df[f'n_channel {ch} n_pulse {n_pulse} average'].max()
			normalized_collected_charge_df[f'n_channel {ch} n_pulse {n_pulse} average'] /= normalization_factor
			normalized_collected_charge_df[f'n_channel {ch} n_pulse {n_pulse} std'] /= normalization_factor
			fig.errorband(
				distance,
				y = normalized_collected_charge_df[f'n_channel {ch} n_pulse {n_pulse} average'],
				lower = normalized_collected_charge_df[f'n_channel {ch} n_pulse {n_pulse} std'],
				higher = normalized_collected_charge_df[f'n_channel {ch} n_pulse {n_pulse} std'],
				label = f'CH {ch}',
				marker = '.',
			)
		
		
		for ch_A in sorted(set(data['n_channel'])):
			for ch_B in sorted(set(data['n_channel'])):
				if ch_A == ch_B:
					continue
				fig = grafica.new(
					title = f'Sum of channels {ch_A} and {ch_B} n_pulse {n_pulse}',
					subtitle = f'Data set: {bureaucrat.measurement_name}',
					xlabel = 'Distance (m)',
					ylabel = 'Normalized collected charge',
				)
				for ch in [ch_A,ch_B]:
					fig.errorband(
						distance,
						y = normalized_collected_charge_df[f'n_channel {ch} n_pulse {n_pulse} average'],
						lower = normalized_collected_charge_df[f'n_channel {ch} n_pulse {n_pulse} std'],
						higher = normalized_collected_charge_df[f'n_channel {ch} n_pulse {n_pulse} std'],
						label = f'CH {ch}',
						marker = '.',
					)
				summed_charge_mean = normalized_collected_charge_df[f'n_channel {ch_A} n_pulse {n_pulse} average'] + normalized_collected_charge_df[f'n_channel {ch_B} n_pulse {n_pulse} average']
				summed_charge_std = normalized_collected_charge_df[f'n_channel {ch_A} n_pulse {n_pulse} std'] + normalized_collected_charge_df[f'n_channel {ch_B} n_pulse {n_pulse} std']
				fig.errorband(
					distance,
					y = summed_charge_mean,
					lower = summed_charge_std,
					higher = summed_charge_std,
					label = f'CH {ch_A} + CH {ch_B}',
					marker = '.',
				)
		grafica.save_unsaved(mkdir = bureaucrat.processed_data_dir_path/Path('error band plots'))
	
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

