import time
import numpy as np
import qcodes as qc

from qcodes.instrument_drivers.AlazarTech.ATS import AcquisitionController

class BaseAcqCtl(AcquisitionController):

    MINSAMPLES = 384

    def __init__(self, name, alazar_name, **kwargs):
        self.acquisitionkwargs = {}
        self.number_of_channels = 2
        self.trigger_func = None
        self._average_buffers = False
        self._nbits = 12
        self._model = 'ATS9360'
        self._buffer_order = 'brsc'
        
        self.do_allocate_data = True
        self.data = None
        self.tvals = None

        super().__init__(name, alazar_name, **kwargs)

        if self._alazar is not None:
            alz = self._get_alazar()
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

        if self._nbits == 8:
            self._datadtype = np.uint8
        elif self._nbits == 12:
            self._datadtype = np.uint16
        else:
            raise ValueError('Unsupported number of bits per samples:', self._nbits)


    def data_shape(self):
        raise NotImplementedError

    def data_dims(self):
        raise NotImplementedError

    def process_buffer(self, buf):
        raise NotImplementedError

    def time2samples(self, t):
        alazar = self._get_alazar()
        nsamples_ideal = t * alazar.sample_rate()
        nsamples = int(nsamples_ideal // 128 * 128)
        if nsamples / alazar.sample_rate() < t:
            nsamples += 128
        return max(self.MINSAMPLES, nsamples)

    def allocate_data(self):
        alazar = self._get_alazar()
        self.tvals = np.arange(self.samples_per_record(), dtype=np.float32) / alazar.sample_rate()
        self.data = np.zeros(self.data_shape(), dtype=self._datadtype)

    def pre_start_capture(self):
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

        if self.do_allocate_data:
            self.allocate_data()

        self.handling_times = np.zeros(self.buffers_per_acquisition(), dtype=np.float64)

    def pre_acquire(self):
        if self.trigger_func:
            self.trigger_func(True)

    def post_acquire(self):
        if self.trigger_func:
            self.trigger_func(False)

        return self.data

    def handle_buffer(self, data, buffer_number=None):
        t0 = time.perf_counter()
        data.shape = self.buffer_shape
        if self._buffer_order == 'bcrs':
            data = data.transpose((1,2,0))

        if not buffer_number or self._average_buffers:
            self.data += self.process_buffer(data)
            self.handling_times[0] = (time.perf_counter() - t0) * 1e3
        else:
            self.data[buffer_number] = self.process_buffer(data)
            self.handling_times[buffer_number] = (time.perf_counter() - t0) * 1e3


    def update_acquisitionkwargs(self, **kwargs):
        if self.acq_time() and 'samples_per_record' not in kwargs:
            kwargs['samples_per_record'] = self.time2samples(self.acq_time())
        self.acquisitionkwargs.update(**kwargs)


    def do_acquisition(self):
        if self._alazar is not None:
            value = self._get_alazar().acquire(acquisition_controller=self, **self.acquisitionkwargs)
        else:
            value = None
        return value


class RawAcqCtl(BaseAcqCtl):

    def data_shape(self):
        shp = (self.buffers_per_acquisition(),
               self.records_per_buffer(),
               self.samples_per_record(),
               self.number_of_channels)

        if not self._average_buffers:
            return shp
        else:
            return shp[1:]

    def data_dims(self):
        dims = ('buffers', 'records', 'samples', 'channels')

        if not self._average_buffers:
            return dims
        else:
            return dims[1:]

    def process_buffer(self, buf):
        return buf

    def post_acquire(self):
        data = super().post_acquire()
        if self._nbits == 12:
            data = np.right_shift(self.data, 4)

        return (data.astype(np.float32) / (2**self._nbits)) - 0.5


class AvgBufCtl(BaseAcqCtl):

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)
        self._average_buffers = True

        if self._nbits == 8:
            self._datadtype = np.uint16
        elif self._nbits == 12:
            self._datadtype = np.uint32


    def data_shape(self):
        shp = (self.records_per_buffer(),
               self.samples_per_record(),
               self.number_of_channels)
        return shp

    def data_dims(self):
        dims = ('records', 'samples', 'channels')
        return dims

    def process_buffer(self, buf):
        return buf

    def post_acquire(self):
        data = super().post_acquire()
        if self._nbits == 12:
            data = np.right_shift(self.data, 4)

        return (data.astype(np.float32) / (2**self._nbits)) - 0.5


class AvgDemodCtl(AvgBufCtl):

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)
        self.add_parameter('demod_frq', set_cmd=None, unit='Hz')

    def data_shape(self):
        self.period = int(self.sample_rate() / self.demod_frq() + 0.5)
        self.demod_samples = self.samples_per_record() // self.period
        self.demod_tvals = self.tvals[::self.period][:self.demod_samples]
        self.cosarr = (np.cos(2*np.pi*self.demod_frq()*self.tvals).reshape(1,-1,1))
        self.sinarr = (np.sin(2*np.pi*self.demod_frq()*self.tvals).reshape(1,-1,1))

        return (self.records_per_buffer(),
                self.demod_samples,
                self.number_of_channels)

    def data_dims(self):
        return ('records', 'IF_periods', 'channels')

    def pre_start_capture(self):
        super().pre_start_capture()
        self.data = np.zeros((
            self.records_per_buffer(),
            self.samples_per_record(),
            self.number_of_channels,
        )).astype(self._datadtype)

    def post_acquire(self):
        data = super().post_acquire()
        real = (data * 2 * self.cosarr)[:,:self.demod_samples*self.period,:].reshape(
            -1, self.demod_samples, self.period, self.number_of_channels).mean(axis=-2)
        imag = (data * 2 * self.sinarr)[:,:self.demod_samples*self.period,:].reshape(
            -1, self.demod_samples, self.period, self.number_of_channels).mean(axis=-2)
        return real + 1j * imag


class AvgIQCtl(AvgDemodCtl):

    def data_shape(self):
        shp = list(super().data_shape())

        return (self.records_per_buffer(),
                self.number_of_channels)

    def data_dims(self):
        return ('records', 'channels')

    def post_acquire(self):
        return super().post_acquire().mean(axis=1)



"""
####
#### OLDER, CURRENTLY NOT WORKING CONTROLLERS. NEEDS TO BE FIXED.
####

class DemodAcqCtl(BaseAcqCtl):

    DATADTYPE = np.complex64

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)
        self.add_parameter('demod_frq', set_cmd=None, unit='Hz')

    def data_shape(self):
        alazar = self._get_alazar()
        self.period = int(alazar.sample_rate() / self.demod_frq() + 0.5)
        self.demod_samples = self.samples_per_record() // self.period
        self.demod_tvals = self.tvals[::self.period][:self.demod_samples]
        self.cosarr = (np.cos(2*np.pi*self.demod_frq()*self.tvals).reshape(1,1,-1,1))
        self.sinarr = (np.sin(2*np.pi*self.demod_frq()*self.tvals).reshape(1,1,-1,1))

        return (self.buffers_per_acquisition(),
                self.records_per_buffer(),
                self.demod_samples,
                self.number_of_channels)

    def data_dims(self):
        return ('buffers', 'records', 'IF_periods', 'channels')

    def process_buffer(self, buf):
        real_data = (buf * self.cosarr)[:, :, :self.demod_samples*self.period, :]
        real_data = real_data.reshape(-1, self.demod_samples, self.period, 2).mean(axis=-2) / self.RANGE

        imag_data = (buf * self.sinarr)[:, :, :self.demod_samples*self.period, :]
        imag_data = imag_data.reshape(-1, self.demod_samples, self.period, 2).mean(axis=-2) / self.RANGE

        return real_data + 1j * imag_data


class DemodRelAcqCtl(DemodAcqCtl):

    REFCHAN = 0
    SIGCHAN = 1

    def data_shape(self):
        ds = list(super().data_shape())
        return tuple(ds[:-1])

    def data_dims(self):
        return ('buffers', 'records', 'IF_periods')

    def process_buffer(self, buf):
        data = super().process_buffer(buf)
        phi = np.angle(data[:, :, self.REFCHAN])
        return data[:, :, self.SIGCHAN] * np.exp(-1j*phi)


class IQAcqCtl(BaseAcqCtl):

    DATADTYPE = np.complex64

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)

        self.add_parameter('demod_frq', set_cmd=None, unit='Hz')

    def data_shape(self):
        alazar = self._get_alazar()
        self.period = int(alazar.sample_rate() / self.demod_frq() + 0.5)
        self.cosarr = (np.cos(2*np.pi*self.demod_frq()*self.tvals).reshape(1,1,-1,1))
        self.sinarr = (np.sin(2*np.pi*self.demod_frq()*self.tvals).reshape(1,1,-1,1))

        return (self.buffers_per_acquisition(),
                self.records_per_buffer(),
                self.number_of_channels)

    def data_dims(self):
        return ('buffers', 'records', 'channels')

    def process_buffer(self, buf):
        real_data = np.tensordot(buf, self.cosarr, axes=(-2, -2)).reshape(self.records_per_buffer(), 2) / self.RANGE / self.samples_per_record()
        imag_data = np.tensordot(buf, self.sinarr, axes=(-2, -2)).reshape(self.records_per_buffer(), 2) / self.RANGE / self.samples_per_record()
        return real_data + 1j * imag_data


class IQRelAcqCtl(IQAcqCtl):

    REFCHAN = 0
    SIGCHAN = 1

    def data_shape(self):
        ds = list(super().data_shape())
        return tuple(ds[:-1])

    def data_dims(self):
        return ('buffers', 'records')

    def process_buffer(self, buf):
        data = super().process_buffer(buf)
        phi = np.angle(data[..., self.REFCHAN])
        return data[..., self.SIGCHAN] * np.exp(-1j*phi)
"""
