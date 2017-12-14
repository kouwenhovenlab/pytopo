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
from qcodes.instrument.parameter import _BaseParameter

import labpythonconfig as cfg


class Parameter(_BaseParameter):
    def __init__(self, name, initial_value=None, **kw):
        super().__init__(name, None, **kw)
        self._value = initial_value

    def get_raw(self):
        return self._value

    def set_raw(self, value):
        self._value = value


class BaseMeasurement(Metadatable, DelegateAttributes):

    def __init__(self, station):
        super().__init__()
        self.station = station
        self.msmt_name = self.__class__.__name__

    def snapshot_base(self, update=False, *arg, **kw):
        snap = {
            "__class__": full_class(self)
            }

        snap['parameters'] = {}
        for name in self.__dir__():
            if isinstance(getattr(self, name), _BaseParameter):
                param = getattr(self, name)
                try:
                    snap['parameters'][name] = param.snapshot(update=update)
                except:
                    logging.debug("Snapshot: Could not update parameter: {}".format(name))
                    snap['parameters'][name] = param.snapshot(update=False)

        return snap

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
        folder, prefix = cfg.data_location_formatter
        self.dataloc_folder = os.path.join(cfg.data_location,
                                           time.strftime(folder)+"_{}".format(self.msmt_name))
        self.datafile_prefix = time.strftime(prefix) + "_{}".format(self.msmt_name)
        self.dataloc_prefix = os.path.join(self.dataloc_folder, self.datafile_prefix)

    def init_data(self):
        """
        Initialize the internal data object.
        """
        self._get_data_location()
        if os.path.exists(self.dataloc_folder):
            logging.warning("Data folder {} already exists.".format(self.dataloc_folder))
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
