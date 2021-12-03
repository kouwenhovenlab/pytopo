from qcodes.utils.validators import Ints, Numbers, Lists, Dict
from qcodes.instrument.base import Instrument

import numpy as np

import time

##################################################################
################### MDAC/UHFLI parent rasterer ###################
##################################################################


class MdacUhfliParentRasterer(Instrument):
    """
    Parent class to the 1DSlow, 1DFast and 2D rasterers
    """

    def __init__(self, name, UHFLI_name, MDAC_name, **kwargs):
        """
        Create a MidasMdacAwgRasterer instance

        Args:
            name (str): rasterer instrument name
            UHFLI_name (str): name of the UHFLI to be used
            MDAC_name (str): name of the MDAC to be used
            **kwargs: other kwargs passed to Instrument init

        Returns:
            MidasUhfliParentRasterer
        """

        super().__init__(name, **kwargs)

        self.UHFLI = self.find_instrument(UHFLI_name)
        self.UHFLI_serial = self.UHFLI._serial
        self.MDAC = self.find_instrument(MDAC_name)

        self.add_parameter('UHFLI_channel_specs',
                            set_cmd=None,
                            initial_value={1:'XY'},
                            docstring="Dictionary specyfying quantities to"
                            " measure. Keys are the cjannel numbers (int)."
                            " Valuses are strings, up to 4 letters from"
                            " the set X, Y, R, P which stand for"
                            " (I, Q, Amplitude or Phase).")

        self.add_parameter('UHFLI_phase_offsets',
                            set_cmd=None,
                            initial_value={i:0 for i in range(1,9)},
                            docstring="Add a phase offset when measuring phase"
                            " WARNING! Phase offset is not added when measuring X or Y!")

        self.add_parameter('UHFLI_trigger_channel',
                            set_cmd=None,
                            initial_value=1,
                            docstring="")

        self.add_parameter('time_constant',
                        set_cmd=None,
                        initial_value=1e-3,
                        vals=Numbers(1e-6,1),
                        docstring="Time constant of the UHFLI filter."
                        " This is roughly equivalent to the integraton time."
                        " Total sweep time uses 3*time_constant as a time per point.")

        # only gettable
        self.add_parameter('UHFLI_channels',
                            get_cmd=self._get_UHFLI_channels,
                            docstring="List of UHFLI demodulators used")

    ################### Get functions ###################
    def _get_UHFLI_channels(self):
        return list(self.UHFLI_channel_specs().keys())

    ################### Other functions ###################

    def prepare_UHFLI(self):
        """
        Sets up the UHFLI to do the acquisition.
        Should be implemented in a subclass.
        """
        raise NotImplementedError(
            'This method should be implemented in a subclass')

    def prepare_MDAC(self):
        """
        Sets up the MDAC to do the acquisition.
        Should be implemented in a subclass.
        """
        raise NotImplementedError(
            'This method should be implemented in a subclass')

    def fn_start(self):
        """
        This function will be exectued by
        just after execution of the measurement.
        Should be implemented in a subclass.
        """
        raise NotImplementedError(
            'This method should be implemented in a subclass')

    def do_acquisition(self):
        """
        Executes a UHFLI capture method
        and returns an ndarray with the data.
        Should be implemented in a subclass.
        """
        raise NotImplementedError(
            'This method should be implemented in a subclass')

    def get_measurement_range(self):
        """
        Returns arrays with voltage ranges
        corresponding to the data.
        Should be implemented in a subclass.
        """
        raise NotImplementedError(
            'This method should be implemented in a subclass')

    def prepare_for_acquisition(self):
        self.prepare_UHFLI()
        self.prepare_MDAC()



##################################################################
##################### 1D MDAC/UHFLI rasterer #####################
##################################################################


class MdacUhfli1DRasterer(MdacUhfliParentRasterer):

    def __init__(self, name, UHFLI_name, MDAC_name, **kwargs):

        super().__init__(name,
                UHFLI_name, MDAC_name,
                **kwargs)

        self.add_parameter('MDAC_channel',
                            set_cmd=None,
                            initial_value=None,
                            vals=Ints(min_value=1,max_value=64),
                            docstring="MDAC channels to be sweeped.")

        self.add_parameter('MDAC_Vpp',
                            set_cmd=None,
                            initial_value=0.1,
                            vals=Numbers(min_value=0),
                            docstring="Amplitude of a single sweep with"
                            " MDAC. DC offset is given by the current setting"
                            " of the MDAC channel. After acquisition the channel"
                            " voltage is set back to the initial value.")

        self.add_parameter('MDAC_divider',
                            set_cmd=None,
                            initial_value=1,
                            vals=Numbers(min_value=1),
                            docstring="Voltage divider to take into account")

        self.add_parameter('npts',
                            set_cmd=None,
                            initial_value=64,
                            vals=Ints(1,2048),
                            docstring="Number of points in a 1D sweep")

        # only gettable
        self.add_parameter('sweep_time',
                            get_cmd=self._get_sweep_time,
                            docstring="")

    #################### Get functions ###################
    def _get_sweep_time(self):
        return self.npts()*self.time_constant()*3

    ################### Other functions ###################

    def prepare_UHFLI(self):
        """
        Sets up the UHFLI to do the acquisition.
        Due to problems with QCoDeS driver all settings of
        daq_module are done by directly accessinf the data
        server, which should be changed whenever possible.
        """
        
        for c in range(8):
            self.UHFLI.sigouts[0][f'enables{c}'](0)

        # Set oscillators and demodulation
        for ch in self.UHFLI_channel_specs().keys():
            self.UHFLI.demods[ch-1].timeconstant(self.time_constant())
            self.UHFLI.demods[ch-1].rate(5/self.time_constant())
            self.UHFLI.demods[ch-1].oscselect(ch-1)
            self.UHFLI.sigouts[0][f'enables{ch-1}'](1)



        # Set DAQ
        self.daq_module = self.UHFLI._controller._controller._connection._daq.dataAcquisitionModule()
        self.daq_module.set("device", self.UHFLI_serial)

        # subscribe to relevant channels (select chanels and quadratures)
        self.signals = []
        for ch, quadratures in self.UHFLI_channel_specs().items():
            for q in quadratures:
                if q == 'P':
                    signal = f'/{self.UHFLI_serial:s}/demods/{ch-1}/sample.theta'
                else:
                    signal = f'/{self.UHFLI_serial:s}/demods/{ch-1}/sample.{q}'
                self.signals.append(signal)
                self.daq_module.subscribe(signal)

        # Trigger settings
            # Signal
        self.daq_module.set('triggernode',f'/{self.UHFLI_serial:s}/demods/0/sample.TrigIn{self.UHFLI_trigger_channel()}')
            # Type, 6 = hardware trigger
        self.daq_module.set('type',6)
            # Edge, 1=positive
        self.daq_module.set('edge',1)
        # Horizontal
            # Hold off time
        self.daq_module.set('/holdoff/time',0.0)
            # Delay
        self.daq_module.set('/delay',0)

        # Configure Grid trab
        self.daq_module.set('grid/mode',2)   # linear
        #self.daq_module.set('grid/mode',4)   # exact
        #self.daq_module.set('grid/mode',1)   # nearest
        self.daq_module.set("grid/cols",self.npts())
        self.daq_module.set("grid/rows",1)
        self.daq_module.set("duration", self.sweep_time())
        self.daq_module.set("count",1)

        self.daq_module.set('clearhistory',1)
        self.daq_module.set('endless', 0)


    def prepare_MDAC(self):
        """
        Sets up the MDAC to do the acquisition.
        """
        MDAC_ch = self.MDAC.channels[self.MDAC_channel()-1]
        MDAC_ch.attach_trigger()

        self.V_start = MDAC_ch.voltage()

        # calculate the rate of the MDAC sweep
        self.ramp_rate = self.MDAC_Vpp()/self.sweep_time()

        MDAC_ch.awg_sawtooth(1/self.sweep_time(), self.MDAC_Vpp()*self.MDAC_divider(), offset=self.V_start)
        self.MDAC.stop()

    def arm(self):
        pass

    def fn_start(self):
        """
        This function is exectued by seld.do_acquisition
        just after telling UHFLI to wait for triggers
        """
        self.MDAC.run()

    def end(self):
        pass

    def finalize(self):
        MDAC_ch = self.MDAC.channels[self.MDAC_channel()-1]
        MDAC_ch.ramp(self.V_start, ramp_rate=self.ramp_rate*5)
        MDAC_ch.voltage(self.V_start)

        self.daq_module.finish()
        self.daq_module.unsubscribe('*')

        for ch in self.UHFLI_channel_specs().keys():
            self.UHFLI.sigouts[0][f'enables{ch-1}'](0)

    def do_acquisition(self):
        """
        Executes a UHFLI capture method
        and returns an ndarray with the data.
        """
        self.arm()

        self.daq_module.execute()

        self.fn_start()

        while not self.daq_module.finished():
            time.sleep(0.01)

        results = self.daq_module.read(True)
        data = np.array([results[str.lower(signal)][0]['value'][0] for signal in self.signals])

        # adjust a phase whn phase is meanured (nut not X or Y)
        row_counter = 0
        for ch, quadratures in self.UHFLI_channel_specs().items():
            for q in quadratures:
                if q == 'P':
                    data[row_counter] = np.mod(data[row_counter]-self.UHFLI_phase_offsets()[ch], 2*np.pi)
                row_counter += 1


        self.end()

        return data

    def get_measurement_range(self):
        """
        Returns arrays with voltage ranges
        corresponding to the data.
        """
        return np.linspace(self.V_start/self.MDAC_divider() - self.MDAC_Vpp()/2,
                           self.V_start/self.MDAC_divider() + self.MDAC_Vpp()/2,
                           self.npts())

##################################################################
################ 1D multigate MDAC/UHFLI rasterer ################
##################################################################

class MdacUhfli1DMultichanRasterer(MdacUhfli1DRasterer):

    def __init__(self, name, UHFLI_name, MDAC_name, **kwargs):

        super().__init__(name,
                UHFLI_name, MDAC_name,
                **kwargs)

        self.add_parameter('MDAC_channel_dict',
                                set_cmd=None,
                                initial_value=None,
                                vals=Dict(),
                                docstring="Dictionary that specifies"
                                    " MDAC channels and amplitudes."
                                    " Format: {ch1: Vpp1, ch2: Vpp2}"
                                    " where ch# is int anf Vpp# is float")

        self.add_parameter('range_scaling',
                            set_cmd=None,
                            initial_value=1,
                            vals=Numbers(),
                            docstring="Set scaling of the measurement axis."
                                "The returned range will be"
                                " Vpp*range_scaling + range_offset"
                                " where Vpp corresponds to a channel with"
                                " the smallest number.")

        self.add_parameter('range_offset',
                            set_cmd=None,
                            initial_value=0,
                            vals=Numbers(),
                            docstring="Set offset of the measurement axis."
                                "The returned range will be"
                                " Vpp*range_scaling + range_offset"
                                " where Vpp corresponds to a channel with"
                                " the smallest number.")


    def prepare_MDAC(self):
        """
        Sets up the MDAC to do the acquisition.
        """
        # use channel with the smallest number to trigger on
        ch = min(self.MDAC_channel_dict().keys())

        MDAC_ch = self.MDAC.channels[ch-1]
        MDAC_ch.attach_trigger()


    def arm(self):

        # set waveform on all channels
        self.V_start = {}
        for ch, Vpp in self.MDAC_channel_dict().items():
            # get the MDAC channel
            MDAC_ch = self.MDAC.channels[ch-1]
            V_start = MDAC_ch.voltage()

            # save initial values
            self.V_start[ch] = V_start

            if Vpp>0:
                MDAC_ch.awg_sawtooth(1/self.sweep_time(), Vpp*self.MDAC_divider(), offset=V_start)
            else:
                MDAC_ch.awg_sawtooth_falling(1/self.sweep_time(), -Vpp*self.MDAC_divider(), offset=V_start)
        

        self.MDAC.stop()
        self.MDAC.sync()

    def end(self):
        for ch, v in self.V_start.items():
            # get the MDAC channel
            MDAC_ch = self.MDAC.channels[ch-1]
            MDAC_ch.voltage(v)


    def get_measurement_range(self):
        ch = min(self.MDAC_channel_dict().keys())
        Vpp = self.MDAC_channel_dict()[ch]
        scaling = self.range_scaling()
        offset = self.range_offset()

        return np.linspace(-Vpp*scaling/2+offset,
                           Vpp*scaling/2+offset,
                           self.npts())

    def finalize(self):
        pass

