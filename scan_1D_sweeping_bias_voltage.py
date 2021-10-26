import numpy as np
from scan_1D import script_core as scan_1D
from TheSetup import TheSetup
import pandas
from pathlib import Path
from data_processing_bureaucrat.Bureaucrat import Bureaucrat, TelegramReportingInformation # https://github.com/SengerM/data_processing_bureaucrat
from progressreporting.TelegramProgressReporter import TelegramReporter # https://github.com/SengerM/progressreporting
import plotly.express as px
import time

N_TRIGGERS_PER_POSITION = 55
BIAS_VOLTAGES = [222,199,177,155,144,122,99]
X_MIDDLE = -1.478975e-3
Y_MIDDLE = 9.21332e-3
Z_FOCUS = .05219872
STEP_SIZE = .5e-6
SWEEP_LENGTH = 333e-6

x_positions = X_MIDDLE + np.linspace(-SWEEP_LENGTH/2,SWEEP_LENGTH/2,int(SWEEP_LENGTH/STEP_SIZE))
y_positions = Y_MIDDLE + x_positions*0
z_positions = Z_FOCUS + x_positions*0

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
		measurement_base_path = scan_1D(
			measurement_name = f'{device_name}_1DScan_{bias_voltage}V',
			the_setup = the_setup,
			bias_voltage = bias_voltage,
			laser_DAC = 2000,
			positions = list(zip(x_positions,y_positions,z_positions)),
			n_triggers = N_TRIGGERS_PER_POSITION,
			acquire_channels = [1,2],
			two_pulses = True,
			external_Telegram_reporter = reporter,
		)
		with open(bureaucrat.processed_data_dir_path/Path(f'README.txt'),'w') as ofile:
			print(measurement_base_path.parts[-1],file=ofile)
