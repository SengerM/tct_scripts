import numpy as np
from scan_1D import script_core as scan_1D
from TheSetup import TheSetup
import pandas
from pathlib import Path
from data_processing_bureaucrat.Bureaucrat import Bureaucrat, TelegramReportingInformation # https://github.com/SengerM/data_processing_bureaucrat
from progressreporting.TelegramProgressReporter import TelegramReporter # https://github.com/SengerM/progressreporting
import plotly.express as px
import time

OSCILLOSCOPE_CHANNELS = [1,2]
LASER_DAC = 2000
N_TRIGGERS_PER_POSITION = 55
BIAS_VOLTAGES = [288,250,222,199,155,111,77,55]
X_MIDDLE = 2.061416015625e-3
Y_MIDDLE = 9.699013671874999e-3
Z_FOCUS = 52.2831640625e-3
STEP_SIZE = .5e-6
SWEEP_LENGTH = 333e-6

y_positions = Y_MIDDLE + np.linspace(-SWEEP_LENGTH/2,SWEEP_LENGTH/2,int(SWEEP_LENGTH/STEP_SIZE))
x_positions = X_MIDDLE + y_positions*0
z_positions = Z_FOCUS + x_positions*0

positions = list(zip(x_positions,y_positions,z_positions))

the_setup = TheSetup()

device_name = input('Device name? ')

bureaucrat = Bureaucrat(
	Path(f'C:/Users/tct_cms/Desktop/TCT_measurements_data')/Path(f'{device_name}_sweeping_bias_voltage'),
	variables = locals(),
	new_measurement = True,
)
time.sleep(1)

reporter = TelegramReporter(
	telegram_token = TelegramReportingInformation().token, 
	telegram_chat_id = TelegramReportingInformation().chat_id,
)

with reporter.report_for_loop(len(x_positions)*N_TRIGGERS_PER_POSITION*len(BIAS_VOLTAGES), f'{bureaucrat.measurement_name}') as reporter:
	with open(bureaucrat.processed_data_dir_path/Path(f'README.txt'),'w') as ofile:
		print(f'This measurement created automatically all the following measurements:',file=ofile)
	for bias_voltage in BIAS_VOLTAGES:
		# Adjust oscilloscope's vertical scale ---
		print(f'Preparing to adjust oscilloscope VDIV...')
		print(f'Turning laser on...')
		the_setup.laser_DAC = LASER_DAC
		the_setup.laser_status = 'on'
		print(f'Setting bias voltage to {bias_voltage} V...')
		the_setup.bias_voltage = bias_voltage
		current_vdiv = 1e-3 # Start with the smallest scale.
		for channel in OSCILLOSCOPE_CHANNELS:
			the_setup.set_oscilloscope_vdiv(channel, current_vdiv)
		the_setup.move_to(*positions[int(len(positions)*2/5)]) # Left pixel position.
		n_signals_without_NaN = 0
		NUMBER_OF_SIGNALS_UNTIL_WE_CONSIDER_WE_ARE_IN_THE_RIGHT_SCALE = 99
		while n_signals_without_NaN < NUMBER_OF_SIGNALS_UNTIL_WE_CONSIDER_WE_ARE_IN_THE_RIGHT_SCALE:
			print(f'Trying with VDIV = {current_vdiv} V/div... Attempt {n_signals_without_NaN+1} out of {NUMBER_OF_SIGNALS_UNTIL_WE_CONSIDER_WE_ARE_IN_THE_RIGHT_SCALE}.')
			the_setup.wait_for_trigger()
			volts = {}
			error_in_acquisition = False
			for n_channel in OSCILLOSCOPE_CHANNELS:
				try:
					raw_data = the_setup.get_waveform(channel = n_channel)
				except Exception as e:
					print(f'Cannot get data from oscilloscope, reason: {e}')
					error_in_acquisition = True
				volts[n_channel] = raw_data['Amplitude (V)']
			if error_in_acquisition:
				continue
			if any(np.isnan(sum(volts[ch])) for ch in volts): # This means the scale is still too small.
				n_signals_without_NaN = 0
				current_vdiv *= 1.1
				print(f'Scale is still too small, increasing to {current_vdiv} V/div')
				for channel in OSCILLOSCOPE_CHANNELS:
					the_setup.set_oscilloscope_vdiv(channel, current_vdiv)
			else:
				print(f'Signals without NaN! :)')
				n_signals_without_NaN += 1
		reporter.warn('Check oscilloscope vertical auto-scale!')
		the_setup._osc.set_trig_mode('norm')
		input('Press enter to confirm scale of left pad, otherwise manually adjust scale and then press enter.')
		the_setup.move_to(*positions[int(len(positions)*3/5)]) # Left pixel position.
		input('Press enter to confirm scale of right pad, otherwise manually adjust scale and then press enter.')
		# ----------------------------------------
		measurement_base_path = scan_1D(
			measurement_name = f'{device_name}_1DScan_{bias_voltage}V',
			the_setup = the_setup,
			bias_voltage = bias_voltage,
			laser_DAC = LASER_DAC,
			positions = positions,
			n_triggers = N_TRIGGERS_PER_POSITION,
			acquire_channels = OSCILLOSCOPE_CHANNELS,
			two_pulses = True,
			external_Telegram_reporter = reporter,
		)
		with open(bureaucrat.processed_data_dir_path/Path(f'README.txt'),'a') as ofile:
			print(measurement_base_path.parts[-1],file=ofile)
