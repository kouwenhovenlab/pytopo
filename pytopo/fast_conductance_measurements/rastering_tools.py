import broadbean as bb
ramp = bb.PulseAtoms.ramp

from qcodes.utils.validators import Ints, Numbers, Lists
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
Search for WORKAROUND for places when the tweaks were made to work around
the issues
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
                            " a sawtooth. Marker 1 of this channel is used"
                            " as a trigger for Midas.")

        self.add_parameter('MIDAS_channels',
                            set_cmd=None,
                            initial_value=[1],
                            vals=Lists(elt_validator=Ints(min_value=1,max_value=8)),
                            docstring="List of Midas channels to return")

        self.add_parameter('samples_per_pixel',
                        set_cmd=None,
                        initial_value=32,
                        vals=Ints(1,8192),
                        docstring="Number of 284.44 ns-long samples to"
                        " be averaged to get a single data pixel."
                        " Must be a power of 2.")

        self.add_parameter('midas_retriggering_time',
                        set_cmd=None,
                        initial_value=10e-9,
                        vals=Numbers(1e-9, 1e-3),
                        docstring="Additional waiting time to let"
                        " the Midas ready to acquire next sample")

        self.add_parameter('midas_buffer_flushing_time',
                        set_cmd=None,
                        initial_value=1e-3,
                        vals=Numbers(10e-6, 100e-3),
                        docstring="Additional waiting time to let"
                        " the Midas flush the buffer"
                        " and get ready for more triggers")

        self.add_parameter('pre_wait',
                            set_cmd=None,
                            initial_value=1e-3,
                            vals=Numbers(min_value=0, max_value=0.1),
                            docstring="Duration of the 'wait' segment in the"
                            " applied sequence of sawtooths. It's purpose is to"
                            " ensure that MDAC sweep starts synchronously with"
                            " the Midas acquisition.")

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
        This function prepares and uploades a needed sequence
        to Tektronix 5014.
        Should be implemented in a subclass.
        """
        raise NotImplementedError(
            'This method should be implemented in a subclass')

    def prepare_MIDAS(self):
        """
        This function sets up the MIDAS to do the acquisition.
        Should be implemented in a subclass.
        """
        raise NotImplementedError(
            'This method should be implemented in a subclass')

    def fn_start(self):
        """
        This function is will be exectued by
        MIDAS.captire_[...] just before the acquisition.
        Should be implemented in a subclass.
        """
        raise NotImplementedError(
            'This method should be implemented in a subclass')

    def fn_stop(self):
        """
        This function is will be exectued by
        MIDAS.captire_[...] just after the acquisition.
        Should be implemented in a subclass.
        """
        raise NotImplementedError(
            'This method should be implemented in a subclass')

    def do_acquisition(self):
        """
        This function executes a MIDAS capture method
        and returns an ndarray with the data.
        Should be implemented in a subclass.
        """
        raise NotImplementedError(
            'This method should be implemented in a subclass')

    def reshape(self):
        """
        This function reshapes and performs required averaging
        of the data returned by do_acquisition()
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

    def arm_for_acquisition(self):
        self.AWG.stop()
        self.AWG.start()

    def arm_acquire_reshape(self):
        self.arm_for_acquisition()
        time.sleep(1e-3)
        data = self.do_acquisition()
        # return data
        data = self.reshape(data)
        # pick selected MIDAS channels
        self.data = []
        for ch in self.MIDAS_channels():
            self.data.append(data[ch-1])
        return np.array(self.data)

##################################################################
######################## 1D MDAC rasterer ########################
##################################################################

class MidasMdacAwg1DSlowRasterer(MidasMdacAwgParentRasterer):
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

        self.add_parameter('MDAC_Vpp',
                            set_cmd=None,
                            initial_value=0.1,
                            vals=Numbers(min_value=0),
                            docstring="Amplitude of a single sweep with"
                            " MDAC. DC offset is given by the current setting"
                            " of the MDAC channel. After acquisition the channel"
                            " voltage is set back to the initial value.")

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

    ################### Get functions ###################

    # def _get_time_per_pixel(self):
    #     # calculate how much time does it take to measure
    #     # a single pixel
    #     return self.samples_to_time(self.samples_per_pixel())

    def _get_time_per_pixel(self):
        # calculate how much time does it take to measure
        # a single pixel
        tM = self.samples_to_time(self.samples_per_pixel())
        tM += self.midas_retriggering_time()
        return tM

    ################### Other functions ###################

    def prepare_AWG(self):
        # use 10 MS/s AWG sampling rate
        AWG_sampling_rate = 10e6

        # generate a sequence to upload to AWG
        # reuse single_sawtooth_many_triggers
        self.sequence = single_sawtooth_many_triggers(self.AWG,
                            AWG_sampling_rate,
                            self.AWG_channel(),
                            self.time_per_pixel(),
                            1,
                            self.midas_buffer_flushing_time(),
                            0,
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
        self.MIDAS.single_point_num_avgs(self.samples_per_pixel())

    def fn_start(self):
        # get the MDAC channel
        MDAC_ch = self.MDAC.channels[self.MDAC_channel()-1]
        self.V_start = MDAC_ch.voltage()

        # calculate measurement time:
        sweep_time = self.pixels()*self.time_per_pixel()

        # calculate the rate of the MDAC sweep
        self.ramp_rate = self.MDAC_Vpp()/sweep_time

        # set the MDAC channel to the initial voltage
        MDAC_ch.ramp(self.V_start - self.MDAC_Vpp()/2, ramp_rate=self.ramp_rate*5)
        MDAC_ch.block()

        # trigger AWG and start the MDAC ramp ASAP
        # this order combined with ~10 ms pre-wait gives
        # aynchronized start of the sweep and data acquisition
        self.AWG.force_trigger()
        MDAC_ch.ramp(self.V_start + self.MDAC_Vpp()/2, ramp_rate=self.ramp_rate)

    def fn_stop(self):
        MDAC_ch = self.MDAC.channels[self.MDAC_channel()-1]

        MDAC_ch.ramp(self.V_start, ramp_rate=self.ramp_rate*5)
        MDAC_ch.block()
        self.AWG.stop()

    def do_acquisition(self):
        data = self.MIDAS.capture_1d_trace(
                            fn_start=self.fn_start,
                            fn_stop=self.fn_stop)
        return data

    def reshape(self, data):
        return data[:,:self.pixels()]

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
                            self.AWG_Vpp(),
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

    def fn_start(self):
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

        # set the MDAC channel to the initial voltage
        MDAC_ch.ramp(self.V_start - self.MDAC_Vpp()/2, ramp_rate=self.ramp_rate*5)
        MDAC_ch.block()

        # trigger AWG and start the MDAC ramp ASAP
        # this order combined with ~10 ms pre-wait gives
        # aynchronized start of the sweep and data acquisition
        self.AWG.force_trigger()
        MDAC_ch.ramp(self.V_start + self.MDAC_Vpp()/2, ramp_rate=self.ramp_rate)

    def fn_stop(self):
        MDAC_ch = self.MDAC.channels[self.MDAC_channel()-1]

        MDAC_ch.ramp(self.V_start, ramp_rate=self.ramp_rate*5)
        MDAC_ch.block()
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

########## Testing 2D rasterer with repeated capture_1d_trace ##########

class MidasMdacAwg2DRasterer_test(MidasMdacAwg2DRasterer):

    def __init__(self, name, MIDAS_name, MDAC_name, AWG_name, **kwargs):

        super().__init__(name,
                MIDAS_name, MDAC_name, AWG_name,
                **kwargs)

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

########## Testing 2D rasterer with single_shot mode ##########

class MidasMdacAwg2DSingleShotRasterer(MidasMdacAwg2DRasterer):

    def __init__(self, name, MIDAS_name, MDAC_name, AWG_name, **kwargs):

        super().__init__(name,
                MIDAS_name, MDAC_name, AWG_name,
                **kwargs)

    def _get_ramps_per_buffer(self):
        return 1

    def _get_buffers_per_acquisition(self):
        return self.ramps_per_line()*self.lines_per_acquisition()

    def prepare_AWG(self):
        # use low AWG sampling rate, but not smaller than
        # minimum 10 MS/s
        AWG_sampling_rate = max(200/self.ramp_time_fast(), 10e6)

        # generate a sequence to upload to AWG
        self.sequence = single_sawtooth_many_triggers(self.AWG,
                            AWG_sampling_rate,
                            self.AWG_channel(),
                            self.ramp_time_fast(),
                            1,
                            self.midas_buffer_flushing_time(),
                            self.AWG_Vpp(),
                            triggersPerFlush=1,
                            pre_wait=self.pre_wait())

        # upload
        package = self.sequence.outputForAWGFile()
        AWGfile = self.AWG.make_awg_file(*package[:])

        self.AWG.send_awg_file('raster',AWGfile)
        self.AWG.load_awg_file('raster')

        self.AWG.clock_freq(AWG_sampling_rate)

        return self.sequence

    def prepare_MIDAS(self):
        self.MIDAS.sw_mode('single_shot')
        self.MIDAS.num_sweeps_2d(self.buffers_per_acquisition())

    def do_acquisition(self):
        data = self.MIDAS.capture_2d_trace(
                            fn_start=self.fn_start,
                            fn_stop=self.fn_stop)
        return np.array(data)

    def reshape(self, data):
        reshaped = []
        for i in range(8):
            d = data[:,i,:self.samples_per_ramp()]
            res = np.reshape(d, (self.lines_per_acquisition(),
                                self.ramps_per_line(),
                                self.pixels_per_line(),
                                -1))
            avg = np.average(res, axis=1)
            avg = np.average(avg, axis=-1)
            reshaped.append(avg)

        return np.array(reshaped)

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
    wait_element.addBluePrint(ch, wait_blueprint)

    wait_element.validateDurations()

    # make a single-segment sawtooth element
    sawtooth_blueprint = bb.BluePrint()
    sawtooth_blueprint.setSR(sampling_rate)
    sawtooth_blueprint.insertSegment(-1, ramp, (-Vpp/2, Vpp/2),
                                name='ramp',
                                dur=rampTime)

    pointTime = rampTime/triggersPerRamp
    sawtooth_blueprint.marker1 = [(pointTime*i, 150e-9) for i in range(triggersPerRamp)]
    sawtooth_blueprint.marker2 = [(pointTime*i, 150e-9) for i in range(triggersPerRamp)]

    sawtooth_element = bb.Element()
    sawtooth_element.addBluePrint(ch, sawtooth_blueprint)

    sawtooth_element.validateDurations()

    # make an element what waits for buffer flushing
    flush_blueprint = bb.BluePrint()
    flush_blueprint.setSR(sampling_rate)
    flush_blueprint.insertSegment(-1, ramp, (0, 0),
                                    name='wait',
                                    dur=flushingTime)
    flush_element = bb.Element()
    flush_element.addBluePrint(ch, flush_blueprint)

    flush_element.validateDurations()

    # make a sequence
    # wait - sawtooth (repeat) - flush - go to sawtooth
    sequence = bb.Sequence()
    sequence.addElement(1, wait_element)
    sequence.setSequencingTriggerWait(1, 1)
    sequence.setSequencingNumberOfRepetitions(1,1)
    sequence.setSequencingGoto(1,0)

    sequence.addElement(2, sawtooth_element)
    sequence.setSequencingTriggerWait(2, 0)
    rampsPerFlush = triggersPerFlush/triggersPerRamp
    sequence.setSequencingNumberOfRepetitions(2,rampsPerFlush)
    sequence.setSequencingGoto(2,0)

    sequence.addElement(3, flush_element)
    sequence.setSequencingTriggerWait(3, 0)
    sequence.setSequencingNumberOfRepetitions(3,1)
    sequence.setSequencingGoto(3,2)

    ch_amp = AWG['ch'+str(ch)+'_amp']()
    sequence.setChannelAmplitude(ch, ch_amp)
    sequence.setChannelOffset(ch, 0)

    sequence.setSR(sampling_rate)

    return sequence
