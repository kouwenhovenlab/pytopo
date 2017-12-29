from collections import OrderedDict
import numpy as np

from qcodes.instrument_drivers.AlazarTech.acq_controllers import ATS9360Controller
from qcodes.instrument_drivers.AlazarTech.acq_controllers.\
    alazar_channel import AlazarChannel

from ..qctools import instruments as instools
from ..experiment.measurement import Parameter, BaseMeasurement


class AlazarMeasurement(BaseMeasurement):

    controller_cls = ATS9360Controller
    ats_nchans = 2

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)

        self.add_parameter('ats_int_time', Parameter, initial_value=1e-6)
        self.add_parameter('ats_int_delay', Parameter, initial_value=2e-7)
        self.add_parameter('ats_demod', Parameter, initial_value=False)
        self.add_parameter('ats_integrate_samples', Parameter, initial_value=False)
        self.add_parameter('ats_average_records', Parameter, initial_value=False)
        self.add_parameter('ats_average_buffers', Parameter, initial_value=True)
        self.add_parameter('ats_records_per_buffer', Parameter, initial_value=1)

        self.add_parameter('IF', Parameter, initial_value=1e6)
        self.add_parameter('navgs', Parameter, initial_value=1)

        self.samples_per_record = None


    def _setup_channels(self, **kw):
        self.chans = []
        for c in ['A', 'B']:
            _chan = AlazarChannel(self.station.alazar_ctl,
                                  'chan'+c,
                                  demod=self.ats_demod(),
                                  integrate_samples=self.ats_integrate_samples(),
                                  average_records=self.ats_average_records(),
                                  average_buffers=self.ats_average_buffers())
            self.station.alazar_ctl.channels.append(_chan)
            self.chans.append(_chan)

            if self.ats_demod():
                _chan.demod_freq(self.IF())
                _chan.demod_type('IQ')

        self.station.alazar_ctl.int_time(self.ats_int_time())
        self.station.alazar_ctl.int_delay(self.ats_int_delay())
        self.samples_per_record = self.station.alazar_ctl.samples_per_record()


        for c, n in zip(self.chans, ['A', 'B']):
            c.num_averages(self.navgs())
            if not self.ats_average_records():
                c.records_per_buffer(self.ats_records_per_buffer())
            c.alazar_channel(n)
            c.prepare_channel()


    def setup_alazar(self, **kw):
        if hasattr(self.station, 'alazar_ctl'):
            del self.station.components['alazar_ctl']

        _ctl = instools.create_inst(self.controller_cls, 'alazar_ctl',
                                    alazar_name='alazar', filter='ave',
                                    force_new_instance=True)
        self.station.add_component(_ctl)
        self.station.alazar.config(**self.namespace.ats_settings)
        self._setup_channels()

    def acquire(self):
        return self.station.alazar_ctl.channels.data()



class AlzTimeTrace(AlazarMeasurement):

    def measure(self):
        self.setup_alazar()

        A, B = self.acquire()
        tvals = np.arange(A.size) / float(self.station.alazar.sample_rate()) * 1e6

        dset = OrderedDict(
            {
                'time' : {'value' : tvals, 'unit' : 'us', 'independent_parameter': True},
                'A' : {'value' : A, 'unit' : 'V'},
                'B' : {'value' : B, 'unit' : 'V'},
            }
        )

        self.data.add(dset)
