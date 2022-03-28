from qcodes.utils.validators import Ints, Numbers, Lists, Dict
from qcodes.instrument.base import Instrument

import numpy as np

import time

##################################################################
###################### 1D MDAC/VNA rasterer ######################
##################################################################

class VNAMDACRasterer(Instrument):
    
    def __init__(self, name, VNA_name, MDAC_name, **kwargs):
        """
        Create a MidasMdacAwgRasterer instance

        Args:
            name (str): rasterer instrument name
            VNAS_name (str): name of the VNA to be used
            MDAC_name (str): name of the MDAC to be used
            **kwargs: other kwargs passed to Instrument init

        Returns:
            MidasMdacAwgRasterer
        """

        super().__init__(name, **kwargs)

        self.MDAC = self.find_instrument(MDAC_name)
        self.VNA = self.find_instrument(VNA_name)


        ########### TODO selectino between amp/phase and I/Q

        self.add_parameter('bandwidth',
                        set_cmd=None,
                        initial_value=1e3,
                        docstring="")

        self.add_parameter('npts',
                            set_cmd=None,
                            initial_value=200,
                            docstring="")

        self.add_parameter('frequency',
                            set_cmd=None,
                            initial_value=1e6,
                            vals=Numbers(1e5, 3e9),
                            docstring="")
        
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

        # only gettable
        self.add_parameter('sweep_time',
                            get_cmd=self._get_sweep_time,
                            docstring="")

    ################### Get functions ###################
    def _get_sweep_time(self):
        return self.VNA.S21.sweep_time()

    ################### Other functions ###################

    def prepare_VNA(self):
        """
        Sets all relevant params of the VNA.
        """
        self.VNA.S21.sweep_type('CW_Point')
        self.VNA.S21.bandwidth(self.bandwidth())
        self.VNA.S21.npts(self.npts())
        self.VNA.S21.trigger('External')
        self.VNA.S21.cw_frequency(self.frequency())

    def prepare_MDAC(self):
        """
        Sets up the MDAC to do the acquisition.
        """
        MDAC_ch = self.MDAC.channels[self.MDAC_channel()-1]
        MDAC_ch.attach_trigger()


    def get_measurement_range(self):
        return np.linspace(self.V_start/self.MDAC_divider() - self.MDAC_Vpp()/2,
                           self.V_start/self.MDAC_divider() + self.MDAC_Vpp()/2,
                           self.npts())


    def prepare_for_acquisition(self):
        self.prepare_VNA()
        self.prepare_MDAC()

    def arm_for_acquisition(self):
        self.VNA.cont_meas_off()
        self.VNA.S21.sweep_count(1)

        # get the MDAC channel
        MDAC_ch = self.MDAC.channels[self.MDAC_channel()-1]
        self.V_start = MDAC_ch.voltage()

        # calculate the rate of the MDAC sweep
        self.ramp_rate = self.MDAC_Vpp()/self.sweep_time()

        MDAC_ch.awg_sawtooth(1/self.sweep_time(), self.MDAC_Vpp()*self.MDAC_divider(), offset=self.V_start)
        self.MDAC.run()

        # self.MDAC.stop()

    def do_acquisition(self):
        """
        Executes a MIDAS capture method
        and returns an ndarrray with the data.
        """
        
        # self.MDAC.run()
        # time.sleep(0.15)
        time.sleep(0.05)
        self.VNA.restart_sweep()
        # time.sleep(self.sweep_time()+0.2)
        time.sleep(self.sweep_time()+0.5)

        data_str = self.VNA.S21.ask(f"CALC1:DATA? SDAT")
        data = np.array(data_str.rstrip().split(",")).astype("float64")
        i = data[0::2]
        q = data[1::2]

        # self.MDAC.stop()
        

        return i+1j*q

    def finalize(self):
        MDAC_ch = self.MDAC.channels[self.MDAC_channel()-1]
        MDAC_ch.ramp(self.V_start, ramp_rate=self.ramp_rate*5)
        # MDAC_ch.block()
        MDAC_ch.voltage(self.V_start)
        self.VNA.cont_meas_on()

    def arm_acquire_reshape(self):
        self.arm_for_acquisition()
        data = self.do_acquisition()
        return data
