import time
from collections import OrderedDict
import numpy as np

from qcodes.instrument_drivers.AlazarTech.acq_controllers import ATS9360Controller
from qcodes.instrument_drivers.AlazarTech.acq_controllers.\
    alazar_channel import AlazarChannel

from ..qctools import instruments as instools
from ..experiment.measurement import Parameter, BaseMeasurement


from qcodes.instrument_drivers.AlazarTech.ATS import AcquisitionController
import time



class AcquisitionController9360(AcquisitionController):

    ZERO = np.int16(2048)
    RANGE = 2047.5

    def __init__(self, name, alazar_name, **kwargs):
        self.acquisitionkwargs = {}
        self.sample_rate = None
        self.samples_per_record = None
        self.records_per_buffer = None
        self.buffers_per_acquisition = None
        self.number_of_channels = 2
        # self.buffer = None
        self.trigger_func = lambda x : True
        self.demod_frq = None

        # make a call to the parent class and by extension, create the parameter
        # structure of this class
        super().__init__(name, alazar_name, **kwargs)

        self.add_parameter("acquisition", get_cmd=self.do_acquisition)


    def pre_start_capture(self):
        alazar = self._get_alazar()
        self.sample_rate = alazar.sample_rate()
        self.samples_per_record = alazar.samples_per_record.get()
        self.records_per_buffer = alazar.records_per_buffer.get()
        self.buffers_per_acquisition = alazar.buffers_per_acquisition.get()

        self.data_shape = (self.buffers_per_acquisition,
                           self.records_per_buffer,
                           # self.samples_per_record,
                           self.number_of_channels)
        self.buffer_shape = (self.records_per_buffer,
                             self.samples_per_record,
                             self.number_of_channels)

        self.buffer = np.zeros(self.data_shape)
        self.data_real = np.zeros(self.data_shape, dtype=np.float32)
        self.data_imag = np.zeros(self.data_shape, dtype=np.float32)

        _t = np.arange(self.samples_per_record, dtype=np.float32)/self.sample_rate
        self.cosarr = (np.cos(2*np.pi*self.demod_frq*_t).reshape(1,-1,1)) # .astype(np.int16)
        self.sinarr = (np.sin(2*np.pi*self.demod_frq*_t).reshape(1,-1,1)) # .astype(np.int16)

        self.handling_times = np.zeros(self.buffers_per_acquisition, dtype=np.float64)


    def pre_acquire(self):
        self.trigger_func(True)


    def post_acquire(self):
        self.trigger_func(False)

        return self.data_real + 1j * self.data_imag


    def handle_buffer(self, data, buffer_number=None):
        """
        See AcquisitionController
        :return:
        """
        t0 = time.perf_counter()

        shaped_data = data.reshape(self.buffer_shape).view(np.uint16)
        shaped_data >>= 4
        shaped_data = shaped_data.view(np.int16)
        shaped_data -= self.ZERO

        real_data = np.tensordot(shaped_data, self.cosarr, axes=(-2, -2)).reshape(self.records_per_buffer, 2) / 2047.5 / self.samples_per_record
        imag_data = np.tensordot(shaped_data, self.sinarr, axes=(-2, -2)).reshape(self.records_per_buffer, 2) / 2047.5 / self.samples_per_record

        if not buffer_number:
            self.data_real += real_data
            self.data_imag += imag_data
            self.handling_times[0] = (time.perf_counter() - t0) * 1e3
        else:
            self.data_real[buffer_number] = real_data
            self.data_imag[buffer_number] = imag_data
            self.handling_times[buffer_number] = (time.perf_counter() - t0) * 1e3


    def update_acquisitionkwargs(self, **kwargs):
        """
        This method must be used to update the kwargs used for the acquisition
        with the alazar_driver.acquire
        :param kwargs:
        :return:
        """
        self.acquisitionkwargs.update(**kwargs)


    def do_acquisition(self):
        """
        this method performs an acquisition, which is the get_cmd for the
        acquisiion parameter of this instrument
        :return:
        """
        value = self._get_alazar().acquire(acquisition_controller=self, **self.acquisitionkwargs)
        return value


class AlazarMeasurement(BaseMeasurement):

    controller_cls = AcquisitionController9360
    ats_nchans = 2

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)

        self.ats_samples_per_record = 128 * 3
        self.ats_records_per_buffer = 1
        self.ats_buffers_per_acquisition = 1
        self.ats_allocated_buffers = 1

        self.add_parameter('IF', Parameter, initial_value=1e6)

        self.trigger_func = lambda x : True


    def setup_alazar(self, **kw):
        if hasattr(self.station, 'alazar_ctl'):
            del self.station.components['alazar_ctl']

        self.controller = instools.create_inst(self.controller_cls, 'alazar_ctl',
                                               alazar_name='alazar',
                                               force_new_instance=True)

        self.controller.trigger_func = self.trigger_func

        # self.station.add_component(self.controller)
        self.station.alazar.config(**self.namespace.ats_settings)

        ackw = self.namespace.ats_acq_kwargs.copy()
        ackw.update(dict(samples_per_record=self.ats_samples_per_record,
                         records_per_buffer=self.ats_records_per_buffer,
                         buffers_per_acquisition=self.ats_buffers_per_acquisition,
                         allocated_buffers=self.ats_allocated_buffers))
        self.controller.update_acquisitionkwargs(**ackw)
        self.controller.demod_frq = self.IF()

    def acquire(self):
        return self.controller.acquisition()

    def setup(self):
        super().setup()
        self.setup_alazar()


# class AlzTimeTrace(AlazarMeasurement):

#     def measure(self):
#         A, B = self.acquire()
#         tvals = np.arange(A.size) / float(self.station.alazar.sample_rate()) * 1e6

#         dset = OrderedDict(
#             {
#                 'time' : {'value' : tvals, 'unit' : 'us', 'independent_parameter': True},
#                 'A' : {'value' : A, 'unit' : 'V'},
#                 'B' : {'value' : B, 'unit' : 'V'},
#             }
#         )

#         self.data.add(dset)
