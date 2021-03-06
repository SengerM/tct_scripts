from pathlib import Path
import datetime
import pandas
import atexit
import shutil
import numpy as np
import tct_scripts_config
import time

class DataFrameDumper:
	"""This class is for easilly store a continuously growing dataframe
	in the disk easilly. I tried to create a subclass of DataFrame but
	it is too cumbersome."""
	def __init__(self, file_path_in_the_end, df, dump_if_more_rows_than: int=1e6, dump_if_more_time_than: float=60):
		self._ended = False
		self._columns_of_the_df = set(df.columns)
		self._file_path_in_the_end = Path(file_path_in_the_end)
		self._temp_files_path = self._file_path_in_the_end.with_suffix('.temp')
		self._temp_files_path.mkdir(parents=True)
		self.dump_if_more_rows_than = dump_if_more_rows_than
		self.dump_if_more_time_than = dump_if_more_time_than
		self._last_dump_when = datetime.datetime.now()
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
	
	def dump_to_disk(self, df, force=False):
		"""Stores the dataframe in a temporary file in the disk and returns the dataframe with all rows deleted.
		Usage:
		my_df = bla bla bla
		my_df = self.dump_to_disk(my_df)
		"""
		self._check_ended()
		if set(df.columns) != self._columns_of_the_df:
			raise ValueError(f'The columns of the dataframe do not match!')
		if force==True or len(df.index) > self.dump_if_more_rows_than or (datetime.datetime.now()-self._last_dump_when).seconds > self.dump_if_more_time_than:
			df.reset_index(drop=True).to_feather(self._temp_files_path/Path(datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')))
			return df[0:0]
		else:
			return df
	
	def end(self, df):
		self.dump_to_disk(df, force=True) # In case there is any data remaining...
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

def adjust_oscilloscope_vdiv_for_linear_scan_between_two_pixels(the_setup, oscilloscope_channels, position_of_each_pixel):
	"""Adjust oscilloscope VDIV assuming a TI-LGAD.
	
	Parameters
	----------
	the_setup: TheSetup
		An instance of TheSetup.
	oscilloscope_channels: list
		A list with the channel of each pixel, e.g. `[1,2]`.
	position_of_each_pixel: list
		A list with two positions, one for the left and one for the right pixel.
	"""
	if len(position_of_each_pixel) != 2:
		raise ValueError(f'`position_of_each_pixel` must be a list with two positions, one for each pixel.')
	print(f"Starting oscilloscope's VDIV adjustment routine...")
	current_vdiv = 1e-3 # Start with the smallest scale.
	for channel in oscilloscope_channels:
		the_setup.set_oscilloscope_vdiv(channel, current_vdiv)
	for position in position_of_each_pixel:
		print(f'Moving to {position}...')
		the_setup.move_to(*position)
		n_signals_without_NaN = 0
		NUMBER_OF_SIGNALS_UNTIL_WE_CONSIDER_WE_ARE_IN_THE_RIGHT_SCALE = 33
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
		if all(noise < 111 for noise in noise_per_channel):
			is_noisy = False
		else:
			print('Noisy trigger! Will skip it...')
