from qcodes.utils.validators import Ints, Numbers, Lists, Dict
from qcodes.instrument.base import Instrument

import numpy as np

import time

##################################################################
################### MDAC/UHFLI parent rasterer ###################
##################################################################


class MidasUhfliParentRasterer(Instrument):
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

        self.add_parameter('bandwidth',
                        set_cmd=None,
                        initial_value=1e3,
                        vals=Ints(1,2**15),
                        docstring="Bandwidth of the UHFLI filter."
                        " This is roughly equivalent to the integraton time."
                        " Total sweep time uses 1.2/bandwidth as a time per point.")

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


class MidasUhfli1DRasterer(MidasUhfliParentRasterer):

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
        return self.npts()/self.bandwidth()*1.2

    ################### Other functions ###################

    def prepare_UHFLI(self):
        """
        Sets up the UHFLI to do the acquisition.
        Due to problems with QCoDeS driver all settings of
        daq_module are done by directly accessinf the data
        server, which should be changed whenever possible.
        """
        
        # Set oscillators and demodulation
        for ch in self.UHFLI_channel_specs().keys():
            uhfli.demods[ch+1].timeconstant(1/self.bandwidth())
            uhfli.demods[ch+1].rate(5/self.bandwidth())
            uhfli.demods[ch+1].oscselect(ch)


        # Set DAQ
        self.daq_module = uhfli._controller._controller._connection._daq.dataAcquisitionModule()
        self.daq_module.set("device", self.UHFLI_serial)

        # subscribe to relevant channels (select chanels and quadratures)
        self.signals = []
        for ch, quadratures in self.UHFLI_channel_specs().items():
            for q in quadratures:
                if q == 'P':
                    signal = f'/{self.UHFLI_serial:s}/demods/{ch-1}/sample.theta'
                    theta
                else:
                    signal = f'/{self.UHFLI_serial:s}/demods/{ch-1}/sample.{q}'
                self.signals.append(signal)
                self.daq_module.subscribe(signal)

        # Trigger settings
            # Signal
        self.daq_module.set('triggernode',f'/{serial:s}/demods/0/sample.TrigIn1')
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


    def fn_start(self):
        """
        This function is exectued by seld.do_acquisition
        just after telling UHFLI to wait for triggers
        """
        self.MDAC.run()

    def finalize(self):
        MDAC_ch = self.MDAC.channels[self.MDAC_channel()-1]
        MDAC_ch.ramp(self.V_start, ramp_rate=self.ramp_rate*5)
        MDAC_ch.voltage(self.V_start)

    def do_acquisition(self):
        """
        Executes a MIDAS capture method
        and returns an ndarray with the data.
        """
        self.daq_module.execute()

        self.fn_start()

        while not self.daq_module.finished():
            time.sleep(0.01)

        self.daq_module.finish()
        self.daq_module.unsubscribe('*')

        results = self.daq_module.read(True)
        data = np.array([results[str.lower(signal)][0]['value'][0] for signal in signals])

        return data

    def get_measurement_range(self):
        """
        Returns arrays with voltage ranges
        corresponding to the data.
        """
        return np.linspace(self.V_start/self.MDAC_divider() - self.MDAC_Vpp()/2,
                           self.V_start/self.MDAC_divider() + self.MDAC_Vpp()/2,
                           self.npts())