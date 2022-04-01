from bureaucrat.Bureaucrat import Bureaucrat # https://github.com/SengerM/bureaucrat
import numpy as np
from pathlib import Path
import plotly.express as px
import pandas
from grafica.plotly_utils.utils import line
from .plot_everything_from_1D_scan import mean_std

def script_core(directory):
	bureaucrat = Bureaucrat(
		directory,
		variables = locals(),
	)
	
	measured_data_df = pandas.read_feather(
		bureaucrat.processed_by_script_dir_path('scan_laser_intensity.py')/Path('measured_data.fd'),
	)
	
	GROUP_BY = ['n_DAC','n_channel','n_pulse','Laser DAC']
	averaged_df = mean_std(df=measured_data_df, by=GROUP_BY)
	
	mean_std_plots_dir_Path = bureaucrat.processed_data_dir_path/Path('mean_std_plots')
	mean_std_plots_dir_Path.mkdir(parents=True, exist_ok=True)
	
	for column in averaged_df:
		if column in GROUP_BY:
			continue
		fig = line(
			data_frame = averaged_df,
			x = 'Laser DAC',
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
	for column in measured_data_df:
		if column in GROUP_BY + ['When']:
			continue
		fig = line(
			data_frame = averaged_df,
			x = 'Laser DAC',
			y = f'{column} mean',
			error_y = f'{column} std',
			error_y_mode = 'band',
			color = 'n_channel',
			line_dash = 'n_pulse',
			symbol = 'n_pulse',
			markers = True,
			title = f'{column}<br><sup>Measurement: {bureaucrat.measurement_name}</sup>',
		)
		fig.write_html(str(error_band_plots_dir_Path/Path(f'{column}.html')), include_plotlyjs='cdn')
	
	average_waveforms_df = pandas.read_feather(bureaucrat.processed_by_script_dir_path('scan_laser_intensity.py')/Path('average_waveforms.fd'))
	fig = line(
		title = f'Waveforms<br><sup>Measurement {bureaucrat.measurement_name}</sup>',
		data_frame = average_waveforms_df,
		x = 'Time (s)',
		y = 'Amplitude mean (V)',
		color = 'n_pulse',
		animation_frame = 'n_DAC',
		facet_row = 'n_channel',
	)
	fig.update_yaxes(range=[average_waveforms_df['Amplitude mean (V)'].min(), average_waveforms_df['Amplitude mean (V)'].max()])
	fig.update_layout(transition={'duration': 1})
	fig.write_html(str(bureaucrat.processed_data_dir_path/Path('waveforms.html')), include_plotlyjs='cdn')
	
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

