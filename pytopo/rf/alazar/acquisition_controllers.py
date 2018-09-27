import time
import numpy as np
from qcodes.instrument_drivers.AlazarTech.ATS import AcquisitionController

class BaseAcqCtl(AcquisitionController):
    """
    The baseclass for all the controllers in this file. Implements the basic
    getting of data but does not implement any of the data shaping,
    demodulation or averaging.
    """
    MINSAMPLES = 256
    CONVERT_TO_VOLTS = True

    _datadtype = None

    def __init__(self, name, alazar_name, allocate_samples=0, **kwargs):
        self.acquisitionkwargs = {}
        self.number_of_channels = 2
        self.pre_acquire_func = None
        self.post_acquire_func = None
        
        self._nbits = 12
        self._model = 'ATS9360'
        self._buffer_order = 'brsc'
        self._cur_block_idx = 0
        self._nblocks = 1

        self.data = None
        self.tvals = None

        super().__init__(name, alazar_name, **kwargs)

        if self._alazar is not None:
            alz = self._alazar
            
            self.add_parameter('sample_rate', get_cmd=alz.sample_rate)
            self.add_parameter('samples_per_record', get_cmd=alz.samples_per_record)
            self.add_parameter('records_per_buffer', get_cmd=alz.records_per_buffer)
            self.add_parameter('buffers_per_acquisition', get_cmd=alz.buffers_per_acquisition)
            self.add_parameter('acq_time', get_cmd=None, set_cmd=None, unit='s', initial_value=None)
            self.add_parameter("acquisition", get_cmd=self.do_acquisition, snapshot_value=False)

            _idn = alz.IDN()
            self._nbits = _idn['bits_per_sample']
            self._model = _idn['model']
            
            if self._model == 'ATS9870':
                self._buffer_order = 'bcrs'

        else:
            self.add_parameter('sample_rate', set_cmd=None)
            self.add_parameter('samples_per_record', set_cmd=None)
            self.add_parameter('records_per_buffer', set_cmd=None)
            self.add_parameter('buffers_per_acquisition', set_cmd=None)

        self.add_parameter('average_buffers', set_cmd=None, initial_value=False)
        self.add_parameter('buffers_per_block', set_cmd=None, initial_value=None)

        if self._datadtype is None:
            if self._nbits == 8:
                self._datadtype = np.uint8
            elif self._nbits == 12:
                self._datadtype = np.uint16
            else:
                raise ValueError('Unsupported number of bits per samples:', self._nbits)
            
        if allocate_samples > 0:
            self.allocate_data(allocate_samples)

    def allocate_data(self, nsamples):
        if self._datadtype is None:
            print('No dtype set, cannot allocate data at this point.')
            return

        nsamples = int(nsamples)
        print(f'Allocating {nsamples} elements ({self.samples2MB(nsamples)} MB)')
        self.data = np.zeros(nsamples, dtype=self._datadtype) 
        
        # this is to circumvent lazy allocation of data
        _ = self.data.sum()
        return True

    def setup_acquisition(self, samples, records, buffers, 
                          allocated_buffers=None, acq_time=None, SR=None):
        alazar = self._alazar
        
        if SR is None:
            SR = alazar.sample_rate()
        
        if allocated_buffers is None:
            nalloc = buffers
        else:
            nalloc = allocated_buffers
            
        if acq_time is not None:
            n_samples_per_record = int(acq_time * SR // 128 * 128)
        else:
            n_samples_per_record = int(samples)

        with alazar.syncing():
            alazar.sample_rate(SR)
            alazar.samples_per_record(n_samples_per_record)
            alazar.records_per_buffer(records)
            alazar.buffers_per_acquisition(buffers)
            alazar.allocated_buffers(nalloc)
        
        if self.buffers_per_block() is not None and self.average_buffers():
            self._nblocks = int(np.ceil(self.buffers_per_acquisition()/self.buffers_per_block()))
        else:
            self._nblocks = 1

        mbpr = self.samples2MB(n_samples_per_record * self.number_of_channels)
        mbpb = mbpr * records
        mbpa = mbpb * buffers
        mbpalloc = nalloc * mbpb
                
        print(f'Setup capture: {mbpa} MB total')
        print(f' * Buffers: {buffers} ({mbpb} MB/buffer) '
              f'| (Allocated buffers: {nalloc} = {mbpalloc} MB)')
        print(f' * Records: {records} ({mbpr} MB/record)') 
        print(f' * Samples: {n_samples_per_record} (= {n_samples_per_record/SR * 1e6} us)')
        print(f' * Channels:', self.number_of_channels)
        
        if self._buffer_order == 'brsc':
            self.buffer_shape = (self.records_per_buffer(),
                                 self.samples_per_record(),
                                 self.number_of_channels)
        elif self._buffer_order == 'bcrs':
            self.buffer_shape = (self.number_of_channels,
                                 self.records_per_buffer(),
                                 self.samples_per_record(),)
        else:
            raise ValueError('Unknown buffer order {}'.format(self._buffer_order))
        
        self.data_size = np.prod(self.buffer_shape)
        if not self.average_buffers():
            self.data_size *= self.buffers_per_acquisition()
        elif self.average_buffers() and self._nblocks > 1:
            self.data_size *= self._nblocks

        self.data[:self.data_size] = 0

        if self.data is None:
            self.allocate_data(self.data_size)
        
        if self.data.size < self.data_size:
            print(f'Currently allocated data not sufficient: '
                   'Need {self.data_size}, have {self.data.size}')
            self.allocate_data(self.data_size)

        if self.data.dtype != self._datadtype:
            print(f'Currently allocated data has incorrect dtype. Re-allocate.')
            self.allocate_data(self.data.size)
            
        self.tvals = np.arange(self.samples_per_record(), dtype=np.float32) \
                        / alazar.sample_rate()
    
    def data_shape(self):
        """
        Implement this method to return the shape of this data produced
        by a a given subclass of this controller.
        Should be returned as a tuple of ints.
        """
        raise NotImplementedError


    def process_buffer(self, buf):
        """
        Implement this method to perform averaging specific for this controller.
        This does not include averaging over buffers as this is performed directly
        in handle_buffer.
        """
        raise NotImplementedError
        
    def samples2MB(self, n):
        """Calculate how much memory in PC a given number of samples will take"""
        #     -n- -mega- --------------------bytes-------
        return n * 1e-6 * np.dtype(self._datadtype).itemsize

    def time2samples(self, t):
        alazar = self._alazar
        nsamples_ideal = t * alazar.sample_rate()
        nsamples = int(nsamples_ideal // 128 * 128)
        return max(self.MINSAMPLES, nsamples)
    
    def pre_start_capture(self):            
        self.handling_times = np.zeros(self.buffers_per_acquisition(), dtype=np.float64)
        self._cur_block_idx = 0
    
    def pre_acquire(self):
        if self.pre_acquire_func:
            self.pre_acquire_func()
    
    def handle_buffer(self, data, buffer_number=None):
        t0 = time.perf_counter()

        if buffer_number is not None and self.buffers_per_block() is not None:
            self._cur_block_idx = buffer_number // self.buffers_per_block()
        else:
            self._cur_block_idx = 0
        
        data.shape = self.buffer_shape
        if self._buffer_order == 'bcrs':
            data = data.transpose((1,2,0))
        
        data = self.process_buffer(data)        
        data = data.reshape(-1)        
        n = data.size
        
        if buffer_number is None or self.average_buffers():
            self.data[self._cur_block_idx*n : (self._cur_block_idx+1)*n] += data
            self.handling_times[0] = (time.perf_counter() - t0) * 1e3
        else:
            self.data[buffer_number*n : (buffer_number+1)*n] = data
            self.handling_times[buffer_number] = (time.perf_counter() - t0) * 1e3

    def post_acquire(self):
        if self.post_acquire_func:
            self.post_acquire_func()
            
        return self.data[:self.data_size].reshape(self.data_shape())
        
    def do_acquisition(self):
        if self._alazar is not None:
            value = self._alazar.acquire(acquisition_controller=self)
        else:
            value = None
        return value

    
class TestCtl(BaseAcqCtl):
        
    def data_shape(self):
        return -1

    def process_buffer(self, buf):
        return np.array([0])

    def post_acquire(self):
        return np.array([0])
    

class RawAcqCtl(BaseAcqCtl):
    """
    A controller that returns the data as received from the Alazar card in
    a 4 dimensional array. Buffers x Records x Samples X Channels. No postprocessing
    is performed.
    """
    
    def data_shape(self):
        """
        Shape of the data that this controller will produce

        Returns:
            A tuple of the sizes of the data dimensions.
        """
        if self.average_buffers():
            shp = (self._nblocks,
                   1,
                   self.records_per_buffer(),
                   self.samples_per_record(),
                   self.number_of_channels)
        else:
            shp = (1,
                   self.buffers_per_acquisition(),
                   self.records_per_buffer(),
                   self.samples_per_record(),
                   self.number_of_channels)
        return shp

    def process_buffer(self, buf):
        """
        Return data as is without any averaging.
        """                
        return buf

    def post_acquire(self):

        t0 = time.perf_counter()
        data = super().post_acquire()
        
        alz = self._alazar
        rng = np.array([alz.channel_range1(), alz.channel_range2()])
        rng = rng.reshape((len(data.shape)-1)*(1,) + (2,))
        
        if self._nbits == 12:
            data = np.right_shift(data, 4)
        data = ((data.astype(np.float32) / (2**self._nbits)) - 0.5) * 2 * rng
        if self.average_buffers():
            data /= self.buffers_per_acquisition()
            data *= self._nblocks

        self.post_acquire_time = time.perf_counter() - t0
        return data


class PostDemodCtl(BaseAcqCtl):

    _datadtype = np.int32

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)

        self.post_acquire_time = 0

        self.add_parameter('demod_frq', set_cmd=None, initial_value=1e6)

    def setup_acquisition(self, *arg, **kw):
        demod_frq = kw.pop('demod_frq', None)
        
        super().setup_acquisition(*arg, **kw)

        if demod_frq is not None:
            self.demod_frq(demod_frq)
        
        if self.demod_frq() is None:
            raise ValueError('No valid demodulation frequency set.')

        shp = (1, 1, 1, self.tvals.size, 1)
        self.cosarr = np.cos(2 * np.pi * self.tvals * self.demod_frq()).reshape(shp)
        self.sinarr = np.sin(2 * np.pi * self.tvals * self.demod_frq()).reshape(shp)
        
        self.period = int(self.sample_rate() / self.demod_frq() + 0.5)
        self.demod_samples = self.samples_per_record() // self.period
        self.demod_tvals = self.tvals[::self.period][:self.demod_samples]

    def data_shape(self):
        if self.average_buffers():
            shp = (self._nblocks,
                   1,
                   self.records_per_buffer(),
                   self.samples_per_record(),
                   self.number_of_channels)
        else:
            shp = (1,
                   self.buffers_per_acquisition(),
                   self.records_per_buffer(),
                   self.samples_per_record(),
                   self.number_of_channels)
        return shp

    def process_buffer(self, buf):
        return buf

    def post_acquire(self):
        """Demodulate the data and average over period of
        sample_rate//demod_frq rounded up to nearest integer"""
        
        t0 = time.perf_counter()
        data = super().post_acquire()

        alz = self._alazar
        rng = np.array([alz.channel_range1(), alz.channel_range2()])
        rng = rng.reshape((len(data.shape)-1)*(1,) + (2,))

        if self._nbits == 12:
            data = np.right_shift(data, 4)        
        data = ((data.astype(np.float32) / (2**self._nbits)) - 0.5) * 2 * rng
        if self.average_buffers():
            data /= self.buffers_per_acquisition()
            data *= self._nblocks

        real = (data * 2 * self.cosarr)[:, :, :, :self.demod_samples*self.period,:].reshape(
            self._nblocks, -1, self.records_per_buffer(), self.demod_samples, 
                self.period, self.number_of_channels).mean(axis=-2)
        imag = (data * 2 * self.sinarr)[:, :, :, :self.demod_samples*self.period,:].reshape(
            self._nblocks, -1, self.records_per_buffer(), self.demod_samples, 
                self.period, self.number_of_channels).mean(axis=-2)

        self.post_acquire_time = time.perf_counter() - t0
        return real + 1j * imag

class PostIQCtl(PostDemodCtl):

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)

        self.add_parameter('integration_start', set_cmd=None, initial_value=None)
        self.add_parameter('integration_stop', set_cmd=None, initial_value=None)

    def post_acquire(self):

        t0 = time.perf_counter()
        z = super().post_acquire()

        if self.integration_start() is None:
            i0 = 0
        else:
            i0 = np.argmin(np.abs(self.demod_tvals - self.integration_start()))

        if self.integration_stop() is None:
            i1 = self.tvals.size
        else:
            i1 = np.argmin(np.abs(self.demod_tvals - self.integration_stop()))

        self.post_acquire_time = time.perf_counter() - t0
        return z[:, :, :, i0:i1, :].mean(axis=-2)
