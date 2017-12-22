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
import logging
import json
import h5py
from collections import OrderedDict
import numpy as np

from qcodes.instrument.base import InstrumentBase
from qcodes.instrument.parameter import _BaseParameter

from pysweep.sweep_object import sweep, ChainSweep
from pysweep.data_storage import NpStorage

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
        self.data = Data(self.datafilepath)
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


class PysweepMeasurement(BaseMeasurement):
    """
    A simple prototype for how we could write a measurement around pysweep loops.
    """

    def measure(self):
        for rec in ChainSweep([self.sweep()]):
            self.data.add(rec)



class Data(NpStorage):
    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath

        self.export_spyview = True
        self.spyview_prefix = os.path.splitext(self.filepath)[0]


    @staticmethod
    def flatten_page(page, invert_axis_order=True):
        names = [n for n in page.dtype.fields]
        if invert_axis_order:
            names = names[:-1][::-1] + [names[-1]]

        shapes = [page.dtype[n].shape for n in names]
        dtypes = [page[n].dtype for n in names]
        sizes = [np.prod(s) for s in shapes]

        if ((1,) in shapes and len(set(shapes)) > 2) or ((1,) not in shapes and len(set(shapes)) > 1):
            raise NotImplementedError("Flattening of non-trivial shapes is currently not implemented.")

        blocksize = max(sizes)
        pagelen = page.size
        datasize = blocksize * pagelen
        data = np.zeros((datasize,), dtype=[(n,d) for n,d in zip(names, dtypes)])

        for name, size in zip(names, sizes):
            if size < blocksize:
                data[name] = np.vstack(blocksize*[page[name].reshape(-1)]).reshape(-1, order='F')
            else:
                data[name] = page[name].reshape(-1)

        return data


    @staticmethod
    def meta_info(data, exclude_dependent=True):
        ret = OrderedDict({})
        names = [n for n in data.dtype.fields]
        if exclude_dependent:
            names = names[:-1]

        for n in names:
            vals, nvals = np.unique(data[n], return_counts=True)
            ret[n] = {
                'values' : vals,
                'occurences' : nvals,
            }
        return ret


    def write_spyview_meta(self, fn, pagename):
        data = Data.flatten_page(self[pagename], invert_axis_order=True)
        info = Data.meta_info(data)
        names = [n for n in data.dtype.fields]
        naxes = len(names[:-1])
        with open(fn, 'w') as f:
            for idx, n in enumerate(names[:-1]):
                m = info[n]
                f.write("{}\n{}\n{}\n{}\n".format(m['values'].size,
                                                  m['values'][0],
                                                  m['values'][-1],
                                                  n))
            for i in range(3 - naxes):
                f.write("{}\n{}\n{}\n{}\n".format(1,0,0,'None'))

            f.write("{}\n{}\n".format(idx+2, names[-1]))


    def write_spyview_data(self, fn, page):
        isnewfile = not os.path.exists(fn)

        data = Data.flatten_page(page, invert_axis_order=True)
        names = [n for n in data.dtype.fields]
        naxes = len(names[:-1])

        if names[-1] in self._pages:
            pagename = names[-1]
        elif names[-1].split(' [')[0] in self._pages:
            pagename = names[-1].split(' [')[0]
        else:
            raise ValueError("Cannot find page corresponding to this data.")

        alldata = Data.flatten_page(self[pagename], invert_axis_order=True)
        col0_start = alldata[names[0]][0]

        metafn = os.path.splitext(fn)[0] + ".meta.txt"
        self.write_spyview_meta(metafn, pagename)

        with open(fn, 'a') as f:
            for i, row in enumerate(data):
                if row[names[0]] == col0_start:
                    f.write("\n")

                line = "\t".join(["{}".format(row[k]) for k in names])
                line += "\n"
                f.write(line)


    def add(self, record, write=True):
        super().add(record)
        if write:
            self.write(record)


    def write(self, record=None):
        with h5py.File(self.filepath, 'a') as f:
            if record is None:
                pages = self._pages
            else:
                pages = self.record_to_pages(record)

            for name, arr in pages.items():
                if name in f:
                    d = f[name]
                else:
                    d = f.create_dataset(name, (0,), maxshape=(None,), dtype=arr.dtype, chunks=True)

                newlen = d.size + arr.size
                d.resize((newlen,))
                d[-arr.size:] = arr

                if self.export_spyview:
                    spyview_fn = self.spyview_prefix + "_{}.dat".format(name)
                    self.write_spyview_data(spyview_fn, arr)
