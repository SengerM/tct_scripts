import EasySensirion # https://github.com/SengerM/EasySensirion
from ElectroAutomatikGmbHPy.ElectroAutomatikGmbHPowerSupply import ElectroAutomatikGmbHPowerSupply # https://github.com/SengerM/ElectroAutomatikGmbHPy
from simple_pid import PID
from time import sleep
import atexit
import threading
from Pyro5.api import expose, behavior, serve
from progressreporting.TelegramProgressReporter import TelegramReporter # https://github.com/SengerM/progressreporting
from data_processing_bureaucrat.Bureaucrat import TelegramReportingInformation # Here I hide the token of my bot. Never make it public.
import datetime

THREADS_SLEEP_SECONDS = 1

@expose
@behavior(instance_mode="single")
class TemperatureController:
	def __init__(self, temperature_low_limit=-25, temperature_high_limit=25):
		self._temperature_humidity_sensor = EasySensirion.SensirionSensor()
		self._peltier_DC_power_supply = ElectroAutomatikGmbHPowerSupply('/dev/ttyACM3')
		
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
			sleep(1)
		self.temperature_setpoint = -20
		print(f'Cooling down to {self.temperature_setpoint} °C...')
		while self.temperature > -20:
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
				telegram_token = TelegramReportingInformation().token, # Here I store the token of my bot hidden, never make it public.
				telegram_chat_id = '-785084808',
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
	
def run_as_daemon():
	# https://stackoverflow.com/questions/656933/communicating-with-a-running-python-daemon
	serve(
		{
			TemperatureController: 'temperature_controller'
		},
		use_ns = False, # Would be nice to set this to True but I am getting an error...
	)

if __name__ == "__main__":
	from Pyro5.api import Proxy
	
	run_as_daemon()
	# ~ c = TemperatureController(temperature_low_limit=18)
	# ~ c.temperature_setpoint = 15
	# ~ c.start()
	# ~ while True:
		# ~ print(c.get_status_summary())
		# ~ sleep(1)