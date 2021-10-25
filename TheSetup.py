import PyticularsTCT # https://github.com/SengerM/PyticularsTCT
import pyvisa
import TeledyneLeCroyPy # https://github.com/SengerM/TeledyneLeCroyPy
from keithley.Keithley2470 import Keithley2470SafeForLGADs
import atexit

class TheSetup:
	"""This class wraps all the hardware so if there are changes it is easy to adapt."""
	def __init__(self):
		self._osc = TeledyneLeCroyPy.LeCroyWaveRunner(pyvisa.ResourceManager().open_resource('USB0::0x05FF::0x1023::4751N40408::INSTR'))
		self._tct = PyticularsTCT.ParticularsTCT()
		self._keithley = Keithley2470SafeForLGADs('USB0::1510::9328::04481179::0::INSTR', polarity = 'negative')
		
		self._keithley.set_output('on')
		
		def at_exit():
			print('Turning bias voltage off...')
			self._keithley.set_output('off')
			print('Bias voltage is OFF.')
			print('Turning laser off...')
			self._tct.laser.off()
			print('Laser is OFF.')
		atexit.register(at_exit)
	
	def move_to(self, x=None, y=None, z=None):
		"""Move the TCT stages to the specified position."""
		self._tct.stages.move_to(x=x,y=y,z=z)
	
	@property
	def position(self):
		"""Returns the position of the stages."""
		return self._tct.stages.position
	
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
	
	def wait_for_trigger(self):
		"""Blocks execution until there is a trigger in the oscilloscope."""
		self._osc.wait_for_single_trigger()
	
	def get_waveform(self, channel: int):
		"""Gets the waveform from the oscilloscope for the respective channel."""
		return self._osc.get_waveform(channel=channel)
	
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
	
	def configure_oscilloscope_for_two_pulses(self):
		"""Configures the horizontal scale and trigger of the oscilloscope to properly acquire two pulses."""
		self._osc.set_trig_source('ext')
		self._osc.set_trig_level('ext', -50e-3)
		self._osc.set_trig_coupling('ext', 'DC')
		self._osc.set_trig_slope('ext', 'negative')
		self._osc.set_tdiv('20ns')
		self._osc.set_trig_delay(-20e-9)

if __name__ == '__main__':
	import time
	
	the_setup = TheSetup()
	
	the_setup.laser_status = 'on'
	the_setup.laser_DAC = 1555
	print('Seting vias boltage;;;')
	the_setup.bias_voltage = 99
	print(f'Bias voltage = {the_setup.bias_voltage} V')
	the_setup.configure_oscilloscope_for_two_pulses()
	
	input('Exit?')
