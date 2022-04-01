import numpy as np
from scan_1D import script_core as scan_1D
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
LASER_DAC = int(2000/3300*2**10)
N_TRIGGERS_PER_POSITION = 55
BIAS_VOLTAGES = [int(V) for V in utils.interlace(np.linspace(111,500,4))] + list(np.linspace(522,650,6).astype(int))

print(f'Bias voltages = {BIAS_VOLTAGES}')
if input(f'Continue? (YeS) : ') != 'YeS':
	raise ValueError(f'The input was not `YeS`.')

STEP_SIZE = 1e-6
SWEEP_LENGTH = 333e-6

with open(tct_scripts_config.CURRENT_DETECTOR_CENTER_FILE_PATH, 'r') as ifile:
	center = {}
	for line in ifile:
		center[line.split('=')[0].replace(' ','')] = float(line.split('=')[-1])
center = tuple([center[k] for k in sorted(center.keys())]) # Sorted x y z
X_MIDDLE = center[0]
Y_MIDDLE = center[1]
Z_FOCUS = center[2]

the_setup = TheSetup()

the_setup.current_compliance = 100e-6

device_name = input('Device name? ').replace(' ','_')

bureaucrat = Bureaucrat(
	tct_scripts_config.DATA_STORAGE_DIRECTORY_PATH/Path(f'{device_name}_sweeping_bias_voltage'),
	variables = locals(),
	new_measurement = True,
)
time.sleep(1)

if 'preview' in bureaucrat.measurement_name.lower():
	print(f'PREVIEW MODE!!!!')
	STEP_SIZE = 11e-6
	BIAS_VOLTAGES = [111]
	N_TRIGGERS_PER_POSITION = 22

reporter = TelegramReporter(
	telegram_token = my_telegram_bots.robobot.token, 
	telegram_chat_id = my_telegram_bots.chat_ids['Robobot TCT setup'],
)

################################
ANGLE = np.pi/4
x_positions = X_MIDDLE + np.linspace(-SWEEP_LENGTH/2,SWEEP_LENGTH/2,int(SWEEP_LENGTH/STEP_SIZE))*np.sin(ANGLE)
y_positions = Y_MIDDLE - np.linspace(-SWEEP_LENGTH/2,SWEEP_LENGTH/2,int(SWEEP_LENGTH/STEP_SIZE))*np.sin(ANGLE)
z_positions = Z_FOCUS + x_positions*0
positions = list(zip(x_positions,y_positions,z_positions))

with reporter.report_for_loop(len(x_positions)*N_TRIGGERS_PER_POSITION*len(BIAS_VOLTAGES), f'{bureaucrat.measurement_name}') as reporter:
	with open(bureaucrat.processed_data_dir_path/Path(f'README.txt'),'w') as ofile:
		print(f'This measurement created automatically all the following measurements:',file=ofile)
	for idx, bias_voltage in enumerate(BIAS_VOLTAGES):
		utils.adjust_oscilloscope_vdiv_for_TILGAD(
			the_setup = the_setup, 
			laser_DAC = LASER_DAC, 
			bias_voltage = bias_voltage, 
			oscilloscope_channels = OSCILLOSCOPE_CHANNELS, 
			positions = positions,
		)
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
