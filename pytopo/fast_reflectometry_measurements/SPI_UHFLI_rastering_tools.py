from qcodes.utils.validators import Ints, Numbers, Lists, Dict
from qcodes.instrument.base import Instrument

import numpy as np

import time

##################################################################
################### SPI/UHFLI parent rasterer ###################
##################################################################


class SpiUhfliParentRasterer(Instrument):
    """
    Parent class to the 1DSlow, 1DFast and 2D rasterers
    """

    def __init__(self, name, UHFLI_name, SPI_name, **kwargs):
        """
        Create a MidasMdacAwgRasterer instance

        Args:
            name (str): rasterer instrument name
            UHFLI_name (str): name of the UHFLI to be used
            SPI_name (str): name of the MDAC to be used
            **kwargs: other kwargs passed to Instrument init

        Returns:
            MidasUhfliParentRasterer
        """

        super().__init__(name, **kwargs)

        self.UHFLI = self.find_instrument(UHFLI_name)
        self.UHFLI_serial = self.UHFLI._serial
        self.SPI_module = self.find_instrument(SPI_name)

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

    def prepare_SPI(self):
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
        self.prepare_SPI()



##################################################################
##################### 1D MDAC/UHFLI rasterer #####################
##################################################################


class SpiUhfli1DRasterer(MdacUhfliParentRasterer):

    def __init__(self, name, UHFLI_name, MDAC_name, **kwargs):

        super().__init__(name,
                UHFLI_name, MDAC_name,
                **kwargs)

        self.add_parameter('SPI_channel',
                            set_cmd=None,
                            initial_value=None,
                            vals=Ints(min_value=1,max_value=2),
                            docstring="SPI channels to be sweeped.")

        self.add_parameter('SPI_Vpp',
                            set_cmd=None,
                            initial_value=0.1,
                            vals=Numbers(min_value=0),
                            docstring="Amplitude of a single sweep with"
                            " SPI-rack. DC offset is given by the current setting"
                            " of the SPI channel. After acquisition the channel"
                            " voltage is set back to the initial value.")

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


    def prepare_SPI(self):
        """
        Sets up the SPI to do the acquisition.
        """
        self.SPI_module.configure_globals(30e-6,self.sweep_time())
        self.SPI_module.set_start_holdoff_time(30e-6)

        # set ch 0 to constant
        v0 = self.SPI_module.get_DAC_voltages(0)[0]
        self.SPI_module.configure_fine_ramp(0, 'repeated', v0, v0, self.sweep_time())
        v2 = self.SPI_module.get_DAC_voltages(2)[0]
        self.SPI_module.configure_fine_ramp(2, 'repeated', v2,v2, self.sweep_time())

        self.V_start = self.SPI_module.get_DAC_voltages(self.SPI_channel()*2)[0]
        v_start = self.V_start-self.SPI_Vpp()/2
        v_stop = self.V_start+self.SPI_Vpp()/2
        self.SPI_module.configure_fine_ramp(self.SPI_channel()*2, 'repeated', v_start, v_stop, self.sweep_time())

        D5c.calc_DAC_step_size(0)
        D5c.calc_DAC_step_size(2)

    def arm(self):
        pass

    def fn_start(self):
        """
        This function is exectued by seld.do_acquisition
        just after telling UHFLI to wait for triggers
        """
        self.SPI_module.software_start()

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
        return np.linspace(self.V_start - self.MDAC_Vpp()/2,
                           self.V_start + self.MDAC_Vpp()/2,
                           self.npts())

