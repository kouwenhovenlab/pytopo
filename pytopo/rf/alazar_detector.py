import numpy as np
from ..qctools.hard_sweep import HardSweepDetector

class AlazarBaseDetector(HardSweepDetector):
    
    def __init__(self, name, acqctl, sweep_params=['buffers', 'records'], **kwargs):
        self.acqctl = acqctl        
        self._time = None
        self._signal_real = None
        self._signal_imag = None
        self._signal_abs = None

        inner_dims = []
        for d in self.acqctl.data_dims():
            if d not in sweep_params:
                inner_dims.append(d)
        
        super().__init__(name, inner_dims=inner_dims, **kwargs)
        
        self.add_parameter('acquisition', get_cmd=self.do_acquisition, unit='V', snapshot_value=False)
        self.add_parameter('signal_real', get_cmd=lambda: self._signal_real, unit='V', snapshot_value=False)
        self.add_parameter('signal_imag', get_cmd=lambda: self._signal_imag, unit='V', snapshot_value=False)
        self.add_parameter('signal_abs', get_cmd=lambda: self._signal_abs, unit='V', snapshot_value=False)
        self.data_params = [self.signal_real, self.signal_imag, self.signal_abs]
        
        if 'samples' in self.inner_dims or 'IF_periods' in self.inner_dims:
            self.add_parameter('time', unit='s', snapshot_value=False, 
                               get_cmd=lambda: self._time)

    def setup(self):
        ### TODO:
        # We should have an option that it's possible to not specify all dimensions,
        # and basically set the shape to (-1, xxx), i.e., set the first one automatic.
        # that might then be an implicit averaging dimension, for example.
        # then sweepers can be used for both avering over buffers, or single-shot        
        for d in self.inner_dims:
            idx = self.acqctl.data_dims().index(d)
            try:
                npts = self.acqctl.data_shape()[idx]
            except:
                npts = 1
            self.set(d, np.arange(npts))
            
        super().setup()
    
    
    def do_acquisition(self):
        data = self.acqctl.acquisition()
        self.setup()
        
        if 'samples' in self.inner_dims:
            self._time = self.acqctl.tvals
        elif 'IF_periods' in self.inner_dims:
            self._time = self.acqctl.demod_tvals
            
        self._signal_real = np.real(data)
        self._signal_imag = np.imag(data)
        self._signal_abs = np.abs(data)
        
        return data

    
class AlazarDetector(AlazarBaseDetector):
    
    def __init__(self, name, acqctl, **kwargs):
        kwargs['sweep_params'] = ['buffers', 'records']
        
        super().__init__(name, acqctl, **kwargs)
        
        self.add_parameter('avg_buffers', set_cmd=None, initial_value=True)
        self.add_parameter('acq_time', 
                           get_cmd=lambda: self.acqctl.acq_time(), 
                           set_cmd=lambda x: self.acqctl.acq_time(x))
        
        if hasattr(self.acqctl, 'demod_frq'):
            self.add_parameter('demod_frq', 
                               get_cmd=lambda: self.acqctl.demod_frq(), 
                               set_cmd=lambda x: self.acqctl.demod_frq(x))
        
    def configure_alazar(self, **kwargs):
        defaults = dict(
            buffer_timeout = 10000,
            allocated_buffers = 1,
        )
        defaults.update(kwargs)
        self.acqctl.update_acquisitionkwargs(**defaults)
        
    def do_acquisition(self):
        data = super().do_acquisition()
        
        if self.avg_buffers() and 'buffers' in self.acqctl.data_dims():
            bidx = self.acqctl.data_dims().index('buffers')
            data = data.mean(axis=bidx)
            
            self._signal_real = np.real(data)
            self._signal_imag = np.imag(data)
            self._signal_abs = np.abs(data)
            
        return data