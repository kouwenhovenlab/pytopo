"""
This module contains basic measurement classes.
The stuff in here is not very specific to any kind of
particular experiment, those typically live in separate modules.
"""

import os
import time
import logging
import json
from qcodes.utils.helpers import DelegateAttributes, full_class
from qcodes.utils.metadata import Metadatable
from qcodes.instrument.base import InstrumentBase
from qcodes.instrument.parameter import _BaseParameter

import labpythonconfig as cfg

DATAIDXPAD = 4

def get_next_data_idx(folder, prefix):
    if not os.path.exists(folder):
        return "-#" + "0".zfill(DATAIDXPAD)

    files = [os.path.splitext(f)[0] for f in os.listdir(folder)]
    idxs = []
    for f in files:
        try:
            idxs.append(int(f.split(prefix+"-#")[1].split("_")[0]))
        except:
            pass

    if not idxs:
        return "-#" + "0".zfill(DATAIDXPAD)

    return "-#" + str(max(idxs) + 1).zfill(DATAIDXPAD)


def get_data_loc(name, struct_time=None, makedir=False):
    if struct_time is None:
        struct_time = time.localtime()

    datadir = time.strftime(cfg.data_location, struct_time)
    datadir = datadir.replace("{n}", name)

    datafile_prefix = time.strftime(cfg.datafile_prefix, struct_time)
    datafile_prefix = datafile_prefix.replace("{n}", name)
    if cfg.data_location_idx:
        datafile_prefix += get_next_data_idx(datadir, datafile_prefix)

    ret = {
        'data_folder' : datadir,
        'datafile_prefix' : datafile_prefix,
    }

    return ret

# class BaseExperimentData(object):
#     def __init__(self, name, **kwargs):
#         self.name = name

#     def add_data(self, **kwargs):
#         raise NotImplementedError


class Parameter(_BaseParameter):

    def __init__(self, name, initial_value=None, **kw):
        super().__init__(name, **kw)
        self._value = initial_value

    def get_raw(self):
        return self._value

    def set_raw(self, value):
        self._value = value


class BaseMeasurement(InstrumentBase):

    def __init__(self, station):
        self.station = station
        name = self.__class__.__name__
        super().__init__(name)

        self._meta_attrs = ['name']

    def save_metadata(self):
        station_snap = self.station.snapshot()
        with open(self.dataloc_prefix + "_station.json", 'w') as f:
            json.dump(station_snap, f, indent=4)

        msmt_snap = self.snapshot()
        with open(self.dataloc_prefix + "_measurement.json", 'w') as f:
            json.dump(msmt_snap, f, indent=4)


    def _get_data_location(self):
        """
        Find the folder on the file system where we will store all
        data and metadata coming from the measurement.
        """
        info = get_data_loc(self.name)
        self.dataloc_folder = info['data_folder']
        self.datafile_prefix = info['datafile_prefix']
        self.dataloc_prefix = os.path.join(self.dataloc_folder, self.datafile_prefix)
        print(self.dataloc_prefix)

    def init_data(self):
        """
        Initialize the internal data object.
        """
        self._get_data_location()
        if os.path.exists(self.dataloc_folder):
            logging.info("Data folder {} already exists.".format(self.dataloc_folder))
        else:
            os.makedirs(self.dataloc_folder)

    def pre_measurement_tasks(self):
        self.init_data()

    def post_measurement_tasks(self):
        self.save_metadata()

    def run(self):
        """
        This is the function used to execute the measurement.
        """
        self.pre_measurement_tasks()
        self.setup()
        self.measure()
        self.cleanup()
        self.postprocess()
        self.post_measurement_tasks()


    # These are the functions that each measurement can implement.
    # measure() is a must.
    def setup(self):
        pass

    def measure(self):
        raise NotImplementedError

    def postprocess(self):
        pass

    def cleanup(self):
        pass
