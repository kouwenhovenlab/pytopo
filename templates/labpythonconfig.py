import os

# Base folder where we will store all data and metadata
data_location = "c:\\data"

# How to generate a location for each dataset.
# need a tuple with two elements, each of which we will supply to
# time.strftime().
# first element: folder structure for the measurement.
# second element: file name prefix for all generated files.
data_location_formatter = "%Y-%m\\%Y-%m-%d\\%H%M%S", "%H%M%S"

# the working directory of our code
labpython_dir = ""
