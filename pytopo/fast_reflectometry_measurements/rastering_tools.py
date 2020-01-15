import broadbean as bb
ramp = bb.PulseAtoms.ramp

from qcodes.utils.validators import Ints, Numbers, Lists, Dict
from qcodes.instrument.base import Instrument

import numpy as np

import time

"""
Known issues:
1. capture_2d_trace was not intended to be used with single_point mode. It kind-of
    works but with a number of bugs. In some situations it may still be most efficient
    way of measuring, even if it fails sometimes. 
    e.g. capture_2d_trace moves returns the num_sweeps_2d-1 first traces from
    the current acquisition and a last trace from the frevious acquisition.
    Consequently MidasMdacAwg1DFastRasterer now uses repeated capture_1d_trace
    and requires midas_buffer_flushing_time > 10 ms
    Meanwhile MidasMdacAwg1DRasterer often show artifacts.
    Firmware version: midas_release_v1_03_085.hex
2. Related to previous (probably). Max samples per pixel for 2D raster
    is 128. I think it is because of some data offset by 128 points
    which you start seeing when numper of triggers per ramp exceeds 128.
Search for WORKAROUND for places when the tweaks were made to work around
the issues

Other comments:
    1. For simplicity the code allows the resolution and averging to
        set to values 2^N.
"""

class MidasMdacAwgParentRasterer(Instrument):
    """
    Parent class to the 1DSlow, 1DFast and 2D rasterers
    """

    def __init__(self, name, MIDAS_name, MDAC_name, AWG_name, **kwargs):
        """
        Create a MidasMdacAwgRasterer instance

        Args:
            name (str): rasterer instrument name
            MIDAS_name (str): name of the Midas to be used
            MDAC_name (str): name of the MDAC to be used
            AWG_name (str): name of the Tektronix 5014 to be used
            **kwargs: other kwargs passed to Instrument init

        Returns:
            MidasMdacAwgRasterer
        """

        super().__init__(name, **kwargs)

        self.SAMPLE_TIME = (1/1.8e9)*512 # 284.44 ns
        self.POINTS_PER_BUFFER = 2048

        self.MIDAS = self.find_instrument(MIDAS_name)
        self.MDAC = self.find_instrument(MDAC_name)
        self.AWG = self.find_instrument(AWG_name)

        self.add_parameter('AWG_channel',
                            set_cmd=None,
                            initial_value=1,
                            vals=Ints(min_value=1,max_value=4),
                            docstring="Channel of AWG used to apply"
                            " a sawtooth")

        self.add_parameter('AWG_trigger_channel',
                            set_cmd=None,
                            initial_value=1,
                            vals=Ints(min_value=1,max_value=4),
                            docstring="Channel of AWG used to apply"
                            " generate a trigger for Midas.")

        self.add_parameter('MIDAS_channel_specs',
                            set_cmd=None,
                            initial_value={1:'IQ'},
                            docstring="Dictionary specyfying quantities to"
                            " measure. Keys are the cjannel numbers (int)."
                            " Valuses are strings, up to 4 letters from"
                            " the set I, Q, A, P which stand for"
                            " (I, Q, Amplitude or Phase).")

        self.add_parameter('samples_per_pixel',
                        set_cmd=None,
                        initial_value=32,
                        vals=Ints(1,8192),
                        docstring="Number of 284.44 ns-long samples to"
                        " be averaged to get a single data pixel."
                        " Must be a power of 2.")

        self.add_parameter('midas_retriggering_time',
                        set_cmd=None,
                        initial_value=100e-9,
                        vals=Numbers(1e-9, 1e-3),
                        docstring="Additional waiting time to let"
                        " the Midas ready to acquire next sample")

        self.add_parameter('midas_buffer_flushing_time',
                        set_cmd=None,
                        initial_value=2e-3,
                        vals=Numbers(10e-6, 100e-3),
                        docstring="Additional waiting time to let"
                        " the Midas flush the buffer"
                        " and get ready for more triggers")

        self.add_parameter('pre_wait',
                            set_cmd=None,
                            initial_value=1e-6,
                            vals=Numbers(min_value=0, max_value=0.1),
                            docstring="Duration of the 'wait' segment in the"
                            " applied sequence of sawtooths. It's purpose is to"
                            " ensure that MDAC sweep starts synchronously with"
                            " the Midas acquisition.")

        # only gettable
        self.add_parameter('MIDAS_channels',
                            get_cmd=self._get_MIDAS_channels,
                            docstring="List of Midas channels to return")

    ################### Get functions ###################
    def _get_MIDAS_channels(self):
        return list(self.MIDAS_channel_specs().keys())

    ################### Conversion functions ###################

    def samples_to_time(self, samples):
        return samples*self.SAMPLE_TIME

    def time_to_samples(self, tim, round_down=True):
        if round_down:
            return int(tim/self.SAMPLE_TIME)
        else:
            return tim/self.SAMPLE_TIME

    ################### Other functions ###################

    def prepare_AWG(self):
        """
        Orepares and uploades a needed sequence
        to Tektronix 5014.
        Should be implemented in a subclass.
        """
        raise NotImplementedError(
            'This method should be implemented in a subclass')

    def prepare_MIDAS(self):
        """
        Sets up the MIDAS to do the acquisition.
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
        MIDAS.captire_[...] just before the acquisition.
        Should be implemented in a subclass.
        """
        raise NotImplementedError(
            'This method should be implemented in a subclass')

    def fn_stop(self):
        """
        This function will be exectued by
        MIDAS.captire_[...] just after the acquisition.
        Should be implemented in a subclass.
        """
        raise NotImplementedError(
            'This method should be implemented in a subclass')

    def do_acquisition(self):
        """
        Executes a MIDAS capture method
        and returns an ndarray with the data.
        Should be implemented in a subclass.
        """
        raise NotImplementedError(
            'This method should be implemented in a subclass')

    def reshape(self):
        """
        Reshapes and performs required averaging
        of the data returned by do_acquisition()
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

    def AWG_channels_on(self):
        self.AWG.ch1_state(1)
        self.AWG.ch2_state(1)
        self.AWG.ch3_state(1)
        self.AWG.ch4_state(1)

    def prepare_for_acquisition(self):
        self.prepare_AWG()
        self.AWG_channels_on()
        self.prepare_MIDAS()
        self.prepare_MDAC()

    def arm_for_acquisition(self):
        self.AWG.stop()
        self.AWG.start()

    def arm_acquire_reshape(self):
        self.arm_for_acquisition()
        time.sleep(1e-3)
        data = self.do_acquisition()
        self.data_raw = data
        # return data
        data = self.reshape(data)
        # pick selected MIDAS channels
        self.data = []
        for ch, quadratures in self.MIDAS_channel_specs().items():
            d = data[ch-1]
            phase_offset = self.MIDAS.channels[ch-1].phase_offset()
            for q in quadratures:
                self.data.append(get_quadrature(d, q, phase_offset))
        return np.array(self.data)

##################################################################
######################## 1D MDAC rasterer ########################
##################################################################

class MidasMdacAwg1DSlowRasterer(MidasMdacAwgParentRasterer):
    def __init__(self, name, MIDAS_name, MDAC_name, AWG_name, **kwargs):
        """
    How to use:
        1. Configure Midas channels
        2. Create a rasterer object:
            >>> rSlow = rast.MidasMdacAwg1DSlowRasterer('rSlow',
                                midas.name, mdac.name, AWG.name)
        3. Set up the MDAC channel, voltage range, averaging
            and resolution:
            >>> rSlow.MDAC_channel(1)
            >>> rSlow.MDAC_Vpp(0.1)
            >>> rSlow.samples_per_pixel(512)
            >>> rSlow.pixels(128)
        4. Run routines to automatically configure AWG and Midas:
            >>> rSlow.prepare_AWG()
            >>> rSlow.AWG_channels_on()
            >>> rSlow.prepare_MIDAS()
        5. Measure:
            >>> data = rSlow.arm_acquire_reshape()
            After acquisition the MDAC channel voltage is set to
            the value from the beginning of the measurement.
        6. "data" is an (8 x pixels) array with the obtained data
            At this time no scaling of the sweeped axis is provided.
            The MDAC sweeps the voltage from Vmdac-MDAC_Vpp/2
            to Vmdac+MDAC_Vpp/2, where Vmdac is the channel setting
            at the moment arm_acquire_reshape method is executed.
        7. Investigate the data to verify if the MDAC sweep
            is synchronized with the AWG. If needed, adjust
            pre_wait parameter and repeat points 4-6
        8. Executing 4 between measurements is only required
            if you changed any of the following parameters:
            - AWG_channel
            - samples_per_pixel
            - midas_retriggering_time
            - pre_wait
            - pixels
            - AWG parameters
            Executing 4 is NOT required if you change:
            - MDAC_channel
            - MDAC_Vpp
            - MDAC_divider
            - MIDAS_channels
            - Midas channel parameters
    """

        super().__init__(name,
                MIDAS_name, MDAC_name, AWG_name,
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

        self.add_parameter('pixels',
                            set_cmd=None,
                            initial_value=64,
                            vals=Ints(1,2048),
                            docstring="Number of pixels along the axis"
                            " controlled by the MDAC sweep."
                            " Must be a power of 2.")

        # only gettable
        self.add_parameter('time_per_pixel',
                            get_cmd=self._get_time_per_pixel)

        self.add_parameter('time_per_point',
                            get_cmd=self._get_time_per_point)

        self.add_parameter('saples_per_point',
                            get_cmd=self._saples_per_point)


    ################### Get functions ###################

    def _get_time_per_pixel(self):
        # calculate how much time does it take to measure
        # a single pixel
        tM = self.samples_to_time(self.samples_per_pixel())
        tM += self.midas_retriggering_time()*self.POINTS_PER_BUFFER/self.pixels()
        return tM

    def _get_time_per_point(self):
        # calculate how much time does it take to measure
        # a single point
        tM = self.time_per_pixel()
        tM /= self.POINTS_PER_BUFFER/self.pixels()
        return tM

    def _saples_per_point(self):
        return int(self.samples_per_pixel()/self.POINTS_PER_BUFFER*self.pixels())

    ################### Other functions ###################

    def prepare_AWG(self):
        # use 10 MS/s AWG sampling rate
        AWG_sampling_rate = 10e6

        # generate a sequence to upload to AWG
        # reuse single_sawtooth_many_triggers
        self.sequence = single_sawtooth_many_triggers(self.AWG,
                            AWG_sampling_rate,
                            self.AWG_channel(),
                            self.time_per_point(),
                            1,
                            self.midas_buffer_flushing_time(),
                            0,
                            trigger_ch=self.AWG_trigger_channel(),
                            pre_wait=self.pre_wait())

        # upload
        package = self.sequence.outputForAWGFile()
        AWGfile = self.AWG.make_awg_file(*package[:])

        self.AWG.send_awg_file('raster',AWGfile)
        self.AWG.load_awg_file('raster')

        self.AWG.clock_freq(AWG_sampling_rate)

        return self.sequence

    def prepare_MIDAS(self):
        self.MIDAS.sw_mode('single_point')
        self.MIDAS.single_point_num_avgs(self.saples_per_point())
        self.MIDAS.calibrate_latency()
        self.MIDAS.trigger_delay(self.MIDAS.trigger_delay())

    def prepare_MDAC(self):
        MDAC_ch = self.MDAC.channels[self.MDAC_channel()-1]
        MDAC_ch.attach_trigger()

    def fn_start(self):
        self.MDAC.run()

    def fn_stop(self):
        MDAC_ch = self.MDAC.channels[self.MDAC_channel()-1]

        MDAC_ch.attach_trigger()
        MDAC_ch.ramp(self.V_start, ramp_rate=self.ramp_rate*5)
        MDAC_ch.block()
        MDAC_ch.voltage(self.V_start)
        self.AWG.stop()

    def do_acquisition(self):
        data = self.MIDAS.capture_1d_trace(
                            fn_start=self.fn_start,
                            fn_stop=self.fn_stop)
        return data

    def reshape(self, data):
        res = np.reshape(data, (8,self.pixels(),-1))
        avg = np.average(res, axis=-1)
        return avg

    def arm_for_acquisition(self):
        self.AWG.stop()
        
        # get the MDAC channel
        MDAC_ch = self.MDAC.channels[self.MDAC_channel()-1]
        self.V_start = MDAC_ch.voltage()

        # calculate measurement time:
        sweep_time = self.pixels()*self.time_per_pixel()

        # calculate the rate of the MDAC sweep
        self.ramp_rate = self.MDAC_Vpp()/sweep_time

        # 0.99/sweep_time frequency is minimally smaller to avoid
        # problems with last pixel in case a few triggers are missed
        MDAC_ch.awg_sawtooth(0.99/sweep_time, self.MDAC_Vpp()*self.MDAC_divider(), offset=self.V_start)
        self.MDAC.stop()
        self.MDAC.sync()

        self.AWG.start()
        time.sleep(0.05)


    def get_measurement_range(self):
        MDAC_ch = self.MDAC.channels[self.MDAC_channel()-1]
        self.V_start = MDAC_ch.voltage()
        return np.linspace(self.V_start/self.MDAC_divider() - self.MDAC_Vpp()/2,
                           self.V_start/self.MDAC_divider() + self.MDAC_Vpp()/2,
                           self.pixels())

class MidasMdacAwg1DSlowMultigateRasterer(MidasMdacAwg1DSlowRasterer):
    def __init__(self, name, MIDAS_name, MDAC_name, AWG_name, **kwargs):
        super().__init__(name,
                MIDAS_name, MDAC_name, AWG_name,
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

    ################### Other functions ###################

    def prepare_MDAC(self):
        # use channel with the smallest number to trigger on
        ch = min(self.MDAC_channel_dict().keys())
        MDAC_ch = self.MDAC.channels[ch-1]
        MDAC_ch.attach_trigger()

    def fn_stop(self):
        for ch, V_start in self.V_start.items():
            MDAC_ch = self.MDAC.channels[ch-1]

            MDAC_ch.attach_trigger()
            MDAC_ch.ramp(V_start)
            MDAC_ch.block()
            MDAC_ch.voltage(V_start)
            time.sleep(0.005)
        self.AWG.stop()

    def arm_for_acquisition(self):
        self.AWG.stop()

        # calculate measurement time:
        sweep_time = self.pixels()*self.time_per_pixel()

        # set waveform on all channels
        self.V_start = {}
        for ch, Vpp in self.MDAC_channel_dict().items():
            # get the MDAC channel
            MDAC_ch = self.MDAC.channels[ch-1]
            V_start = MDAC_ch.voltage()

            # save initial values
            self.V_start[ch] = V_start

            # 0.99/sweep_time frequency is minimally smaller to avoid
            # problems with last pixel in case a few triggers are missed
            if Vpp>0:
                MDAC_ch.awg_sawtooth(0.99/sweep_time, Vpp, offset=V_start)
            else:
                MDAC_ch.awg_sawtooth_falling(0.99/sweep_time, -Vpp, offset=V_start)
        

        self.MDAC.stop()
        self.MDAC.sync()

        self.AWG.start()
        time.sleep(0.05)

    def get_measurement_range(self):
        ch = min(self.MDAC_channel_dict().keys())
        Vpp = self.MDAC_channel_dict()[ch]
        scaling = self.range_scaling()
        offset = self.range_offset()

        return np.linspace(-Vpp*scaling/2+offset,
                           Vpp*scaling/2+offset,
                           self.pixels())

#################################################################
######################## 1D AWG rasterer ########################
#################################################################

class MidasMdacAwg1DFastRasterer(MidasMdacAwgParentRasterer):
    """
    How to use:
        1. Configure Midas channels
        2. Create a rasterer object:
            >>> rFast = rast.MidasMdacAwg1DFastRasterer('rFast',
                                midas.name, mdac.name, AWG.name)
            MDAC name is required but not used anywhere.
        3. Set up the voltage range, averaging and resolution:
            >>> rFast.AWG_Vpp(0.1)
            >>> rFast.samples_per_pixel(512)
            >>> rFast.pixels(128)
            >>> rFast.midas_buffer_flushing_time(0.01)
                # long buffer flushing time needed at this point
        4. Run routines to automatically configure AWG and Midas:
            >>> rFast.prepare_AWG()
            >>> rFast.AWG_channels_on()
            >>> rFast.prepare_MIDAS()
        5. Measure:
            >>> data = rFast.arm_acquire_reshape()
        6. "data" is an (8 x pixels) array with the obtained data
            At this time no scaling of the sweeped axis is provided.
        7. Investigate the data to verify if Midas
            is synchronized with the AWG sawtooth. If needed, adjust
            pre_wait and trigger_delay parameters and repeat
            points 4-6
        8. Executing 4 between measurements is only required
            if you changed any of the following parameters:
            - AWG_channel
            - samples_per_pixel
            - midas_retriggering_time
            - pre_wait
            - pixels
            - samples_per_ramp
            - AWG_Vpp
            - AWG parameters
            - high_pass_cutoff
            Executing 4 is NOT required if you change:
            - MIDAS_channels
            - Midas channel parameters
    """

    def __init__(self, name, MIDAS_name, MDAC_name, AWG_name, **kwargs):
        """
        Create a MidasMdacAwgRasterer instance

        Args:
            name (str): rasterer instrument name
            MIDAS_name (str): name of the Midas to be used
            MDAC_name (str): name of the MDAC to be used
            AWG_name (str): name of the Tektronix 5014 to be used
            **kwargs: other kwargs passed to Instrument init

        Returns:
            MidasMdacAwgRasterer
        """

        super().__init__(name,
                MIDAS_name, MDAC_name, AWG_name,
                **kwargs)

        self.add_parameter('pixels',
                            set_cmd=None,
                            initial_value=64,
                            vals=Ints(1,2048),
                            docstring="Number of pixels along the axis"
                            " controlled by the MDAC sweep."
                            " Must be a power of 2.")

        self.add_parameter('samples_per_ramp',
                        set_cmd=None,
                        initial_value=1024,
                        vals=Ints(128,4096),
                        docstring="Number of samples taken per"
                        " single AWG ramp. Should be the largest"
                        " number possible that does not lead to"
                        " the distortions."
                        " Must be a power of 2.")

        self.add_parameter('AWG_Vpp',
                            set_cmd=None,
                            initial_value=0.1,
                            vals=Numbers(min_value=0),
                            docstring="Vpp of the sawtooth applied with AWG,"
                            " Not adjusted for the attenuation of the"
                            " high-frequency lines. DC offset of the voltage"
                            " needs to be set separately with whatever"
                            " instrument you use for that.")

        self.add_parameter('high_pass_cutoff',
                            set_cmd=None,
                            initial_value=0,
                            vals=Numbers(min_value=0,max_value=1e9),
                            docstring="Cut off frequency of the high pass filter"
                            " which is to be compensated by predistorting"
                            " the AWG waveform.")

        # only gettable
        self.add_parameter('samples_total',
                            get_cmd=self._get_samples_total)

        self.add_parameter('points_total',
                            get_cmd=self._get_points_total)

        self.add_parameter('ramp_time_fast',
                            get_cmd=self._get_ramp_time_fast)

        self.add_parameter('samples_per_point',
                            get_cmd=self._get_samples_per_point)

        self.add_parameter('ramps_per_acquisition',
                            get_cmd=self._get_ramps_per_acquisition)

        self.add_parameter('buffers_per_acquisition',
                            get_cmd=self._get_buffers_per_acquisition)

    ################### Get functions ###################

    def _get_samples_total(self):
        return int(self.samples_per_pixel()*self.pixels())

    def _get_points_total(self):
        return int(self.ramps_per_acquisition()*self.pixels())

    def _get_ramp_time_fast(self):
        # calculate the AWG sawtooth period corresponding to
        # the number of samples per single ramp
        # plus time for the Midas to retrigger
        # in principle time for th emidas to retrigges can be set to 0
        tM = self.samples_to_time(self.samples_per_ramp())
        tW = self.pixels()*self.midas_retriggering_time()
        return tM+tW

    def _get_samples_per_point(self):
        return int(self.samples_per_ramp()/self.pixels())

    def _get_ramps_per_acquisition(self):
        samples_per_acquisition =  self.samples_per_pixel()*self.pixels()
        ramps_per_acquisition = samples_per_acquisition/self.samples_per_ramp()
        return int(max(ramps_per_acquisition,1))

    def _get_buffers_per_acquisition(self):
        sample_limited_minimum = self.samples_total()/self.samples_per_point()/self.POINTS_PER_BUFFER
        resolution_limited_minimum = self.pixels()/self.POINTS_PER_BUFFER
        return int(max(sample_limited_minimum, resolution_limited_minimum,1))

    ################### Other functions ###################

    def prepare_AWG(self):
        # use low AWG sampling rate, but not smaller than
        # minimum 10 MS/s
        AWG_sampling_rate = max(200/self.ramp_time_fast(), 10e6)

        # generate a sequence to upload to AWG
        self.sequence = single_sawtooth_many_triggers(self.AWG,
                            AWG_sampling_rate,
                            self.AWG_channel(),
                            self.ramp_time_fast(),
                            self.pixels(),
                            self.midas_buffer_flushing_time(),
                            self.AWG_Vpp(),
                            high_pass_cutoff=self.high_pass_cutoff(),
                            trigger_ch=self.AWG_trigger_channel(),
                            pre_wait=self.pre_wait())

        # upload
        package = self.sequence.outputForAWGFile()
        AWGfile = self.AWG.make_awg_file(*package[:])

        self.AWG.send_awg_file('raster',AWGfile)
        self.AWG.load_awg_file('raster')

        self.AWG.clock_freq(AWG_sampling_rate)

        return self.sequence

    def prepare_MIDAS(self):
        self.MIDAS.sw_mode('single_point')
        self.MIDAS.single_point_num_avgs(self.samples_per_point())
        self.MIDAS.num_sweeps_2d(self.buffers_per_acquisition())
        self.MIDAS.calibrate_latency()
        self.MIDAS.trigger_delay(self.MIDAS.trigger_delay())

    def prepare_MDAC(self):
        MDAC_ch = self.MDAC.channels[self.MDAC_channel()-1]
        MDAC_ch.attach_trigger()

    def fn_start(self):
        # trigger AWG
        self.AWG.force_trigger()

    def fn_stop(self):
        self.AWG.stop()

    def do_acquisition(self):
        if self.buffers_per_acquisition() == 1:
            data = [self.MIDAS.capture_1d_trace(
                                    fn_start=self.fn_start,
                                    fn_stop=self.fn_stop)]
        else:
            data = [self.MIDAS.capture_1d_trace(
                                    fn_start=self.fn_start)]
            for _ in range(self.buffers_per_acquisition()-2):
                data.append(self.MIDAS.capture_1d_trace())
            data.append(self.MIDAS.capture_1d_trace(
                                    fn_stop=self.fn_stop))
        return np.array(data)

    def reshape(self, data):
        reshaped = []
        for i in range(8):
            d = data[:,i,:]
            if self.points_total()<2048:
                d = d[0,:self.points_total()]
            res = np.reshape(d, (self.ramps_per_acquisition(),
                                self.pixels()))
            avg = np.average(res, axis=0)
            reshaped.append(avg)

        return np.array(reshaped)

    def get_measurement_range(self):
        return np.linspace(-self.AWG_Vpp()/2,
                           self.AWG_Vpp()/2,
                           self.pixels())

########## Testing 1D fast rasterer with capture_2d_trace ##########

class MidasMdacAwg1DFastRasterer_test(MidasMdacAwg1DFastRasterer):

    def __init__(self, name, MIDAS_name, MDAC_name, AWG_name, **kwargs):

        super().__init__(name,
                MIDAS_name, MDAC_name, AWG_name,
                **kwargs)

    def prepare_MIDAS(self):
        self.MIDAS.sw_mode('single_point')
        self.MIDAS.single_point_num_avgs(self.samples_per_point())
        # adding +1 [WORKAROUND]
        self.MIDAS.num_sweeps_2d(self.buffers_per_acquisition() + 1)
        self.MIDAS.calibrate_latency()
        self.MIDAS.trigger_delay(self.MIDAS.trigger_delay())

    def do_acquisition(self):
        data = self.MIDAS.capture_2d_trace(
                            fn_start=self.fn_start,
                            fn_stop=self.fn_stop)
        # removing first buffer [WORKAROUND]
        return np.array(data[1:])

#################################################################
########################## 2D rasterer ##########################
#################################################################

class MidasMdacAwg2DRasterer(MidasMdacAwgParentRasterer):
    """
    The class responsible for dual gate rastering with
    MIDAS, MDAC and Tektronix 5014.

    Relevant parameters:
    - AWG_channel
    - MDAC_channel
    - AWG_Vpp (amplitude of the sawtooth applied by AWG)
    - MDAC_Vpp (amplitude of the MDAC sweep)
    - samples_per_pixel (indicates averaging per point;
        1 sample = 284.44 ns; only values 2^N will yield
        successful measurement)
    - pixels_per_line (resolution along the axis
        controlled by AWG; only values 2^N will yield
        successful measurement)
    - lines_per_acquisition (resolution along the axis
        controlled by MDAC; only values 2^N will yield
        successful measurement)
    - samples_per_ramp (specifies the length of the sawtooth
        applied by AWG; 1 sample = 284.44 ns; only values 2^N will
        yield successful measurement; should set to the largest
        value, for which the distortions are not observed)
    - midas_buffer_flushing_time (additional waiting time between
        some of the sawtooth teeth, for the Midas to flush the
        FIFO buffer; maual specifies this needs to be no longer
        than 0.6 ms, but I found out that this is often not
        sufficient and recommend using 1 ms to reduce
        how often triggers are missed)
    - high_pass_cutoff (specifies the cutoff frequency of
        the high pass filter on the high frequency (AWG) line)

    The idea is that the user only needs to specify an averaging
    time per pixel, resolution and sawtooth period (constrained by
    the bandwidth of the setup). The order in which the data
    is acquired is taken care of automatically.
    
    Naming convention:
    - sample: 284.44 ns long sample measured by Midas
    - point: a number of samples averaged together during a single ramp
    - ramp: a single tooth of an AWG sawtooth
    - pixel: a single data point in the final dataset. Depending on
        demanded samples_per_pixel several points (from consequtive
        ramps) may be averaged together to get a single pixel
    - line: a collection of pixels forming a single line in
        the final dataset. Depending on demanded samples_per_pixel
        data from one or more ramps may be averaged together to
        yield a single line
    - buffer: a collection of 2048 points. This number is strictly
        specified by the Midas user manual
    - acquisition: a collection of buffers with all of the acquired data
        
    How to use:
        1. Configure Midas channels
        2. Create a rasterer object:
            >>> r2D = rast.MidasMdacAwg1DFastRasterer('r2D',
                                midas.name, mdac.name, AWG.name)
        3. Set up the MDAC channel, voltage ranges, averaging
            and resolution:
            >>> r2D.MDAC_channel(1)
            >>> r2D.MDAC_Vpp(0.8)
            >>> r2D.AWG_Vpp(0.1)
            >>> r2D.samples_per_pixel(64)
            >>> r2D.pixels_per_line(128)
            >>> r2D.lines_per_acquisition(128)
        4. Run routines to automatically configure AWG and Midas:
            >>> r2D.prepare_AWG()
            >>> r2D.AWG_channels_on()
            >>> r2D.prepare_MIDAS()
        5. Measure:
            >>> data = r2D.arm_acquire_reshape()
        6. "data" is an (8 x pixels x lines) array with
            the obtained data. At this time no scaling
            of the sweeped axis is provided.
            The MDAC sweeps the voltage from Vmdac-MDAC_Vpp/2
            to Vmdac+MDAC_Vpp/2, where Vmdac is the channel setting
            at the moment arm_acquire_reshape method is executed.
        7. Investigate the data to verify if Midas
            is synchronized with the AWG sawtooth and if
            AWG starts in outputting sawtooth in sync with
            MDAC starting the sweep. If needed, adjust
            pre_wait and trigger_delay parameters and repeat
            points 4-6
        8. Executing 4 between measurements is only required
            if you changed any of the following parameters:
            - AWG_channel
            - samples_per_pixel
            - midas_retriggering_time
            - pre_wait
            - pixels_per_line
            - lines_per_acquisition
            - samples_per_ramp
            - AWG_Vpp
            - AWG parameters
            - high_pass_cutoff
            Executing 4 is NOT required if you change:
            - MDAC_channel
            - MDAC_Vpp
            - MIDAS_channels
            - Midas channel parameters
    """

    def __init__(self, name, MIDAS_name, MDAC_name, AWG_name, **kwargs):
        """
        Create a MidasMdacAwgRasterer instance

        Args:
            name (str): rasterer instrument name
            MIDAS_name (str): name of the Midas to be used
            MDAC_name (str): name of the MDAC to be used
            AWG_name (str): name of the Tektronix 5014 to be used
            **kwargs: other kwargs passed to Instrument init

        Returns:
            MidasMdacAwgRasterer
        """

        super().__init__(name,
                MIDAS_name, MDAC_name, AWG_name,
                **kwargs)

        self.add_parameter('MDAC_channel',
                            set_cmd=None,
                            initial_value=None,
                            vals=Ints(min_value=1,max_value=64),
                            docstring="MDAC channels to be sweeped.")

        self.add_parameter('MDAC_channel_for_AWG',
                            set_cmd=None,
                            initial_value=None,
                            vals=Ints(min_value=1,max_value=64),
                            docstring="MDAC channel corresponding to the gate"
                            " sweeped by AWG. Needed for axis scaling."
                            )

        self.add_parameter('pixels_per_line',
                        set_cmd=None,
                        initial_value=64,
                        vals=Ints(1,8192),
                        docstring="Number of pixels along the axis"
                        " specified by the fast AWG ramp."
                        " Must be a power of 2.")

        self.add_parameter('lines_per_acquisition',
                        set_cmd=None,
                        initial_value=64,
                        vals=Ints(1,4096),
                        docstring="Number of lines in"
                        " the final 2D diagram."
                        " Must be a power of 2.")

        self.add_parameter('samples_per_ramp',
                        set_cmd=None,
                        initial_value=1024,
                        vals=Ints(128,4096),
                        docstring="Number of samples taken per"
                        " single AWG ramp. Should be the largest"
                        " number possible that does not lead to"
                        " the distortions."
                        " Must be a power of 2.")

        self.add_parameter('AWG_Vpp',
                            set_cmd=None,
                            initial_value=0.1,
                            vals=Numbers(min_value=0),
                            docstring="Vpp of the sawtooth applied with AWG,"
                            " Not adjusted for the attenuation of the"
                            " high-frequency lines. DC offset of the voltage"
                            " needs to be set separately with whatever"
                            " instrument you use for that.")

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

        self.add_parameter('AWG_divider',
                            set_cmd=None,
                            initial_value=1,
                            vals=Numbers(min_value=1),
                            docstring="Voltage divider to take into account")

        self.add_parameter('high_pass_cutoff',
                            set_cmd=None,
                            initial_value=0,
                            vals=Numbers(min_value=0,max_value=1e9),
                            docstring="Cut off frequency of the high pass filter"
                            " which is to be compensated by predistorting"
                            " the AWG waveform.")

        # only gettable
        self.add_parameter('samples_total',
                            get_cmd=self._get_samples_total)

        self.add_parameter('points_total',
                            get_cmd=self._get_points_total)

        self.add_parameter('ramp_time_fast',
                            get_cmd=self._get_ramp_time_fast)

        self.add_parameter('ramps_per_buffer',
                            get_cmd=self._get_ramps_per_buffer)

        self.add_parameter('samples_per_point',
                            get_cmd=self._get_samples_per_point)

        self.add_parameter('ramps_per_line',
                            get_cmd=self._get_ramps_per_line)

        self.add_parameter('buffers_per_acquisition',
                            get_cmd=self._get_buffers_per_acquisition)                            

    ################### Get functions ###################

    def _get_samples_total(self):
        return int(self.samples_per_pixel()*self.pixels_per_line()*self.lines_per_acquisition())

    def _get_points_total(self):
        return int(self.lines_per_acquisition()*self.ramps_per_line()*self.pixels_per_line())

    def _get_ramp_time_fast(self):
        # calculate the AWG sawtooth period corresponding to
        # the number of samples per single ramp
        # plus time for the Midas to retrigger
        # in principle time for th emidas to retrigges can be set to 0
        tM = self.samples_to_time(self.samples_per_ramp())
        tW = self.pixels_per_line()*self.midas_retriggering_time()
        return tM+tW

    def _get_ramps_per_buffer(self):
        return int(self.POINTS_PER_BUFFER/self.pixels_per_line())

    def _get_samples_per_point(self):
        return int(self.samples_per_ramp()/self.pixels_per_line())

    def _get_ramps_per_line(self):
        samples_per_line =  self.samples_per_pixel()*self.pixels_per_line()
        ramps_per_line = samples_per_line/self.samples_per_ramp()
        return int(max(ramps_per_line,1))

    def _get_buffers_per_acquisition(self):
        sample_limited_minimum = self.samples_total()/self.samples_per_point()/self.POINTS_PER_BUFFER
        resolution_limited_minimum = self.pixels_per_line()*self.lines_per_acquisition()/self.POINTS_PER_BUFFER
        return int(max(sample_limited_minimum, resolution_limited_minimum,1))


    ################### Other functions ###################

    def prepare_AWG(self):
        # use low AWG sampling rate, but not smaller than
        # minimum 10 MS/s
        AWG_sampling_rate = max(200/self.ramp_time_fast(), 10e6)

        # generate a sequence to upload to AWG
        self.sequence = single_sawtooth_many_triggers(self.AWG,
                            AWG_sampling_rate,
                            self.AWG_channel(),
                            self.ramp_time_fast(),
                            self.pixels_per_line(),
                            self.midas_buffer_flushing_time(),
                            self.AWG_Vpp()*self.AWG_divider(),
                            high_pass_cutoff=self.high_pass_cutoff(),
                            trigger_ch=self.AWG_trigger_channel(),
                            pre_wait=self.pre_wait())

        # upload
        package = self.sequence.outputForAWGFile()
        AWGfile = self.AWG.make_awg_file(*package[:])

        self.AWG.send_awg_file('raster',AWGfile)
        self.AWG.load_awg_file('raster')

        self.AWG.clock_freq(AWG_sampling_rate)

        return self.sequence

    def prepare_MIDAS(self):
        self.MIDAS.sw_mode('single_point')
        self.MIDAS.single_point_num_avgs(self.samples_per_point())

        # +1 as a workaround for the Midas bug [WORKAROUND]
        self.MIDAS.num_sweeps_2d(self.buffers_per_acquisition() + 1)
        self.MIDAS.calibrate_latency()
        self.MIDAS.trigger_delay(self.MIDAS.trigger_delay())

    def prepare_MDAC(self):
        MDAC_ch = self.MDAC.channels[self.MDAC_channel()-1]
        MDAC_ch.attach_trigger()

    def fn_start(self):
        self.MDAC.run()

    def fn_stop(self):
        MDAC_ch = self.MDAC.channels[self.MDAC_channel()-1]

        MDAC_ch.ramp(self.V_start, ramp_rate=self.ramp_rate*5)
        MDAC_ch.block()
        MDAC_ch.voltage(self.V_start)
        self.AWG.stop()

    def do_acquisition(self):
        data = self.MIDAS.capture_2d_trace(
                            fn_start=self.fn_start,
                            fn_stop=self.fn_stop)

        # removing first buffer [WORKAROUND]
        return np.array(data[1:])

    def reshape(self, data):
        reshaped = []
        for i in range(8):
            d = data[:,i,:]
            if self.points_total()<2048:
                d = d[0,:self.points_total()]
            res = np.reshape(d, (self.lines_per_acquisition(),
                                self.ramps_per_line(),
                                self.pixels_per_line()))
            avg = np.average(res, axis=1)
            reshaped.append(avg)

        return np.array(reshaped)

    def arm_for_acquisition(self):
        self.AWG.stop()

        # get the MDAC channel
        MDAC_ch = self.MDAC.channels[self.MDAC_channel()-1]
        self.V_start = MDAC_ch.voltage()

        # calculate measurement time:
        ramps = self.ramps_per_buffer()
        buffers = self.buffers_per_acquisition()
        ramp_time = self.ramp_time_fast()
        flushing_time = self.midas_buffer_flushing_time()

        sweep_time = ramps*buffers*ramp_time
        sweep_time += (buffers-1)*flushing_time

        # calculate the rate of the MDAC sweep
        self.ramp_rate = self.MDAC_Vpp()/sweep_time

        # 0.99/sweep_time frequency is minimally smaller to avoid
        # problems with last pixel in case a few triggers are missed
        MDAC_ch.awg_sawtooth(0.99/sweep_time, self.MDAC_Vpp()*self.MDAC_divider(), offset=self.V_start)
        self.MDAC.stop()
        self.MDAC.sync()

        self.AWG.start()
        time.sleep(0.1)

    def get_measurement_range(self):
        MDAC_ch = self.MDAC.channels[self.MDAC_channel()-1]
        self.V_start = MDAC_ch.voltage()
        MDAC_range = np.linspace(self.V_start - self.MDAC_Vpp()/2,
                           self.V_start + self.MDAC_Vpp()/2,
                           self.lines_per_acquisition())/self.MDAC_divider()

        AWG_range =  np.linspace(-self.AWG_Vpp()/2,
                                 self.AWG_Vpp()/2,
                                 self.pixels_per_line())

        if self.MDAC_channel_for_AWG() is not None:
            MDAC_ch_2 = self.MDAC.channels[self.MDAC_channel_for_AWG()-1]
            AWG_range += MDAC_ch_2.voltage()


        return AWG_range, MDAC_range

######################################################################
########################## helper functions ##########################
######################################################################

def single_sawtooth_many_triggers(AWG,
                    sampling_rate,
                    ch,
                    rampTime,
                    triggersPerRamp,
                    flushingTime,
                    Vpp,
                    high_pass_cutoff=None,
                    trigger_ch=1,
                    triggersPerFlush=2048,
                    pre_wait=None):
    
    # make a wait element
    # by default it has 2 clock cycle length
    # (the least a segmant can have)
    # to ensure that sequence starts and ends
    # with 0V
    # otherwise it has length specified by pre_wait
    if pre_wait is None:
        pre_wait = 2/sampling_rate

    wait_blueprint = bb.BluePrint()
    wait_blueprint.setSR(sampling_rate)
    wait_blueprint.insertSegment(-1, ramp, (0, 0),
                                    name='wait',
                                    dur=pre_wait)
    wait_element = bb.Element()
    if ch != trigger_ch:
        wait_element.addBluePrint(trigger_ch, wait_blueprint)
    wait_element.addBluePrint(ch, wait_blueprint)

    wait_element.validateDurations()

    # make a single-segment sawtooth element
    sawtooth_blueprint = bb.BluePrint()
    sawtooth_blueprint.setSR(sampling_rate)
    sawtooth_blueprint.insertSegment(-1, ramp, (-Vpp/2, Vpp/2),
                                name='ramp',
                                dur=rampTime)

    if ch == trigger_ch:
        pointTime = rampTime/triggersPerRamp
        sawtooth_blueprint.marker1 = [(pointTime*i, 200e-9) for i in range(triggersPerRamp)]
        sawtooth_blueprint.marker2 = [(pointTime*i, 200e-9) for i in range(triggersPerRamp)]
    else:
        sawtooth_trigger_blueprint = bb.BluePrint()
        sawtooth_trigger_blueprint.setSR(sampling_rate)
        sawtooth_trigger_blueprint.insertSegment(-1, ramp, (0, 0),
                                    name='ramp_trig',
                                    dur=rampTime)
        pointTime = rampTime/triggersPerRamp
        sawtooth_trigger_blueprint.marker1 = [(pointTime*i, 200e-9) for i in range(triggersPerRamp)]
        sawtooth_trigger_blueprint.marker2 = [(pointTime*i, 200e-9) for i in range(triggersPerRamp)]

    sawtooth_element = bb.Element()
    if ch != trigger_ch:
        sawtooth_element.addBluePrint(trigger_ch, sawtooth_trigger_blueprint)
    sawtooth_element.addBluePrint(ch, sawtooth_blueprint)

    sawtooth_element.validateDurations()

    # make an element what waits for buffer flushing
    flush_blueprint = bb.BluePrint()
    flush_blueprint.setSR(sampling_rate)
    flush_blueprint.insertSegment(-1, ramp, (0, 0),
                                    name='wait',
                                    dur=flushingTime)
    flush_element = bb.Element()
    if ch != trigger_ch:
        flush_element.addBluePrint(trigger_ch, flush_blueprint)
    flush_element.addBluePrint(ch, flush_blueprint)

    flush_element.validateDurations()



    # make a sequence
    # wait - sawtooth (repeat) - flush - go to sawtooth
    elem_num = 1
    sequence = bb.Sequence()

    sequence.addElement(elem_num, wait_element)
    sequence.setSequencingTriggerWait(elem_num, 1)
    sequence.setSequencingNumberOfRepetitions(elem_num,1)
    sequence.setSequencingGoto(elem_num,0)
    elem_num += 1

    sequence.addElement(elem_num, sawtooth_element)
    sequence.setSequencingTriggerWait(elem_num, 0)
    rampsPerFlush = triggersPerFlush/triggersPerRamp
    sequence.setSequencingNumberOfRepetitions(elem_num,rampsPerFlush)
    sequence.setSequencingGoto(elem_num,0)
    elem_num += 1

    sequence.addElement(elem_num, flush_element)
    sequence.setSequencingTriggerWait(elem_num, 0)
    sequence.setSequencingNumberOfRepetitions(elem_num,1)
    sequence.setSequencingGoto(elem_num,2)
    elem_num += 1

    ch_amp = AWG['ch'+str(ch)+'_amp']()
    sequence.setChannelAmplitude(ch, ch_amp)
    sequence.setChannelOffset(ch, 0)

    if ch != trigger_ch:
        ch_amp = AWG['ch'+str(trigger_ch)+'_amp']()
        sequence.setChannelAmplitude(trigger_ch, ch_amp)
        sequence.setChannelOffset(trigger_ch, 0)

    sequence.setSR(sampling_rate)

    if high_pass_cutoff is not None:
        if high_pass_cutoff>0:
            sequence.setChannelFilterCompensation(ch, 'HP',
                            order=1, f_cut=high_pass_cutoff)

    return sequence


def get_quadrature(d, q, phase_offset=0):
    rot_vec = complex(np.cos(phase_offset), -np.sin(phase_offset))
    if q=='A':
        return np.abs(d)
    elif q=='P':
        phases = np.angle(d) - phase_offset
        return (phases + np.pi) % (2*np.pi) - np.pi
    elif q=='I':
        return np.real(d*rot_vec)
    elif q=='Q':
        return np.imag(d*rot_vec)
    else:
        ValueError("Quadrature must be specified as I, Q, A or P")



