import os

# all data location formats will be used with time.strftime()
# additionally available variables:
#  * {n} : name of the measurement
#
# The folder where to store a new data set
data_location = "c:\\data\\%Y-%m\\%Y-%m-%d"
# data file prefix in the data location
datafile_prefix = "%Y-%m-%d_{n}"
# subdirectory in the data location for metadata (can be "")
metadata_subdir = "%Y-%m-%d_{n}"
# prefix for metadata files
metadatafile_prefix = "%Y-%m-%d_{n}"
# whether to append a counting index to the data files
# (handy when storing multiple data sets in the same folder)
data_location_idx = True

# the working directory of our code
labpython_dir = ""
