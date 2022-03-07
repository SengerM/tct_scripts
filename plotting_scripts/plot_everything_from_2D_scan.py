from data_processing_bureaucrat.Bureaucrat import Bureaucrat
import numpy as np
from pathlib import Path
import pandas
import plotly.graph_objects as go

def script_core(directory):
	bureaucrat = Bureaucrat(
		directory,
		variables = locals(),
	)
	
	try:
		measured_data_df = pandas.read_feather(bureaucrat.processed_by_script_dir_path('scan_2D.py')/Path('measured_data.fd'))
	except FileNotFoundError:
		measured_data_df = pandas.read_csv(bureaucrat.processed_by_script_dir_path('scan_2D.py')/Path('measured_data.csv'))
	
	mean_df = measured_data_df.groupby(by=['n_position_1','n_position_2','n_channel','n_pulse']).mean()
	mean_df = mean_df.reset_index()
	for col in sorted(measured_data_df.columns):
		if col in {'n_position','n_position_1','n_position_2','n_channel','n_pulse','n_trigger','index'}:
			continue
		for n_channel in set(measured_data_df['n_channel']):
			for n_pulse in set(measured_data_df['n_pulse']):
				df = mean_df.query(f'n_channel=={n_channel}')
				df = df.query(f'n_pulse=={n_pulse}')
				df = pandas.pivot_table(
					df,
					index = 'n_position_1',
					columns = 'n_position_2',
				)
				try:
					df[col]
				except KeyError:
					continue
				fig = go.Figure()
				figure_name = f'{col} mean value n_channel {n_channel} n_pulse {n_pulse}'
				fig.update_layout(
					title = f'{figure_name}<br><sup>Measurement: {bureaucrat.measurement_name}</sup>',
					xaxis_title = 'n_position_1',
					yaxis_title = 'n_position_2',
				)
				fig.add_trace(
					go.Heatmap(
						x = df.index.tolist(),
						y = df[col].columns.tolist(),
						z = df[col].values.tolist(),
						hovertemplate = f'n<sub>1</sub>: %{{x}}, n<sub>2</sub>: %{{y}}<br>{col}: %{{z}}',
						name = '',
						colorbar = dict(title = col),
					)
				)
				fig.update_yaxes(
					scaleanchor = "x",
					scaleratio = 1,
				)
				fig.write_html(
					str(bureaucrat.processed_data_dir_path/Path(f'{figure_name}.html')),
					include_plotlyjs = 'cdn',
				)
	
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

