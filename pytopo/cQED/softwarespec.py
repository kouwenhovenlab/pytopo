import qcodes
import numpy as np
import time
from lmfit.models import LorentzianModel

from pytopo.awg_sequencing import broadbean as bbtools
from pytopo.awg_sequencing import awg_tools
from pytopo.rf.alazar import acquisition_tools 
from pytopo.rf.alazar import awg_sequences
from pytopo.rf.alazar import acquisition_controllers

from plottr import qcodes_dataset
from plottr.qcodes_dataset import QcodesDatasetSubscriber

from qcodes.instrument.parameter import Parameter
from qcodes.dataset.plotting import plot_by_id
from qcodes.dataset.data_export import get_data_by_id

from pytopo.sweep.base import Nest, Chain 
from pytopo.sweep.decorators import getter, setter
from pytopo.sweep import sweep, do_experiment, hardsweep, measure

from pytopo.rf.alazar.awg_sequences import TriggerSequence

class SoftSweepCtl(acquisition_controllers.PostIQCtl):
    """
    An acquisition controller that allows fast software spec.
    The frequencies can be iterated through without stopping the alazar acquisition.
    Returns one IQ value per frequency.
    
    NOTE: you probably want to use at least 2 or 3 averages per point for this to work
    without glitches.
    
    Set the total number of buffers, and the buffers per block to determine the number of points
    and the number of averages, n_avgs = buffers / buffers_per_block.
    
    You will want to run this when the AWG runs a sequence that triggers the alazar n_avgs times in a row,
    but each of these trigger trains must be triggered (i.e., AWG is waiting for a trigger).
    Of course the trigger interval needs to slightly exceed the acquisition time per record, as usual.
    """
    
    values = []
    param = None
    settling_time = 0

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)
        
        self._step = 0
    
    def _settle(self):
        if self.settling_time > 0:
            time.sleep(self.settling_time)
    
    def _perform_step(self, num):
        """
        Set generator to the i-th point whenever buffer_number // buffers_per_block increases.
        Takes into account that calls to this function lag 2 behind the actual acquisition.
        """
        awg = qcodes.Station.default.awg
        
        # we have to increase num by 2: by the time this is called, the
        # alazar is already measuring the buffer that's 2 after the received one.
        # this is just a reality of the alazar we have to live with here.
        if ((num+2) % self.buffers_per_block()) == 0:
            self._step += 1
            if self._step < len(self.values):
                print(f'Point {self._step} ({self.values[self._step]:1.5e})' + 10 * "", end='\r')
                self.param(self.values[self._step])
                self._settle()
            else:
                print('Done!', end='\r')
        
    def pre_acquire(self):
        """
        Starts the acquisition. Sets the generator to the first point, triggers the AWG for the first time.
        """
        super().pre_acquire()
        
        self.param(self.values[0])
        self._settle()
        
        self._step = 0        

        awg = qcodes.Station.default.awg
        awg.start()
    
    
    def buffer_done_callback(self, buffernum):
        """
        This function is called every time the alazar returns buffer data.
        """
        nextstep = buffernum
        self._perform_step(nextstep)
        

def setup_soft_sweep(values, param, time_bin=0.2e-3, integration_time=10e-3, 
                     post_integration_delay=10e-6, setup_awg=True, ctl=None,
                     waiting_time_per_value=0):
    
    awg = qcodes.Station.default.awg
    if ctl is None:
        ctl = qcodes.Station.default.softsweep_ctl
    alazar = qcodes.Station.default.alazar
    
    navgs = int(integration_time / time_bin)
    
    if setup_awg:
        trig_seq = TriggerSequence(awg, SR=1e7)
        trig_seq.wait = 'off'
        trig_seq.setup_awg(cycle_time=time_bin, debug_signal=False, ncycles=navgs, plot=False,
                           final_waiting_time=waiting_time_per_value, start_awg=False)
    
    ctl.param = param
    ctl.values = values
    ctl.buffers_per_block(navgs)
    ctl.average_buffers(True)
    
    ctl.setup_acquisition(samples=int((time_bin-post_integration_delay) * alazar.sample_rate() // 128 * 128),
                          records=1,
                          buffers=len(values)*navgs, verbose=False,
                          allocated_buffers=max(2, len(values)-1))
    return ctl
        

def get_soft_sweep_trace(ctl=None, phase_reference_arm=True):
    if ctl is None:
        ctl = qcodes.Station.default.softsweep_ctl
    data_AB = np.squeeze(ctl.acquisition())
    data_A = data_AB[...,0]
    data_B = data_AB[...,1]
    if phase_reference_arm == True:
        data = data_A*np.exp(-1.j*(np.angle(data_B)))
    else:
        data = data_A
    mag, phase, re, im = np.abs(data), np.angle(data, deg=True), np.real(data), np.imag(data)
    return mag, phase, re, im    
        

@hardsweep(
    ind=[('frequency', 'Hz', 'array')], 
    dep=[('signal_magnitude', 'V', 'array'), ('signal_phase', 'deg', 'array'), ('signal_real', 'V', 'array'), ('signal_imag', 'V', 'array')]
)
def measure_soft_time_avg_spec(frequencies, rf_src, integration_time=10e-3, phase_reference_arm_delay=0, *arg, **kw):
    """
    Use the softspec controller to measure a software-controlled spectrum.
    time_bin is the time per buffer, integration_time sets how many buffers we'll average per 
    frequency point.
    """
    setup = kw.pop('setup', True)
    if setup:
        ctl = setup_soft_sweep(frequencies, rf_src.frequency, integration_time=integration_time, *arg, **kw)
    else:
        ctl = qcodes.Station.default.softsweep_ctl
    mag, phase, re, im = get_soft_sweep_trace(ctl, **kw)
    if phase_reference_arm_delay != 0: 
        data = (re - 1.j*im)*np.exp(1.j*phase_reference_arm_delay*frequencies+np.pi) ##not sure why we need to complex conjugate, but else the phase lineshape of the resonator is inverted... (low to high)
        mag, phase, re, im = np.abs(data), np.angle(data, deg=True), np.real(data), np.imag(data)
    return (frequencies, np.vstack((mag.reshape(-1), phase.reshape(-1), re.reshape(-1), im.reshape(-1))))


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
    setup = kw.pop('setup', True)
    if setup:
        ctl = setup_soft_sweep(voltages, ivvi_dac, integration_time=integration_time, *arg, **kw)
    else:
        ctl = qcodes.Station.default.softsweep_ctl
    mag, phase = get_soft_sweep_trace(ctl)
    return (voltages, np.vstack((mag.reshape(-1), phase.reshape(-1))))


def setup_single_averaged_IQpoint(time_bin, integration_time, setup_awg=True):
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
        trig_seq.setup_awg(cycle_time=1e-3, debug_signal=False, ncycles=1, plot=False)
    
    ctl = station.post_iq_acq
    ctl.buffers_per_block(None)
    ctl.average_buffers(True)
        
    ctl.setup_acquisition(samples=int(time_bin * alazar.sample_rate() // 128 * 128), 
                          records=1,
                          buffers=navgs, verbose=False)


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

def fit_lorentzian(x,y):
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
    dep=[('signal_magnitude', 'V', 'array'), ('signal_phase', 'deg', 'array'), ('peak_frq', 'Hz', 'array')]
)
def measure_qubit_spec_optimize_resonator(resonator_frequencies, resonator_src, 
                                          qubit_frequencies, qubit_src, integration_time=10e-3,
                                          *arg, **kw):
    """
    Takes a resonator spec trace (using software spec), fits a lorentzian line shape,
    then sets the heterodyne source to the peak frequency, then measures
    qubit soft-spec.
    """    
    ctl = setup_soft_sweep(resonator_frequencies, resonator_src.frequency, 
                           integration_time=integration_time, setup_awg=False, **kw)
    
    _, _, fitout = get_resonator_spec_and_fit(resonator_frequencies)
    peak_frequency = fitout.best_values['center']
    resonator_src.frequency(peak_frequency)
    print(f'Found resonator peak frequency: {peak_frequency:1.5e}')
    
    ctl = setup_soft_sweep(qubit_frequencies, qubit_src.frequency, 
                           integration_time=integration_time, setup_awg=True, **kw)    
    mag, phase = get_soft_sweep_trace(ctl)
       
    
    return (qubit_frequencies.reshape(-1), 
            np.vstack((mag.reshape(-1), phase.reshape(-1), np.ones(qubit_frequencies.size) * peak_frequency)))