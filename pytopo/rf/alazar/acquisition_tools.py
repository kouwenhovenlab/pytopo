import logging
import time
import numpy as np
import qcodes as qc
from qcodes.utils.helpers import LogCapture
from qcodes.instrument.parameter import Parameter
from qcodes.dataset.measurements import Measurement

# tools for setting up and starting the measurement

def simple_triggered_sweep_acquisition(npts, acq_time, navgs=1, ctl=None,
                                       pre_acq_func=None, post_acq_func=None, **kw):
    """
    Simple wrapper for measurements where each record corresponds to one data point
    (i.e., one complex number). Buffers are assumed to be used for averaging.
    
    Parameters:
    -----------
    
    npts : int
        number of points in the sequence
        
    acq_time : float
        acquisition time per point (in seconds)
        
    navgs : int
        number of averages (i.e., buffers per acquisition)
        
    ctl : qcodes instrument (default: None)
        if not None, use this controller.
        otherwise, we'll try to find the controller 'post_iq_acq'.
        
    pre_acq_func : callable (default: None)
        function to call in ctl's pre_acquire.
        
    post_acq_func : callable (default: None)
        function to call in ctl's post_acquire.
        
    further keyword args will be passed to ctl.setup_acquisition
    
    Returns:
    --------
    
    return value of ctl.acquisition
    """
    
    if ctl is None:
        ctl = qc.Instrument.find_instrument(
            qc.config['user']['instruments']['default_acquisition_controller']
            )
        
    ctl.pre_acquire_func = pre_acq_func
    ctl.post_acquire_func = post_acq_func
    ctl.setup_acquisition(samples=None, records=npts, buffers=navgs, 
                          allocated_buffers=10, acq_time=acq_time, **kw)
    
    return ctl.acquisition()


class AlazarMeasurement(Measurement):
    """
    Extension of the qcodes measurement class to make handling Alazar data easier.
    """

    def __init__(self, station, hard_axes=[], soft_params=[], exp=None, 
                 real=True, imag=True, mag=False, phase=False):
        
        super().__init__(exp, station)
        
        self.real = real
        self.imag = imag
        self.mag = mag
        self.phase = phase
        
        self._soft_params = []
        self._hard_params = []
        self._hard_params_names = []
        
        for p in soft_params:
            if isinstance(p, str):
                self.register_custom_parameter(p, paramtype='array')
            elif isinstance(p, Parameter):
                self.register_parameter(p, paramtype='array')
            else:
                raise ValueError(f'Unknown parameter type for {p}: {type(p)}')
                
            self._soft_params.append(p)

        for a in hard_axes:
            if len(a) == 2:
                n, v = a
                u = ''
            elif len(a) == 3:
                n, v, u = a
            else:
                raise ValueError(f'Cannot determine axis specification from {a}')

            self._hard_params.append((n, v))
            self._hard_params_names.append(n)
            self.register_custom_parameter(n, unit=u, paramtype='array')
            
        if real:
            self.register_custom_parameter('signal_real', unit='V',
                                           setpoints=self._soft_params + self._hard_params_names,
                                           paramtype='array')
        if imag:
            self.register_custom_parameter('signal_imag', unit='V',
                                           setpoints=self._soft_params + self._hard_params_names,
                                           paramtype='array')
        if mag:
            self.register_custom_parameter('signal_mag', unit='V',
                                           setpoints=self._soft_params + self._hard_params_names,
                                           paramtype='array')
        if phase:
            self.register_custom_parameter('signal_phase', unit='rad',
                                           setpoints=self._soft_params + self._hard_params_names,
                                           paramtype='array')
    
    
    @staticmethod
    def acquisition2result(data, *axes, real=True, imag=True, mag=False, phase=False):
        axarrs = []
        axnames = []
        for axname, axvals in axes:
            axarrs.append(axvals)
            axnames.append(axname)

        grids = [g.reshape(-1) for g in np.meshgrid(*axarrs, indexing='ij')]

        datavals = []
        datanames = []
        if real:
            datavals.append(data.real.reshape(-1))
            datanames.append('signal_real')
        if imag:
            datavals.append(data.imag.reshape(-1))
            datanames.append('signal_imag')
        if mag:
            datavals.append(np.abs(data).reshape(-1))
            datanames.append('signal_mag')
        if phase:
            datavals.append(np.angle(data).reshape(-1))
            datanames.append('signal_phase')        

        return list(zip(axnames + datanames, grids + datavals))
    
    
    def get_result(self, data, *params):
        soft_params = []
        for k, v in params:
            if k in self._hard_params_names:
                i = self._hard_params_names.index(k)
                self._hard_params[i] = (k, v)
            else:
                soft_params.append((k, v))
        
        axes = soft_params + self._hard_params
        return AlazarMeasurement.acquisition2result(
            data, *axes, real=self.real, imag=self.imag,
            mag=self.mag, phase=self.phase)



# commonly used tools for triggering, etc.

def start_awg_func():
    """
    Finds the AWG from the qcodes config entry user/instruments/awg_name and executes 'play'.
    """
    awg = qc.Instrument.find_instrument(qc.config['user']['instruments']['awg_name'])
    awg.play()

    
def stop_awg_func():
    """
    Finds the AWG from the qcodes config entry user/instruments/awg_name and executes 'stop'.
    """
    awg = qc.Instrument.find_instrument(qc.config['user']['instruments']['awg_name'])
    awg.stop()

def trigger_awg_func():
    awg = qc.Instrument.find_instrument(qc.config['user']['instruments']['awg_name'])
    awg.force_triggerA()


# Debugging and testing functions

def time_acquisition(ctl, nsamples, nrecords, nbuffers, 
                     alloc_buffers=10, SR=2e8, t_total=None):
    """
    Parameters:
    -----------
    
    ctl : qcodes instrument instance
        acquisition controller to test
        
    nsamples : int
        samples per record
        
    nrecords : int
        records per buffer
        
    nbuffers : int
        buffers in the total acquisition
        
    alloc_buffers : int (default: 10)
        number of allocated buffers to use by the card
        
    SR : float (default: 2e8)
        acquisition sampling rate
        
    t_total : float (default: None)
        total time the sequence takes for this measurement.
        allows to compute the overhead.

    Returns:
    --------

    acquisition time
        the time that the ctl.acquisition call took, in seconds.

    data
        the data returned by the ctl.acquisition call.
    """

    ats_logger = qc.instrument_drivers.AlazarTech.ATS.logger
    ats_logger.setLevel(logging.DEBUG)
    
    t1 = time.perf_counter()

    ctl.setup_acquisition(samples=nsamples,
                          records=nrecords, 
                          buffers=nbuffers, 
                          acq_time=None, 
                          allocated_buffers=alloc_buffers, 
                          SR=int(SR))
    
    t2 = time.perf_counter()
    print("done:",  t2 - t1, 's')
    
    with LogCapture(logger=ats_logger) as logs:
        t0 = time.perf_counter()
        data = ctl.acquisition() 
        t1 = time.perf_counter()
    
    log_str = logs.value    
    t_acq_total = t1 - t0
    print(f'Acquistion: {t_acq_total:.6f} sec.')
    
    if t_total is not None:
        overhead = t_acq_total / t_total
        print(f'Net time: {t_total:.6f} sec.')
        print(f'Overhead: {overhead:.2f} X')

    print(f'Mean buffer handling time: {ctl.handling_times.mean():.1f} ms')

    if hasattr(ctl, 'post_acquire_time'):
        print(f'post_acquire time: {ctl.post_acquire_time:.2f} s')
            
    print('Data shape:', data.shape)
    
    print('\n', log_str)

    
    
    return t_acq_total, data
