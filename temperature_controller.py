import EasySensirion # https://github.com/SengerM/EasySensirion
from ElectroAutomatikGmbHPy.ElectroAutomatikGmbHPowerSupply import ElectroAutomatikGmbHPowerSupply # https://github.com/SengerM/ElectroAutomatikGmbHPy
from simple_pid import PID
from time import sleep
import atexit
import threading

class TemperatureController:
	def __init__(self):
		self._temperature_humidity_sensor = EasySensirion.SensirionSensor()
		self._peltier_DC_power_supply = ElectroAutomatikGmbHPowerSupply('/dev/ttyACM3')
		
		# Threading locks ---
		self._temperature_humidity_sensor_lock = threading.RLock()
		self._peltier_DC_power_supply_lock = threading.RLock()
		
		def at_exit():
			self.turn_off()
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
	
	def turn_off(self):
		"""Turn off everything related to the peltiers."""
		with self._peltier_DC_power_supply_lock:
			self._peltier_DC_power_supply.enable_output(False)
	
	@property
	def temperature_setpoint(self):
		"""Return the temperature setpoint in °C."""
		return self._temperature_setpoint if hasattr(self, '_temperature_setpoint') else 22 # This is the default temperature setpoint.
	@temperature_setpoint.setter
	def temperature_setpoint(self, celsius):
		"""Set the temperature setpoint in °C."""
		if not isinstance(celsius, (int, float)):
			raise TypeError(f'Temperature must be a float number, received {repr(celsius)} of type {type(celsius)}.')
		if not -25 <= celsius <= 25:
			raise ValueError(f'Temperature must be within -25 °C and 25 °C, received {celsius} °C.')
		self._temperature_setpoint = celsius
	
	@property
	def temperature_control_status(self):
		"""Returns 'on' or 'off'."""
		return self._temperature_control_status if hasattr(self, '_temperature_control_status') else 'off' # Start off by default.
	@temperature_control_status.setter
	def temperature_control_status(self, status: str):
		PID_SAMPLE_TIME = 1
		if status not in {'on', 'off'}:
			raise ValueError(f'`status` must be either "on" or "off", received {repr(status)}.')
		if status == 'on' and self.temperature_control_status == 'off': # It has to be turned on.
			self._temperature_control_status = 'on'
			self.temperature_pid = PID(-.5,-.1,-2)
			self.temperature_pid.sample_time = PID_SAMPLE_TIME
			self.temperature_pid.output_limits = (0, 4.2) # Will control the current in Ampere.
			with self._peltier_DC_power_supply_lock:
				self._peltier_DC_power_supply.set_voltage_value = 30
				self._peltier_DC_power_supply.enable_output(True) # Turn the power supply on.
			def temperature_control_thread_function():
				while self._temperature_control_status == 'on' and self.peltier_status == 'on':
					self.temperature_pid.setpoint = self.temperature_setpoint # Update setpoint regularly.
					new_current = self.temperature_pid(self.temperature)
					with self._peltier_DC_power_supply_lock:
						self._peltier_DC_power_supply.set_current_value = new_current # Update the current.
					sleep(PID_SAMPLE_TIME)
				self.turn_off()
				self._temperature_control_status = 'off'
				print(f'Temperature control has finished.')
			temperature_control_thread = threading.Thread(target=temperature_control_thread_function)
			sleep(1) # Any transient.
			temperature_control_thread.start()
		elif status == 'off' and self.temperature_control_status == 'on':
			self._temperature_control_status = 'off'

if __name__ == '__main__':
	controller = TemperatureController()

	print(f'Temperature system is {controller.temperature_control_status}')

	controller.temperature_setpoint = 19
	controller.temperature_control_status = 'on'
	print(f'Temperature control system is {controller.temperature_control_status} with setpoint = {controller.temperature_setpoint} °C')
	while True:
		print(f'T_set = {controller.temperature_setpoint} °C | T_meas = {controller.temperature:.2f} °C | I_meas = {controller.peltier_measured_current:.2f} A | V_meas = {controller.peltier_measured_voltage:.2f} V | I_set = {controller.peltier_set_current:.2f} A | V_set = {controller.peltier_set_voltage:.2f} V | Peltier = {repr(controller.peltier_status)}')
		sleep(1)
