import PyticularsTCT # https://github.com/SengerM/PyticularsTCT
import pyvisa
import TeledyneLeCroyPy # https://github.com/SengerM/TeledyneLeCroyPy
from keithley.Keithley2470 import Keithley2470SafeForLGADs # https://github.com/SengerM/keithley
import EasySensirion # https://github.com/SengerM/EasySensirion
from ElectroAutomatikGmbHPy.ElectroAutomatikGmbHPowerSupply import ElectroAutomatikGmbHPowerSupply # https://github.com/SengerM/ElectroAutomatikGmbHPy
import atexit
from time import sleep

class TheSetup:
	"""This class wraps all the hardware so if there are changes it is easy to adapt."""
	def __init__(self, safe_mode=True):
		self._osc = TeledyneLeCroyPy.LeCroyWaveRunner(pyvisa.ResourceManager().open_resource('USB0::1535::4131::2810N60091::0::INSTR'))
		self._tct = PyticularsTCT.TCT()
		self._keithley = Keithley2470SafeForLGADs('USB0::1510::9328::04481179::0::INSTR', polarity = 'negative')
		self._temperature_humidity_sensor = EasySensirion.SensirionSensor()
		self._peltier_DC_power_supply = ElectroAutomatikGmbHPowerSupply('/dev/ttyACM3')
		
		def at_exit():
			print('Turning bias voltage off...')
			self.bias_output_status = 'off'
			print(f'Bias voltage is: {self.bias_output_status}.')
			print('Turning laser off...')
			self.laser_status = 'off'
			print(f'Laser is: {self.laser_status}.')
			print('Turning Peltier array off...')
			self.peltier_status = 'off'
			sleep(.5) # Transcient...
			print(f'Peltier array is: {self.peltier_status}.')
		if safe_mode == True:
			atexit.register(at_exit)
	
	# Motorized xyz stages ---------------------------------------------
	
	def move_to(self, x=None, y=None, z=None):
		"""Move the TCT stages to the specified position."""
		self._tct.stages.move_to(x=x,y=y,z=z)
	
	@property
	def position(self):
		"""Returns the position of the stages."""
		return self._tct.stages.position
	
	# Laser ------------------------------------------------------------
	
	@property
	def laser_status(self):
		"""Return the laser status "on" or "off"."""
		return self._tct.laser.status
	@laser_status.setter
	def laser_status(self, status):
		"""Set the laser status "on" or "off"."""
		self._tct.laser.status = status
	
	@property
	def laser_DAC(self):
		"""Returns the laser DAC value."""
		return self._tct.laser.DAC
	@laser_DAC.setter
	def laser_DAC(self, value):
		"""Set the value of the DAC for the laser."""
		self._tct.laser.DAC = value
	
	# Bias voltage power supply ----------------------------------------
	
	@property
	def bias_voltage(self):
		"""Returns the measured bias voltage."""
		return self._keithley.measure_voltage()
	@bias_voltage.setter
	def bias_voltage(self, volts):
		"""Sets the bias voltage."""
		self._keithley.set_source_voltage(volts)
	
	@property
	def bias_current(self):
		"""Returns the measured bias current."""
		return self._keithley.measure_current()
	
	@property
	def current_compliance(self):
		"""Returns the current limit of the voltage source."""
		return self._keithley.current_limit
	@current_compliance.setter
	def current_compliance(self, amperes):
		"""Sets the current compliance."""
		self._keithley.current_limit = amperes
	
	@property
	def bias_output_status(self):
		"""Returns either 'on' or 'off'."""
		return self._keithley.output
	@bias_output_status.setter
	def bias_output_status(self, status: str):
		"""Set the bias output either 'on' or 'off'."""
		self._keithley.output = status
	
	# Oscilloscope -----------------------------------------------------
	
	def configure_oscilloscope_for_two_pulses(self):
		"""Configures the horizontal scale and trigger of the oscilloscope to properly acquire two pulses."""
		self._osc.set_trig_source('ext')
		self._osc.set_trig_level('ext', -50e-3)
		self._osc.set_trig_coupling('ext', 'DC')
		self._osc.set_trig_slope('ext', 'negative')
		self._osc.set_tdiv('20ns')
		self._osc.set_trig_delay(-20e-9)
	
	def wait_for_trigger(self):
		"""Blocks execution until there is a trigger in the oscilloscope."""
		self._osc.wait_for_single_trigger()
	
	def get_waveform(self, channel: int):
		"""Gets the waveform from the oscilloscope for the respective channel."""
		return self._osc.get_waveform(channel=channel)
	
	def set_oscilloscope_vdiv(self, channel: int, vdiv: float):
		"""Sets the osciloscope's Volts per division."""
		self._osc.set_vdiv(channel, vdiv)
	
	# Temperature and humidity sensor ----------------------------------
	
	@property
	def temperature(self):
		"""Returns a reading of the temperature as a float number in Celsius."""
		return self._temperature_humidity_sensor.temperature
	
	@property
	def humidity(self):
		"""Returns a reading of the humidity as a float number in %RH."""
		return self._temperature_humidity_sensor.humidity
	
	# Peltier ----------------------------------------------------------
	
	@property
	def peltier_set_voltage(self):
		"""Return the set voltage of the Peltier array, in volt as a float number."""
		return self._peltier_DC_power_supply.set_voltage_value
	@peltier_set_voltage.setter
	def peltier_set_voltage(self, volts):
		"""Set the voltage for the Peltier array, in volt."""
		self._peltier_DC_power_supply.set_voltage_value = volts
	
	@property
	def peltier_set_current(self):
		"""Return the set current of the Peltier array, in ampere as a float number."""
		return self._peltier_DC_power_supply.set_current_value
	@peltier_set_current.setter
	def peltier_set_current(self, amperes):
		"""Set the current for the Peltier array, in ampere."""
		self._peltier_DC_power_supply.set_current_value = amperes
	
	@property
	def peltier_measured_voltage(self):
		"""Return the measured voltage of the Peltier array, in volt as a float number."""
		return self._peltier_DC_power_supply.measured_voltage
	
	@property
	def peltier_measured_current(self):
		"""Return the measured current of the Peltier array, in ampere as a float number."""
		return self._peltier_DC_power_supply.measured_current
	
	@property
	def peltier_status(self):
		"""Return 'on' or 'off'."""
		return self._peltier_DC_power_supply.output
	@peltier_status.setter
	def peltier_status(self, status: str):
		"""Turn on or off the Peltier array power supply."""
		if status == 'on':
			status = True
		elif status == 'off':
			status = False
		else:
			raise ValueError(f'`status` must be "on" or "off".')
		self._peltier_DC_power_supply.enable_output(status)
	
if __name__ == '__main__':
	import time
	
	the_setup = TheSetup()
	
	the_setup.laser_status = 'on'
	the_setup.laser_DAC = 0
	print('Seting vias boltage')
	the_setup.bias_voltage = 66
	print(f'Bias voltage = {the_setup.bias_voltage} V')
	the_setup.configure_oscilloscope_for_two_pulses()
	
	input('Exit?')

