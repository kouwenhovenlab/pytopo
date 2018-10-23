import numpy as np
from warnings import warn

import qcodes
from qcodes.dataset.data_export import get_data_by_id
from qcodes.dataset.plotting import plot_by_id
from qcodes.dataset.experiment_container import load_or_create_experiment
from qcodes.dataset.data_set import DataSet

from pytopo.sweep.measurement import SweepMeasurement


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

        i = np.array([
            set(layout).issubset(set(data_layout))
            for data_layout in data_layouts
        ])

        ind = np.flatnonzero(i)
        if len(ind) == 0:
            raise ValueError(f"No such layout {layout}. "
                             f"Available layouts: {data_layouts}")

        data = all_data[ind[0]]
        return {d["name"]: d["data"] for d in data}

    def plot(self):
        plot_by_id(self._run_id)

    @property
    def run_id(self):
        return self._run_id


def do_experiment(
        experiment_name, sweep_object, setup=None, cleanup=None,
        station=None, live_plot=False):

    if "/" in experiment_name:
        experiment_name, sample_name = experiment_name.split("/")
    else:
        sample_name = None

    experiment = load_or_create_experiment(experiment_name, sample_name)

    def add_actions(action, callables):
        if callables is None:
            return

        for cabble in np.atleast_1d(callables):
            if not isinstance(cabble, tuple):
                cabble = (cabble, ())

            action(*cabble)

    if live_plot:
        try:
            from plottr.qcodes_dataset import QcodesDatasetSubscriber
            from plottr.tools import start_listener

            start_listener()

        except ImportError:
            warn("Cannot perform live plots, plottr not installed")
            live_plot = False

    meas = SweepMeasurement(exp=experiment, station=station)
    meas.register_sweep(sweep_object)

    add_actions(meas.add_before_run, setup)
    add_actions(meas.add_after_run, cleanup)

    with meas.run() as datasaver:

        if live_plot:
            datasaver.dataset.subscribe(
                QcodesDatasetSubscriber(datasaver.dataset),
                state=[], min_wait=0, min_count=1
            )

        for data in sweep_object:
            datasaver.add_result(*data.items())

    return _DataExtractor(datasaver)
