import numpy as np
from scan_1D import script_core as scan_1D, DEVICE_CENTER, SCAN_STEP, SCAN_LENGTH, SCAN_ANGLE_DEG
from TheSetup import TheSetup
import pandas
from pathlib import Path
from bureaucrat.Bureaucrat import Bureaucrat # https://github.com/SengerM/bureaucrat
from progressreporting.TelegramProgressReporter import TelegramReporter # https://github.com/SengerM/progressreporting
import my_telegram_bots
import plotly.express as px
import time
import utils
import tct_scripts_config

OSCILLOSCOPE_CHANNELS = [1,2]
LASER_DAC = 653
N_TRIGGERS_PER_POSITION = 300
BIAS_VOLTAGES = np.linspace(600,900,6) # [int(V) for V in utils.interlace(np.linspace(111,500,22))]

CURRENT_COMPLIANCE = 11e-6

########################################################################

device_name = input('Device name? ').replace(' ','_')
Rick = Bureaucrat(
	tct_scripts_config.DATA_STORAGE_DIRECTORY_PATH/Path(f'{device_name}_sweeping_bias_voltage'),
	variables = locals(),
	new_measurement = True,
)
time.sleep(1)

if 'preview' in Rick.measurement_name.lower():
	print(f'ENTERING INTO PREVIEW MODE!!!!')
	STEP = 11e-6
	BIAS_VOLTAGES = [float(input(f'Bias voltage for preview? '))]
	N_TRIGGERS_PER_POSITION = 4

if input(f'I will use BIAS_VOLTAGES = {BIAS_VOLTAGES} (in volts), is this correct? (YeS) ') != 'YeS':
	print(f'Your answer was not "YeS", I will exit.')
	exit()

x = DEVICE_CENTER['x'] + np.arange(-SCAN_LENGTH/2,SCAN_LENGTH/2, STEP)*np.cos(SCAN_ANGLE_DEG*np.pi/180)
y = DEVICE_CENTER['y'] + np.arange(-SCAN_LENGTH/2,SCAN_LENGTH/2, STEP)*np.sin(SCAN_ANGLE_DEG*np.pi/180)
z = DEVICE_CENTER['z'] + 0*x + 0*y
positions = []
for i in range(len(y)):
	positions.append( [ x[i],y[i],z[i] ] )

the_setup = TheSetup()

the_setup.current_compliance = CURRENT_COMPLIANCE

reporter = TelegramReporter(
	telegram_token = my_telegram_bots.robobot.token, 
	telegram_chat_id = my_telegram_bots.chat_ids['Robobot TCT setup'],
)

with reporter.report_for_loop(len(BIAS_VOLTAGES), f'{Rick.measurement_name}') as reporter:
	with open(Rick.processed_data_dir_path/Path(f'README.txt'),'w') as ofile:
		print(f'This measurement created automatically all the following measurements:',file=ofile)
	for idx, bias_voltage in enumerate(BIAS_VOLTAGES):
		# Automatically find the best vertical scale in the oscilloscope...
		print('Configuring laser...')
		the_setup.laser_DAC = LASER_DAC
		the_setup.laser_status = 'on'
		print('Setting bias voltage...')
		the_setup.bias_voltage = bias_voltage
		the_setup.bias_output_status = 'on'
		the_setup.configure_oscilloscope_for_two_pulses()
		utils.adjust_oscilloscope_vdiv_for_linear_scan_between_two_pixels(
			the_setup,
			oscilloscope_channels = OSCILLOSCOPE_CHANNELS,
			position_of_each_pixel = [
				positions[int(len(positions)*2/6)],
				positions[int(len(positions)*4/6)],
			],
		)
		# Do the measurement...
		measurement_base_path = scan_1D(
			measurement_name = f'{device_name}_1DScan_{bias_voltage}V',
			the_setup = the_setup,
			bias_voltage = bias_voltage,
			laser_DAC = LASER_DAC,
			positions = positions,
			n_triggers = N_TRIGGERS_PER_POSITION,
			acquire_channels = OSCILLOSCOPE_CHANNELS,
		)
		with open(Rick.processed_data_dir_path/Path(f'README.txt'),'a') as ofile:
			print(measurement_base_path.parts[-1],file=ofile)
		reporter.update(1)
