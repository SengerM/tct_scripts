from pathlib import Path
import datetime
import pandas
import atexit
import shutil
import numpy as np
import tct_scripts_config

class DataFrameDumper:
	"""This class is for easilly store a continuously growing dataframe
	in the disk easilly. I tried to create a subclass of DataFrame but
	it is too cumbersome."""
	def __init__(self, file_path_in_the_end, df):
		self._ended = False
		self._columns_of_the_df = set(df.columns)
		self._file_path_in_the_end = Path(file_path_in_the_end)
		self._temp_files_path = self._file_path_in_the_end.with_suffix('.temp')
		self._temp_files_path.mkdir(parents=True)
		def _atexit():
			if self._ended == False: # This means that the user forgot to call "end".
				df = pandas.DataFrame(columns = self._columns_of_the_df)
				# Concatenate all files into a single file.
				for fpath in sorted(self._temp_files_path.iterdir()):
					df = df.append(pandas.read_feather(fpath))
				df.reset_index(inplace = True, drop=True)
				df.to_csv(self._file_path_in_the_end.with_suffix('.csv')) # For some strange reason this does not work for feather format within the atexit module, see https://stackoverflow.com/questions/69667532/pandas-feather-atexit-runtimeerror-cannot-schedule-new-futures-after-inte
				shutil.rmtree(self._temp_files_path)
				self._ended = True
		atexit.register(_atexit)
	
	def dump_to_disk(self, df):
		"""Stores the dataframe in a temporary file in the disk and returns the dataframe with all rows deleted.
		Usage:
		my_df = bla bla bla
		my_df = self.dump_to_disk(my_df)
		"""
		self._check_ended()
		if set(df.columns) != self._columns_of_the_df:
			raise ValueError(f'The columns of the dataframe do not match!')
		df.reset_index(drop=True).to_feather(self._temp_files_path/Path(datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')))
		return df[0:0]
	
	def end(self, df):
		self.dump_to_disk(df) # In case there is any data remaining...
		df = pandas.DataFrame(columns = self._columns_of_the_df)
		# Concatenate all files into a single file.
		for fpath in sorted(self._temp_files_path.iterdir()):
			df = df.append(pandas.read_feather(fpath))
		df.reset_index(inplace = True, drop=True)
		df.to_feather(self._file_path_in_the_end.with_suffix('.fd'))
		shutil.rmtree(self._temp_files_path)
		self._ended = True
	
	def _check_ended(self):
		if self._ended == True:
			raise RuntimeError(f'This instance of {repr(DataFrameDumper)} was already ended! You cannot use it anymore.')
	
	@property
	def file_path(self):
		return self._file_path_in_the_end

def adjust_oscilloscope_vdiv_for_TILGAD(the_setup, laser_DAC, bias_voltage, oscilloscope_channels, positions):
	"""Adjust oscilloscope VDIV assuming a TI-LGAD."""
	print(f'Preparing to adjust oscilloscope VDIV...')
	print(f'Turning laser on...')
	the_setup.laser_DAC = laser_DAC
	the_setup.laser_status = 'on'
	print(f'Setting bias voltage to {bias_voltage} V...')
	the_setup.bias_voltage = bias_voltage
	the_setup.bias_output_status = 'on'
	current_vdiv = 1e-3 # Start with the smallest scale.
	for channel in oscilloscope_channels:
		the_setup.set_oscilloscope_vdiv(channel, current_vdiv)
	for position_idx,position in enumerate([positions[int(len(positions)*2/5)],positions[int(len(positions)*3/5)]]): # One position is left pix, the other is right pix.
		the_setup.move_to(*position) # Left pixel position.
		n_signals_without_NaN = 0
		NUMBER_OF_SIGNALS_UNTIL_WE_CONSIDER_WE_ARE_IN_THE_RIGHT_SCALE = 9
		while n_signals_without_NaN < NUMBER_OF_SIGNALS_UNTIL_WE_CONSIDER_WE_ARE_IN_THE_RIGHT_SCALE:
			try:
				the_setup.wait_for_trigger()
			except Exception as e:
				print(f'I was `waiting for trigger` when this error happened: {repr(e)}.')
				print(f'I will start again at n_signals_without_NaN={n_signals_without_NaN}...')
				continue
			volts = {}
			for n_channel in oscilloscope_channels:
				try:
					raw_data = the_setup.get_waveform(channel = n_channel)
				except Exception as e:
					print(f'Cannot get data from oscilloscope, reason: {e}')
					print(f'I will start again at n_signals_without_NaN={n_signals_without_NaN}...')
					continue
				volts[n_channel] = raw_data['Amplitude (V)']
			if any(np.isnan(sum(volts[ch])) for ch in volts): # This means the scale is still too small.
				n_signals_without_NaN = 0
				current_vdiv *= 1.1
				print(f'Scale is still too small, increasing to {current_vdiv} V/div')
				for channel in oscilloscope_channels:
					try:
						the_setup.set_oscilloscope_vdiv(channel, current_vdiv)
					except Exception as e:
						print(f'Could not change oscilloscope`s VDIV, reason is {repr(e)}.')
						print(f'I will start again at n_signals_without_NaN={n_signals_without_NaN}...')
						continue
			else:
				print(f'{n_signals_without_NaN+1} out of {NUMBER_OF_SIGNALS_UNTIL_WE_CONSIDER_WE_ARE_IN_THE_RIGHT_SCALE} signals without NaN, scale seems to be fine!')
				n_signals_without_NaN += 1

def interlace(lst):
	# https://en.wikipedia.org/wiki/Interlacing_(bitmaps)
	lst = sorted(lst)[::-1]
	result = [lst[0], lst[-1]]
	ranges = [(1, len(lst) - 1)]
	for start, stop in ranges:
		if start < stop:
			middle = (start + stop) // 2
			result.append(lst[middle])
			ranges += (start, middle), (middle + 1, stop)
	return result

def get_center_position_from_file():
	if tct_scripts_config.CURRENT_DETECTOR_CENTER_FILE_PATH.is_file():
		with open(tct_scripts_config.CURRENT_DETECTOR_CENTER_FILE_PATH, 'r') as ifile:
			center = {}
			for line in ifile:
				center[line.split('=')[0].replace(' ','')] = float(line.split('=')[-1])
		return tuple([center[k] for k in sorted(center.keys())]) # Sorted x y z
	
def wait_for_nice_trigger_without_EMI(the_setup, channels: list):
	is_noisy = True
	while is_noisy:
		try:
			the_setup.wait_for_trigger()
		except Exception as e:
			print(f'Error while waiting for trigger, reason: {repr(e)}...')
			sleep(1)
			continue
		noise_per_channel = []
		for ch in channels:
			try:
				_raw = the_setup.get_waveform(channel=ch)
			except Exception as e:
				print(f'Cannot get data from oscilloscope, reason: {e}')
				break
			_amplitude = np.array(_raw['Amplitude (V)'])
			_time = np.array(_raw['Time (s)'])
			# ~ # For debug ---
			# ~ import grafica
			# ~ fig = grafica.new()
			# ~ fig.scatter(y=_amplitude, x=_time)
			# ~ fig.save(str(tct_scripts_config.DATA_STORAGE_DIRECTORY_PATH/Path('plot.html')))
			# ~ input('Figure has been saved...')
			# ~ # -------------
			samples_where_we_shoud_have_no_signal = _amplitude[(_time<190e-9)|((_time>240e-9)&(_time<290e-9))] # Totally empiric numbers, the "debug lines" just before are to find this.
			this_channel_noise = np.std(samples_where_we_shoud_have_no_signal)
			noise_per_channel.append(this_channel_noise)
		if all(noise < 10e-3 for noise in noise_per_channel):
			is_noisy = False
		else:
			print('Noisy trigger! Will skip it...')
