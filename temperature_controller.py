import EasySensirion # https://github.com/SengerM/EasySensirion
from ElectroAutomatikGmbHPy.ElectroAutomatikGmbHPowerSupply import ElectroAutomatikGmbHPowerSupply # https://github.com/SengerM/ElectroAutomatikGmbHPy
from simple_pid import PID
from time import sleep
import atexit
import threading

PID_SAMPLE_TIME = 1

class TemperatureController:
	def __init__(self):
		self._temperature_humidity_sensor = EasySensirion.SensirionSensor()
		self._peltier_DC_power_supply = ElectroAutomatikGmbHPowerSupply('/dev/ttyACM3')
		
		# Threading locks ---
		self._temperature_humidity_sensor_lock = threading.RLock()
		self._peltier_DC_power_supply_lock = threading.RLock()
		
		# PID to control temperature ---
		self.temperature_pid = PID(-.5,-.1,-2)
		self.temperature_pid.sample_time = PID_SAMPLE_TIME
		self.temperature_pid.output_limits = (0, 4.2) # Will control the current in Ampere.
		self.temperature_pid.setpoint = 22 # Default value.
		
		def at_exit():
			self.stop()
			sleep(.5) # Transcient...
			print(f'Peltier array is: {repr(self.peltier_status)}. I_peltier = {self.peltier_measured_current:.2f} A, V_peltier = {self.peltier_measured_voltage:.2f} V.')
		atexit.register(at_exit)
	
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
		if not -25 <= celsius <= 25:
			raise ValueError(f'Temperature must be within -25 °C and 25 °C, received {celsius} °C.')
		self.temperature_pid.setpoint = celsius
	
	@property
	def status(self):
		"""Returns 'on' or 'off'."""
		return self._temperature_control_status if hasattr(self, '_temperature_control_status') else 'off' # Start off by default.
	
	def stop(self):
		"""Stops the controller and turn off everything related to the peltiers."""
		with self._peltier_DC_power_supply_lock:
			self._peltier_DC_power_supply.enable_output(False)
	
	def start(self):
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
				sleep(PID_SAMPLE_TIME)
			self._temperature_control_status = 'off'
		temperature_control_thread = threading.Thread(target=temperature_control_thread_function)
		temperature_control_thread.start()
	
	def print_report(self):
		print(f'Controller status: {repr(self.status)}')
		print(f'T_set = {self.temperature_setpoint} °C | T_meas = {self.temperature:.2f} °C')
		print(f'I_meas = {self.peltier_measured_current:.2f} A | V_meas = {self.peltier_measured_voltage:.2f} V Peltier = {repr(self.peltier_status)}')

if __name__ == '__main__':
	controller = TemperatureController()

	print(f'Temperature system is {controller.status}')

	controller.temperature_setpoint = 19
	controller.start()
	print(f'Temperature control system is {controller.status} with setpoint = {controller.temperature_setpoint} °C')
	while True:
		controller.print_report()
		new_setpoint = input('New setpoint? ')
		if new_setpoint != '':
			controller.temperature_setpoint = float(new_setpoint)
