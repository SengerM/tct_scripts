from TheSetup import TheSetup
from simple_pid import PID
from time import sleep

the_setup = TheSetup()

# Initialize ---
the_setup.peltier_set_voltage = 30
the_setup.peltier_set_current = 0
the_setup.peltier_status = 'on'
sleep(1)

pid = PID(-.5,-.1,-2)
pid.sample_time = 1
pid.output_limits = (0, 4.2) # Will control the current in Ampere.

pid.setpoint = 18
print(f'T = {the_setup.temperature:.2f} °C | I_set = {the_setup.peltier_set_current:.2f} A | I_meas = {the_setup.peltier_measured_current:.2f} A')
while True:
	T = the_setup.temperature
	new_current = pid(T)
	the_setup.peltier_set_current = new_current
	print(f'T = {the_setup.temperature:.2f} °C | I_set = {the_setup.peltier_set_current:.2f} A | I_meas = {the_setup.peltier_measured_current:.2f} A')
	sleep(1)
