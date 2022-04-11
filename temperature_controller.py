import EasySensirion # https://github.com/SengerM/EasySensirion
import ElectroAutomatikGmbHPy
from ElectroAutomatikGmbHPy.ElectroAutomatikGmbHPowerSupply import ElectroAutomatikGmbHPowerSupply # https://github.com/SengerM/ElectroAutomatikGmbHPy
from simple_pid import PID
from time import sleep
import atexit
import threading
import Pyro5.api
import Pyro5.errors
from progressreporting.TelegramProgressReporter import TelegramReporter # https://github.com/SengerM/progressreporting
import my_telegram_bots
import datetime
import tkinter as tk
import tkinter.messagebox
import tkinter.font as tkFont
import threading
import time

THREADS_SLEEP_SECONDS = 1

@Pyro5.api.expose
@Pyro5.api.behavior(instance_mode="single")
class TemperatureController:
	def __init__(self, temperature_low_limit=-25, temperature_high_limit=25):
		self._temperature_humidity_sensor = EasySensirion.SensirionSensor()
		
		list_of_Elektro_Automatik_devices_connected = ElectroAutomatikGmbHPy.find_elektro_automatik_devices()
		if len(list_of_Elektro_Automatik_devices_connected) == 1:
			self._peltier_DC_power_supply = ElectroAutomatikGmbHPowerSupply(list_of_Elektro_Automatik_devices_connected[0]['port'])
		else:
			raise RuntimeError(f'Cannot autodetect the Elektro-Automatik power source because eiter it is not connected to the computer or there is more than one Elektro-Automatik device connected.')
		
		# Threading locks ---
		self._temperature_humidity_sensor_lock = threading.RLock()
		self._peltier_DC_power_supply_lock = threading.RLock()
		
		# PID to control temperature ---
		self.temperature_pid = PID(-.5,-.1,-2)
		self.temperature_pid.sample_time = THREADS_SLEEP_SECONDS
		self.temperature_pid.output_limits = (0, 4.2) # Will control the current in Ampere.
		self.temperature_pid.setpoint = 22 # Default value.
		
		if not isinstance(temperature_low_limit, (int, float)):
			raise TypeError(f'`temperature_low_limit` must be a number, received {repr(temperature_low_limit)} of type {type(temperature_low_limit)}.')
		if not isinstance(temperature_high_limit, (int, float)):
			raise TypeError(f'`temperature_high_limit` must be a number, received {repr(temperature_high_limit)} of type {type(temperature_high_limit)}.')
		if temperature_low_limit >= temperature_high_limit:
			raise ValueError(f'`temperature_low_limit` must be less than `temperature_high_limit`.')
		self._temperature_low_limit = temperature_low_limit
		self._temperature_high_limit = temperature_high_limit
		
		def at_exit():
			self.stop()
			sleep(.5) # Transcient...
			print(f'Peltier array is: {repr(self.peltier_status)}. I_peltier = {self.peltier_measured_current:.2f} A, V_peltier = {self.peltier_measured_voltage:.2f} V.')
			self._is_monitor_temperature_overheat = False
			sleep(THREADS_SLEEP_SECONDS*1.1) # So the threads have time to finish.
		atexit.register(at_exit)
		
		self.start_temperature_monitoring_overheat() # Run it automatically because it is a safety measure.
	
	# Temperature and humidity sensor ----------------------------------
	
	@property
	def temperature(self):
		"""Returns a reading of the temperature as a float number in Celsius."""
		with self._temperature_humidity_sensor_lock:
			return self._temperature_humidity_sensor.temperature
	
	@property
	def humidity(self):
		"""Returns a reading of the humidity as a float number in %RH."""
		with self._temperature_humidity_sensor_lock:
			return self._temperature_humidity_sensor.humidity
	
	# Peltier ----------------------------------------------------------
	
	@property
	def peltier_set_voltage(self):
		"""Return the set voltage of the Peltier array, in volt as a float number."""
		with self._peltier_DC_power_supply_lock:
			return self._peltier_DC_power_supply.set_voltage_value
	
	@property
	def peltier_set_current(self):
		"""Return the set current of the Peltier array, in ampere as a float number."""
		with self._peltier_DC_power_supply_lock:
			return self._peltier_DC_power_supply.set_current_value
	
	@property
	def peltier_measured_voltage(self):
		"""Return the measured voltage of the Peltier array, in volt as a float number."""
		with self._peltier_DC_power_supply_lock:
			return self._peltier_DC_power_supply.measured_voltage
	
	@property
	def peltier_measured_current(self):
		"""Return the measured current of the Peltier array, in ampere as a float number."""
		with self._peltier_DC_power_supply_lock:
			return self._peltier_DC_power_supply.measured_current
	
	@property
	def peltier_status(self):
		"""Return 'on' or 'off'."""
		with self._peltier_DC_power_supply_lock:
			return self._peltier_DC_power_supply.output
	
	@property
	def temperature_setpoint(self):
		"""Return the temperature setpoint in °C."""
		return self.temperature_pid.setpoint
	@temperature_setpoint.setter
	def temperature_setpoint(self, celsius):
		"""Set the temperature setpoint in °C."""
		if not isinstance(celsius, (int, float)):
			raise TypeError(f'Temperature must be a float number, received {repr(celsius)} of type {type(celsius)}.')
		if not self.temperature_low_limit <= celsius <= self.temperature_high_limit:
			raise ValueError(f'Temperature must be within {self.temperature_low_limit} °C and {self.temperature_high_limit} °C, received {celsius} °C.')
		self.temperature_pid.setpoint = celsius
	
	@property
	def status(self):
		"""Returns 'on' or 'off'."""
		return self._temperature_control_status if hasattr(self, '_temperature_control_status') else 'off' # Start off by default.
	
	@property
	def temperature_low_limit(self):
		"""Return the current temperature low limit."""
		return self._temperature_low_limit
	@temperature_low_limit.setter
	def temperature_low_limit(self, celsius):
		"""Set the temperature low limit."""
		if not isinstance(celsius, (int, float)):
			raise TypeError(f'Must be a number, received {repr(celsius)} of type {type(celsius)}.')
		if celsius > self.temperature_high_limit:
			raise ValueError(f'The current `temperature_high_limit` is {self.temperature_high_limit}, cannot set `temperature_low_limit` to {celsius} which is higher than that.')
		self._temperature_low_limit = celsius
	
	@property
	def temperature_high_limit(self):
		"""Return the current temperature high limit."""
		return self._temperature_high_limit
	@temperature_high_limit.setter
	def temperature_high_limit(self, celsius):
		"""Set the temperature high limit."""
		if not isinstance(celsius, (int, float)):
			raise TypeError(f'Must be a number, received {repr(celsius)} of type {type(celsius)}.')
		if celsius < self.temperature_low_limit:
			raise ValueError(f'The current `temperature_low_limit` is {self.temperature_low_limit}, cannot set `temperature_high_limit` to {celsius} which is lower than that.')
		self._temperature_high_limit = celsius
	
	def stop(self):
		"""Stops the controller and turn off everything related to the peltiers."""
		with self._peltier_DC_power_supply_lock:
			self._peltier_DC_power_supply.enable_output(False)
	
	def start(self):
		"""Turn on the Peltier cells and start the temperature control."""
		if self.status == 'on': # Do nothing.
			return
		def temperature_control_thread_function():
			self._temperature_control_status = 'on'
			with self._peltier_DC_power_supply_lock:
				self._peltier_DC_power_supply.set_voltage_value = 30
				self._peltier_DC_power_supply.enable_output(True) # Turn the power supply on.
			sleep(.5) # Transients.
			while self.peltier_status == 'on': # Operate as long as nobody turn the Peltier cells off...
				new_current = self.temperature_pid(self.temperature)
				with self._peltier_DC_power_supply_lock:
					self._peltier_DC_power_supply.set_current_value = new_current # Update the current.
				sleep(THREADS_SLEEP_SECONDS)
			self._temperature_control_status = 'off'
		temperature_control_thread = threading.Thread(target=temperature_control_thread_function)
		temperature_control_thread.start()
	
	def start_cooling_sequence(self):
		print('Starting cooling sequence... Please wait until I tell you it is ready to use!')
		self.temperature_setpoint = 5
		self.start()
		print(f'Cooling down to {self.temperature_setpoint} °C and waiting humidity to decrease...')
		while self.temperature > self.temperature_setpoint+1 or self.humidity > 5:
			print(f'T = {self.temperature} °C, H = {self.humidity} %RH')
			sleep(1)
		self.temperature_setpoint = -20
		print(f'Humidity is under control, now cooling down to {self.temperature_setpoint} °C...')
		while self.temperature > -20:
			print(f'T = {self.temperature} °C, H = {self.humidity} %RH')
			sleep(1)
		print(f'Temperature is {self.temperature} °C. You can start using the system :)')
	
	def get_status_summary(self):
		"""Return a string for quick checking the status of the system."""
		report_string = ''
		report_string += f'Controller status: {repr(self.status)}'
		report_string += '\n'
		report_string += f'T_set = {self.temperature_setpoint} °C | T_meas = {self.temperature:.2f} °C'
		report_string += '\n'
		report_string += f'Peltier = {repr(self.peltier_status)}, I_measured = {self.peltier_measured_current:.2f} A | V_measured = {self.peltier_measured_voltage:.2f} V'
		return report_string
	
	def start_temperature_monitoring_overheat(self):
		"""Start a background thread constantly monitoring that temperature is not outside range and sending notifications to Telegram."""
		if hasattr(self, '_is_monitor_temperature_overheat') and self._is_monitor_temperature_overheat == True:
			return # This means that it is already running, don't want to run it twice.
		def _temperature_monitoring_overheat_thread_function():
			telegram_reporter = TelegramReporter(
				telegram_token = my_telegram_bots.robobot.token, # Here I store the token of my bot hidden, never make it public.
				telegram_chat_id = my_telegram_bots.chat_ids['TCT setup temperature controller'],
			)
			response = telegram_reporter.send_message('Initializing temperature monitoring system...')
			message_id = response['result']['message_id']
			last_report_to_telegram = datetime.datetime.now()
			while self._is_monitor_temperature_overheat == True:
				if (datetime.datetime.now()-last_report_to_telegram).seconds > 10:
					cadena = f'TCT temperature controller 🌡️\n'
					cadena += f'Status: {repr(self.status)}\n'
					cadena += f'T_set = {self.temperature_setpoint:.2f} °C\n'
					cadena += f'T_meas = {self.temperature:.2f} °C\n'
					cadena += f'Peltier {repr(self.peltier_status)}, I = {self.peltier_measured_current:.2f} A | V = {self.peltier_measured_voltage:.2f} V\n'
					cadena += f'Humidity = {self.humidity:.2f} %RH\n'
					cadena += f'\nLast update: {datetime.datetime.now()}'
					telegram_reporter.edit_message(
						cadena,
						message_id = message_id,
					)
					last_report_to_telegram = datetime.datetime.now()
				if self.status == 'on' and not self.temperature_low_limit <= self.temperature <= self.temperature_high_limit:
					self.stop() # Turn things off as the Peltiers are the only source of power, if temperature is high the problem is here.
					telegram_reporter.send_message(
						f'❗ ATTENTION REQUIRED\nTurned off controller because temperature T_measured = {self.temperature:.2f} °C was outside range T_low = {self.temperature_low_limit:.2f} and T_high = {self.temperature_high_limit:.2f} °C.',
						reply_to_message_id = message_id,
					)
				sleep(THREADS_SLEEP_SECONDS)
			telegram_reporter.edit_message(
				f'Finished...',
				message_id = message_id,
			)
		temperature_monitoring_thread = threading.Thread(target=_temperature_monitoring_overheat_thread_function)
		self._is_monitor_temperature_overheat = True
		temperature_monitoring_thread.start()

SERVER_NAME = 'temperature_controller'

def run_as_daemon():
	# https://pyro5.readthedocs.io/en/latest/intro.html#with-a-name-server
	print('Starting daemon...')
	daemon = Pyro5.server.Daemon()
	ns = Pyro5.api.locate_ns()
	uri = daemon.register(TemperatureController)
	ns.register(SERVER_NAME, uri)
	print("Temperature controller ready to start working!")
	daemon.requestLoop()

class TemperatureControllerDisplay(tk.Frame):
	def __init__(self, parent, temperature_controller:TemperatureController, temperature_controller_lock, *args, **kwargs):
		tk.Frame.__init__(self, parent, *args, **kwargs)
		self.parent = parent
		self._auto_update_interval = 1 # seconds
		self._temperature_controller = temperature_controller
		self._temperature_controller_lock = temperature_controller_lock
		
		self.list_of_parameters = [
			'Set temperature (°C)',
			'Measured temperature (°C)',
			'Measured humidity (%RH)',
			'Peltier voltage (V)',
			'Peltier current (A)'
		]
		self.getters_dict = {
			'Set temperature (°C)': lambda: self._temperature_controller.temperature_setpoint,
			'Measured temperature (°C)': lambda: self._temperature_controller.temperature,
			'Measured humidity (%RH)': lambda: self._temperature_controller.humidity,
			'Peltier voltage (V)': lambda: self._temperature_controller.peltier_measured_voltage,
			'Peltier current (A)': lambda: self._temperature_controller.peltier_measured_current,
		}
		
		self.tk_labels = {}
		for param in self.list_of_parameters:
			frame = tk.Frame(self)
			frame.grid(pady=10)
			tk.Label(frame, text = f'{param}: ').grid()
			self.tk_labels[param] = tk.Label(frame, text = '?')
			self.tk_labels[param].grid()
		
		self.automatic_display_update('on')
	
	def update_display(self):
		with self._temperature_controller_lock:
			self._temperature_controller._pyroClaimOwnership()
			for parameter in self.list_of_parameters:
				self.tk_labels[parameter].config(text = f'{self.getters_dict[parameter]():.2f}')
	
	def automatic_display_update(self, status):
		if not isinstance(status, str):
			raise TypeError(f'<status> must be a string, received {status} of type {type(status)}.')
		if status.lower() not in ['on','off']:
			raise ValueError(f'<status> must be either "on" or "off", received {status}.')
		self._automatic_display_update_status = status
		if hasattr(self, '_automatic_display_update_is_running') and self._automatic_display_update_is_running == 'yes':
			return
		
		def thread_function():
			self._automatic_display_update_is_running = 'yes'
			while self._automatic_display_update_status == 'on':
				try:
					self.update_display()
				except Exception as e:
					print(f'Cannot update display, reason: {repr(e)}')
				time.sleep(self._auto_update_interval)
			self._automatic_display_update_is_running == 'no'
		
		self._automatic_display_update_thread = threading.Thread(target = thread_function)
		self._automatic_display_update_thread.start()

if __name__ == "__main__":
	import argparse
	
	parser = argparse.ArgumentParser()
	parser.add_argument(
		'--daemon',
		help = 'Use this option to run the daemon.',
		dest = 'daemon',
		action = 'store_true'
	)
	
	args = parser.parse_args()
	if args.daemon == True:
		print('Running in daemon mode...')
		try:
			run_as_daemon()
		except Pyro5.errors.NamingError:
			print(f'Before running this you have to open a new terminal and run `python3 -m Pyro5.nameserver`, and keep it running. See *https://pyro5.readthedocs.io/en/latest/intro.html#with-a-name-server* for more info.')
	else:
		print('Running the graphical interface mode...')
		try:
			temperature_controller = Pyro5.api.Proxy('PYRONAME:temperature_controller')
			temperature_controller._pyroBind()
			temperature_controller_lock = threading.RLock()
		except Pyro5.errors.CommunicationError:
			print(f'Cannot find an instance of the temperature controller running in the background as a daemon. Before running the graphical interface, you should run a daemon instance with the option `--daemon`.')
			exit()
		
		root = tk.Tk()
		root.title('TCT temperature controller')
		default_font = tkFont.nametofont("TkDefaultFont")
		default_font.configure(size=16)
		main_frame = tk.Frame(root)
		main_frame.grid(padx=20,pady=20)
		tk.Label(main_frame, text = 'TCT temperature controller', font=("Calibri",22)).grid()
		display = TemperatureControllerDisplay(
			main_frame, 
			temperature_controller = temperature_controller, 
			temperature_controller_lock = temperature_controller_lock
		)
		display.grid(pady=20)
		
		def on_closing():
			display.automatic_display_update('off')
			root.destroy()
		root.protocol("WM_DELETE_WINDOW", on_closing)
		
		root.mainloop()
