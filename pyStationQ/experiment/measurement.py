"""
This module contains basic measurement classes.
The stuff in here is not very specific to any kind of
particular experiment, those typically live in separate modules.

TODO (wpfff) : probably want something like a DataManager class
    that is responsible for interfacing with data storage.
    (for future compatibility it might be unwise to have the
     msmt class talk to the data on too low level...?)
"""

import os
import time
import json

from qcodes.instrument.base import InstrumentBase
from qcodes.instrument.parameter import _BaseParameter

from pysweep.sweep_object import sweep, ChainSweep

from data.data_storage import Data
import labpythonconfig as cfg


DATAIDXPAD = 4

class Parameter(_BaseParameter):

    def __init__(self, name, initial_value=None, **kw):
        super().__init__(name, **kw)
        self._value = initial_value

    def get_raw(self):
        return self._value

    def set_raw(self, value):
        self._value = value


class BaseMeasurement(InstrumentBase):

    def __init__(self, station, namespace):
        self.station = station
        self.namespace = namespace
        name = self.__class__.__name__
        super().__init__(name)

        self._meta_attrs = ['name']

    @staticmethod
    def _get_next_data_idx(folder, prefix):
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


    def _get_data_location(self, makedirs=True, struct_time=None):
        if struct_time is None:
            struct_time = time.localtime()
        idx = None

        self.datadir = time.strftime(cfg.data_location, struct_time)
        self.datadir = self.datadir.replace("{n}", self.name)

        self.datafile_prefix = time.strftime(cfg.datafile_prefix, struct_time)
        self.datafile_prefix = self.datafile_prefix.replace("{n}", self.name)
        if cfg.data_location_idx:
            idx = BaseMeasurement._get_next_data_idx(self.datadir, self.datafile_prefix)
            self.datafile_prefix += idx

        self.data_prefix = os.path.join(self.datadir, self.datafile_prefix)

        if cfg.metadata_subdir != "":
            self.metadatadir = time.strftime(cfg.metadata_subdir, struct_time)
            self.metadatadir = self.metadatadir.replace("{n}", self.name)
            if idx is not None:
                self.metadatadir += idx
            self.metadatadir = os.path.join(self.datadir, self.metadatadir)
        else:
            self.metadatadir = self.datadir

        self.metadatafile_prefix = time.strftime(cfg.datafile_prefix, struct_time)
        self.metadatafile_prefix = self.metadatafile_prefix.replace("{n}", self.name)
        if idx is not None:
            self.metadatafile_prefix += idx

        self.metadata_prefix = os.path.join(self.metadatadir, self.metadatafile_prefix)

        if makedirs:
            if not os.path.exists(self.datadir):
                os.makedirs(self.datadir)
            if cfg.metadata_subdir != '':
                if not os.path.exists(self.metadatadir):
                    os.makedirs(self.metadatadir)


    def init_data(self):
        """
        Initialize the internal data object.
        """
        self._get_data_location(makedirs=True)
        self.datafilepath = self.data_prefix + ".hdf5"
        self.data = self.data_cls(self.datafilepath)
        self.data.spyview_prefix = self.metadata_prefix

    def save_metadata(self):
        station_snap = self.station.snapshot()
        with open(self.metadata_prefix + "_station.json", 'w') as f:
            json.dump(station_snap, f, indent=4)

        msmt_snap = self.snapshot()
        with open(self.metadata_prefix + "_measurement.json", 'w') as f:
            json.dump(msmt_snap, f, indent=4)


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
