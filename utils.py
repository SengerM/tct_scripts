from pathlib import Path
import datetime
import pandas
import atexit
import shutil

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
