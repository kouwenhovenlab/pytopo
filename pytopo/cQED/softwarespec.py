import qcodes
import numpy as np
import time
from lmfit.models import LorentzianModel

from pytopo.awg_sequencing import broadbean as bbtools
from pytopo.awg_sequencing import awg_tools
from pytopo.rf.alazar import acquisition_tools
from pytopo.rf.alazar import awg_sequences
from pytopo.rf.alazar import acquisition_controllers
from pytopo.rf.alazar import softsweep

from qcodes.instrument.parameter import Parameter
from qcodes.dataset.plotting import plot_by_id
from qcodes.dataset.data_export import get_data_by_id

from pytopo.sweep.base import Nest, Chain
from pytopo.sweep.decorators import getter, setter
from pytopo.sweep import sweep, do_experiment, hardsweep, measure

from pytopo.rf.alazar.awg_sequences import TriggerSequence
from pytopo.rf.alazar.softsweep import SoftSweepCtl


def setup_soft_sweep(values, param, time_bin=0.5e-3, integration_time=10e-3,
                     post_integration_delay=10e-6, setup_awg=True, ctl=None, verbose = True):

    if ctl is None:
        ctl = qcodes.Station.default.softsweep_ctl

    softsweep.setup_triggered_softsweep(
        ctl, param, values, integration_time, time_bin=time_bin,
        setup_awg=setup_awg, post_integration_delay=post_integration_delay,verbose = verbose,
    )

    return ctl


def get_soft_sweep_trace(ctl=None):
    if ctl is None:
        ctl = qcodes.Station.default.softsweep_ctl
    data = np.squeeze(ctl.acquisition())[..., 0]
    mag, phase = np.abs(data), np.angle(data, deg=True)
    return mag, phase


def setup_single_averaged_IQpoint(time_bin, integration_time, setup_awg=True,
                                  post_integration_delay=10e-6,
                                  verbose=True, allocated_buffers=None):
    """
    Setup the alazar to measure a single IQ value / buffer.

    Note: we always average over buffers here (determined by time_bin and integration_time).
    This implies that you need to use a trigger sequence with a trigger interval that 
    corresponds to an even number of IF periods.
    """
    station = qcodes.Station.default
    alazar = station.alazar

    navgs = int(integration_time / time_bin)

    if setup_awg:
        trig_seq = TriggerSequence(station.awg, SR=1e7)
        trig_seq.wait = 'off'
        trig_seq.setup_awg(
            cycle_time=time_bin, debug_signal=False, ncycles=1, plot=False)

    ctl = station.post_iq_acq
    ctl.buffers_per_block(None)
    ctl.average_buffers(True)

    ctl.setup_acquisition(samples=int((time_bin-post_integration_delay) * alazar.sample_rate() // 128 * 128),
                          records=1, buffers=navgs, allocated_buffers=allocated_buffers, verbose=verbose)


# measurements that use pytopo.sweep

@hardsweep(
    ind=[('frequency', 'Hz', 'array')],
    dep=[('signal_magnitude', 'V', 'array'), ('signal_phase', 'deg', 'array')]
)
def measure_soft_time_avg_spec(frequencies, rf_src, integration_time=10e-3, *arg, **kw):
    """
    Use the softspec controller to measure a software-controlled spectrum.
    time_bin is the time per buffer, integration_time sets how many buffers we'll average per 
    frequency point.
    """
    setup = kw.pop('setup_', True)
    if setup:
        ctl = setup_soft_sweep(frequencies, rf_src.frequency,
                               integration_time=integration_time, *arg, **kw)
    else:
        ctl = qcodes.Station.default.softsweep_ctl
    mag, phase = get_soft_sweep_trace(ctl)
    return (frequencies, np.vstack((mag.reshape(-1), phase.reshape(-1))))


@hardsweep(
    ind=[('voltage', 'mV', 'array')],
    dep=[('signal_magnitude', 'V', 'array'), ('signal_phase', 'deg', 'array')]
)
def measure_soft_gate_sweep(voltages, ivvi_dac, integration_time=10e-3, *arg, **kw):
    """
    Use the softspec controller to measure a software-controlled spectrum.
    time_bin is the time per buffer, integration_time sets how many buffers we'll average per 
    frequency point.
    """
    setup = kw.pop('setup_awg', True)
    if setup:
        ctl = setup_soft_sweep(
            voltages, ivvi_dac, integration_time=integration_time, *arg, **kw)
    else:
        ctl = qcodes.Station.default.softsweep_ctl
    mag, phase = get_soft_sweep_trace(ctl)
    return (voltages, np.vstack((mag.reshape(-1), phase.reshape(-1))))


@getter(('signal_amp', 'V'), ('signal_phase', 'deg'))
def get_single_averaged_IQpoint_chanA():
    """
    Measure a single IQ point from channel A on the alazar. 
    Up to the channel dimension, we average all other dimensions.
    Returns amplitude and phase of the measured value.
    """
    station = qcodes.Station.default
    ctl = station.post_iq_acq
    data = ctl.acquisition()
    data = np.squeeze(data)[..., 0].mean()
    mag, phase = np.abs(data), np.angle(data, deg=True)

    return mag, phase


### Qubit spectroscopy (two-tone) ###

def fit_lorentzian(x, y):
    mod = LorentzianModel()

    pars = mod.guess(y, x=x)
    out = mod.fit(y, pars, x=x)
    return out


def get_resonator_spec_and_fit(frequencies):
    mag, phase = get_soft_sweep_trace()
    out = fit_lorentzian(frequencies, mag**2)
    return mag, phase, out


@hardsweep(
    ind=[('frequency', 'Hz', 'array')],
    dep=[('signal_magnitude', 'V', 'array'), ('signal_phase',
                                              'deg', 'array'), ('peak_frq', 'Hz', 'array')]
)
def measure_qubit_spec_optimize_resonator(resonator_frequencies, resonator_src,
                                          qubit_frequencies, qubit_src, time_bin=0.5e-3, integration_time=10e-3, hanger=False,
                                          *arg, **kw):
    """
    Takes a resonator spec trace (using software spec), fits a lorentzian line shape,
    then sets the heterodyne source to the peak frequency, then measures
    qubit soft-spec.
    """
    ctl = setup_soft_sweep(resonator_frequencies, resonator_src.frequency, time_bin=time_bin,
                           integration_time=integration_time, setup_awg=False, **kw)
    if hanger:
        mag, phase = get_soft_sweep_trace()
        peak_frequency = resonator_frequencies[np.argmin(mag)]
    else:
        _, _, fitout = get_resonator_spec_and_fit(resonator_frequencies)
        peak_frequency = fitout.best_values['center']

    resonator_src.frequency(peak_frequency)
    print(f'Found resonator peak frequency: {peak_frequency:1.5e}')
    ctl = setup_soft_sweep(qubit_frequencies, qubit_src.frequency, time_bin=time_bin,
                           integration_time=integration_time, setup_awg=False, **kw)
    mag, phase = get_soft_sweep_trace(ctl)
    return (qubit_frequencies.reshape(-1),
            np.vstack((mag.reshape(-1), phase.reshape(-1), np.ones(qubit_frequencies.size) * peak_frequency)))
