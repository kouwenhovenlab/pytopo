""" A module to make working with the qcodes v2 dataset a bit more
convenient.

Maintainer: Wolfgang Pfaff <wolfgangpfff@gmail.com>
"""
import numpy as np
import time
import qcodes as qc
from qcodes.dataset.data_set import DataSet
from qcodes.dataset.experiment_container import load_experiment_by_name, \
    new_experiment
from qcodes.dataset.sqlite_base import transaction, one
from qcodes.dataset.data_export import get_data_by_id
from qcodes.dataset.plotting import plot_by_id

from pytopo.sweep import SweepMeasurement


def select_experiment(exp_name, sample_name):
    """
    Convenience function that will check if the experiment/sample
    combination already exists in the current database. If so,
    it'll return the existing one. Otherwise it will create a new
    one and return that.

    Potential issue: if multiple experiments with the same
    experiment/sample combination exist, our detection method will
    fail, and another copy of this combination will be created.
    """
    try:
        exp = load_experiment_by_name(exp_name, sample_name)
    except ValueError:
        exp = new_experiment(exp_name, sample_name)
    return exp


def get_run_timestamp(run_id):
    DB = qc.config["core"]["db_location"]

    d = DataSet(DB)
    sql = """
    SELECT run_timestamp
    FROM
      runs
    WHERE
      run_id= ?
    """
    c = transaction(d.conn, sql, run_id)
    run_timestamp = one(c, 'run_timestamp')
    return run_timestamp


def timestamp_to_fmt(ts, fmt="%Y-%m-%d %H:%M:%S"):
    return time.strftime(fmt, time.gmtime(ts))


class _DataExtractor:
    """
    A convenience class to quickly extract data from a data saver instance
    """
    def __init__(self, datasaver):
        self._run_id = datasaver.run_id
        self._dataset = datasaver.dataset

    def __getitem__(self, layout):

        layout = sorted(layout.split(","))
        all_data = get_data_by_id(self._run_id)
        data_layouts = [sorted([d["name"] for d in ad]) for ad in all_data]

        i = np.array(
            [set(layout).issubset(data_layout) for data_layout in data_layouts]
        )

        ind = np.flatnonzero(i)
        if len(ind) == 0:
            raise ValueError(f"No such layout {layout}")

        data = all_data[ind[0]]
        return {d["name"]: d["data"] for d in data}

    def plot(self):
        plot_by_id(self._run_id)

    @property
    def run_id(self):
        return self._run_id


def do_experiment(setup, sweep_object, cleanup, experiment=None, station=None):

    meas = SweepMeasurement(exp=experiment, station=station)
    meas.register_sweep(sweep_object)

    call_args = lambda tpl: (tpl if isinstance(tpl, tuple) else (tpl, ()))

    for s in setup:
        f, args = call_args(s)
        meas.add_before_run(f, args)

    for s in cleanup:
        f, args = call_args(s)
        meas.add_after_run(f, args)

    with meas.run() as datasaver:
        for data in sweep_object:
            datasaver.add_result(*data.items())

    return _DataExtractor(datasaver)
