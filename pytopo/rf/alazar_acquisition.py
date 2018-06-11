import time
import numpy as np
import qcodes as qc

from qcodes.instrument_drivers.AlazarTech.ATS import AcquisitionController

class BaseAcqCtl(AcquisitionController):

    ZERO = np.int16(2048)
    RANGE = 2047.5
    MINSAMPLES = 384
    DATADTYPE = np.float32

    def __init__(self, name, alazar_name, **kwargs):
        self.acquisitionkwargs = {}
        self.number_of_channels = 2
        self.trigger_func = None

        # make a call to the parent class and by extension, create the parameter
        # structure of this class
        super().__init__(name, alazar_name, **kwargs)

        alz = self._get_alazar()
        self.add_parameter('sample_rate', get_cmd=alz.sample_rate)
        self.add_parameter('samples_per_record', get_cmd=alz.samples_per_record)
        self.add_parameter('records_per_buffer', get_cmd=alz.records_per_buffer)
        self.add_parameter('buffers_per_acquisition', get_cmd=alz.buffers_per_acquisition)

        self.add_parameter('acq_time', get_cmd=None, set_cmd=None, unit='s', initial_value=None)
        self.add_parameter("acquisition", get_cmd=self.do_acquisition, snapshot_value=False)


    # Functions that need to be implemented by child classes
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

    def pre_start_capture(self):
        alazar = self._get_alazar()
        # self.sample_rate = alazar.sample_rate()
        # self.samples_per_record = alazar.samples_per_record.get()
        # self.records_per_buffer = alazar.records_per_buffer.get()
        # self.buffers_per_acquisition = alazar.buffers_per_acquisition.get()
        self.tvals = np.arange(self.samples_per_record(), dtype=np.float32) / alazar.sample_rate()

        self.buffer_shape = (self.records_per_buffer(),
                             self.samples_per_record(),
                             self.number_of_channels)

        self.data = np.zeros(self.data_shape(), dtype=self.DATADTYPE)
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

        shaped_data = data.reshape(self.buffer_shape).view(np.uint16)
        shaped_data >>= 4
        shaped_data = shaped_data.view(np.int16)
        shaped_data -= self.ZERO

        data = self.process_buffer(shaped_data)

        if not buffer_number:
            self.data += data
            self.handling_times[0] = (time.perf_counter() - t0) * 1e3
        else:
            self.data[buffer_number] = data
            self.handling_times[buffer_number] = (time.perf_counter() - t0) * 1e3

    def update_acquisitionkwargs(self, **kwargs):
        """
        This method must be used to update the kwargs used for the acquisition
        with the alazar_driver.acquire
        :param kwargs:
        :return:
        """
        if self.acq_time() and 'samples_per_record' not in kwargs:
            kwargs['samples_per_record'] = self.time2samples(self.acq_time())
        self.acquisitionkwargs.update(**kwargs)


    def do_acquisition(self):
        """
        this method performs an acquisition, which is the get_cmd for the
        acquisiion parameter of this instrument
        :return:
        """
        value = self._get_alazar().acquire(acquisition_controller=self, **self.acquisitionkwargs)
        return value


class RawAcqCtl(BaseAcqCtl):

    def data_shape(self):
        return (self.buffers_per_acquisition(),
                self.records_per_buffer(),
                self.samples_per_record(),
                self.number_of_channels)

    def data_dims(self):
        return ('buffers', 'records', 'samples', 'channels')

    def process_buffer(self, buf):
        return buf / self.RANGE / 2.


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
