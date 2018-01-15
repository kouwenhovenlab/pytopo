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
import logging
from IPython import get_ipython

from qcodes.instrument.base import InstrumentBase
from qcodes.instrument.parameter import _BaseParameter

from pysweep.sweep_object import sweep, ChainSweep

import labpythonconfig as cfg

from ..data.data_storage import Data, GridData


logger = logging.getLogger('measurement')

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

    data_cls = Data

    def __init__(self, station, namespace, info_string=None):
        self.station = station
        self.namespace = namespace
        name = self.__class__.__name__
        super().__init__(name)

        self.info_string = info_string
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
        if self.info_string is not None:
            self.data_prefix += f"_{self.info_string}"

        if cfg.metadata_subdir != "":
            self.metadatadir = time.strftime(cfg.metadata_subdir, struct_time)
            self.metadatadir = self.metadatadir.replace("{n}", self.name)
            if idx is not None:
                self.metadatadir += idx
            self.metadatadir = os.path.join(self.datadir, self.metadatadir)
            if self.info_string is not None:
                self.metadatadir += f"_{self.info_string}"
        else:
            self.metadatadir = self.datadir

        self.metadatafile_prefix = time.strftime(cfg.datafile_prefix, struct_time)
        self.metadatafile_prefix = self.metadatafile_prefix.replace("{n}", self.name)
        if idx is not None:
            self.metadatafile_prefix += idx

        self.metadata_prefix = os.path.join(self.metadatadir, self.metadatafile_prefix)
        if self.info_string is not None:
            self.metadata_prefix += f"_{self.info_string}"

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

        ipython = get_ipython()
        ipython.magic("%notebook -e {self.metadata_prefix}_notebook.ipynb")


    def pre_measurement_tasks(self):
        self.init_data()


    def post_measurement_tasks(self):
        self.save_metadata()


    def run(self):
        """
        This is the function used to execute the measurement.
        """
        self.pre_measurement_tasks()
        logger.info('Ready to measure, file location: {}...'.format(self.data_prefix))

        self.setup()
        self.measure()
        logger.info('Measurement finished, cleaning up...')
        self.cleanup()
        self.postprocess()
        self.post_measurement_tasks()
        logger.info('All done!')


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


class PysweepGrid(BaseMeasurement):

    data_cls = GridData

    def __init__(self, station, namespace, *arg, **kw):
        super().__init__(station, namespace, *arg, **kw)

        self.sweep = []


    def measure_datapoint(self):
        raise NotImplementedError


    def measure(self):
        swp = []
        for p, vals in self.sweep:
            swp.append(sweep(p, vals))
        swp.append(self.measure_datapoint)

        for rec in ChainSweep([tuple(swp)]):
            self.data.add(rec)


    def postprocess(self):
        for n in self.data._pages:
            self.data.save_griddata(n)
