import PyticularsTCT # https://github.com/SengerM/PyticularsTCT
import pyvisa
import TeledyneLeCroyPy # https://github.com/SengerM/TeledyneLeCroyPy
from keithley.Keithley2470 import Keithley2470SafeForLGADs # https://github.com/SengerM/keithley
from Pyro5.api import Proxy
import atexit
from time import sleep
import threading
import tct_scripts_config

class TheSetup:
	"""This class wraps all the hardware so if there are changes it is easy to adapt."""
	def __init__(self, safe_mode=True):
		"""
		- safe_mode: Turns laser and high voltage off when your Python instance is finished using `atexit`. Temperature is not touched.
		"""
		self._oscilloscope = TeledyneLeCroyPy.LeCroyWaveRunner(pyvisa.ResourceManager().open_resource('USB0::1535::4131::2810N60091::0::INSTR'))
		self._tct = PyticularsTCT.TCT(
			x_stage_port = '/dev/ttyACM3',
			y_stage_port = '/dev/ttyACM2',
			z_stage_port = '/dev/ttyACM1',
		)
		self._keithley = Keithley2470SafeForLGADs('USB0::1510::9328::04481179::0::INSTR', polarity = 'negative')
		self._temperature_controller = Proxy(tct_scripts_config.TEMPERATURE_CONTROLLER_URI)
		
		# Threading locks ---
		self._oscilloscope_Lock = threading.RLock()
		self._tct_Lock = threading.RLock()
		self._keithley_Lock = threading.RLock()
		self._temperature_humidity_sensor_Lock = threading.RLock()
		self._peltier_DC_power_supply_Lock = threading.RLock()
		
		def at_exit():
			print('Turning bias voltage off...')
			self.bias_output_status = 'off'
			print(f'Bias voltage is: {self.bias_output_status}.')
			print('Turning laser off...')
			self.laser_status = 'off'
			print(f'Laser is: {self.laser_status}.')
		if safe_mode == True:
			atexit.register(at_exit)
	
	# Motorized xyz stages ---------------------------------------------
	
	def move_to(self, x=None, y=None, z=None):
		"""Move the TCT stages to the specified position."""
		with self._tct_Lock:
			self._tct.stages.move_to(x=x,y=y,z=z)
	
	@property
	def position(self):
		"""Returns the position of the stages."""
		with self._tct_Lock:
			return self._tct.stages.position
	
	# Laser ------------------------------------------------------------
	
	@property
	def laser_status(self):
		"""Return the laser status "on" or "off"."""
		with self._tct_Lock:
			return self._tct.laser.status
	@laser_status.setter
	def laser_status(self, status):
		"""Set the laser status "on" or "off"."""
		with self._tct_Lock:
			self._tct.laser.status = status
	
	@property
	def laser_DAC(self):
		"""Returns the laser DAC value."""
		with self._tct_Lock:
			return self._tct.laser.DAC
	@laser_DAC.setter
	def laser_DAC(self, value):
		"""Set the value of the DAC for the laser."""
		with self._tct_Lock:
			self._tct.laser.DAC = value
	
	# Bias voltage power supply ----------------------------------------
	
	@property
	def bias_voltage(self):
		"""Returns the measured bias voltage."""
		with self._keithley_Lock:
			return self._keithley.measure_voltage()
	@bias_voltage.setter
	def bias_voltage(self, volts):
		"""Sets the bias voltage."""
		with self._keithley_Lock:
			self._keithley.set_source_voltage(volts)
	
	@property
	def bias_current(self):
		"""Returns the measured bias current."""
		with self._keithley_Lock:
			return self._keithley.measure_current()
	
	@property
	def current_compliance(self):
		"""Returns the current limit of the voltage source."""
		with self._keithley_Lock:
			return self._keithley.current_limit
	@current_compliance.setter
	def current_compliance(self, amperes):
		"""Sets the current compliance."""
		with self._keithley_Lock:
			self._keithley.current_limit = amperes
	
	@property
	def bias_output_status(self):
		"""Returns either 'on' or 'off'."""
		with self._keithley_Lock:
			return self._keithley.output
	@bias_output_status.setter
	def bias_output_status(self, status: str):
		"""Set the bias output either 'on' or 'off'."""
		with self._keithley_Lock:
			self._keithley.output = status
	
	# Oscilloscope -----------------------------------------------------
	
	def configure_oscilloscope_for_two_pulses(self):
		"""Configures the horizontal scale and trigger of the oscilloscope to properly acquire two pulses."""
		with self._oscilloscope_Lock:
			self._oscilloscope.set_trig_source('ext')
			self._oscilloscope.set_trig_level('ext', -175e-3) # Totally empiric.
			self._oscilloscope.set_trig_coupling('ext', 'DC')
			self._oscilloscope.set_trig_slope('ext', 'negative')
			self._oscilloscope.set_tdiv('20ns')
			self._oscilloscope.set_trig_delay(-43e-9) # Totally empiric.
	
	def wait_for_trigger(self):
		"""Blocks execution until there is a trigger in the oscilloscope."""
		with self._oscilloscope_Lock:
			self._oscilloscope.wait_for_single_trigger()
	
	def get_waveform(self, channel: int):
		"""Gets the waveform from the oscilloscope for the respective channel."""
		with self._oscilloscope_Lock:
			return self._oscilloscope.get_waveform(channel=channel)
	
	def set_oscilloscope_vdiv(self, channel: int, vdiv: float):
		"""Sets the osciloscope's Volts per division."""
		with self._oscilloscope_Lock:
			self._oscilloscope.set_vdiv(channel, vdiv)
	
	# Temperature and humidity sensor ----------------------------------
	
	@property
	def temperature(self):
		"""Returns a reading of the temperature as a float number in Celsius."""
		return self._temperature_controller.temperature
	
	@property
	def humidity(self):
		"""Returns a reading of the humidity as a float number in %RH."""
		return self._temperature_controller.humidity
	
if __name__ == '__main__':
	import time
	
	the_setup = TheSetup(
		temperature_controller_Pyro_uri = 'PYRO:temperature_controller@0.0.0.0:41995',
	)
	
	print(f'Temperature = {the_setup.temperature:.2f} °C, humidity = {the_setup.humidity:.2f} %RH')

