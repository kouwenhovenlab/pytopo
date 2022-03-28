import numpy as np
import time

from qcodes.utils.validators import Ints, Numbers, Lists, Dict
from qcodes.instrument.base import Instrument

import broadbean as bb

import pytopo.awg_sequencing.csv_to_broadbean as csv

class MidasTektronixSequencer(Instrument):
    """
    Meta instrument for preparing pulse sequences and controlling
    MIDAS and Tektronix 5014c.

    It includes functions for programmating building of pulse
    sequence in which a single parameter is varied.

    Examples:
        Configure correction for attenuation and distortions:
            > sequencer.high_pass_cutoff_ch_2(1.7e3)
            > sequencer.high_pass_cutoff_ch_4(1.7e3)
            > sequencer.divider_ch_2(22.2)
            > sequencer.divider_ch_4(21.4)

        Generate a sequence based on a csv file:
            > sequencer.single_keyword_sequence('./pulses/sequence_measurement_testing.csv',
                                  'level', 4, 'A', np.linspace(-10e-3,10e-3,64))
            > sequencer.prepare_for_acquisition()
            > sequencer.samples_per_point(32)
            > sequencer.sequence_repetitions(512)

        Run a measurement 'by hand':
            > d = sequencer.arm_acquire_reshape()
    """

    def __init__(self, name, MIDAS_name, AWG_name, **kwargs):
        """
        Create a MidasTektronixSequencer instance

        Args:
            name (str): rasterer instrument name
            MIDAS_name (str): name of the Midas to be used
            MDAC_name (str): name of the MDAC to be used
            AWG_name (str): name of the Tektronix 5014 to be used
            **kwargs: other kwargs passed to Instrument init

        Returns:
            MidasTektronixSequencer
        """

        super().__init__(name, **kwargs)

        # code in the MIDAS parameters
        self.SAMPLE_TIME = (1/1.8e9)*512 # 284.44 ns
        self.POINTS_PER_BUFFER = 2048

        self.MIDAS = self.find_instrument(MIDAS_name)
        self.AWG = self.find_instrument(AWG_name)

        self.add_parameter('samples_per_point',
                        set_cmd=None,
                        initial_value=32,
                        vals=Ints(1,4096),
                        docstring="Set midas integration time"
                        " in units of MIDAS samples. Must be"
                        " a power of 2.")

        self.add_parameter('measurements_per_sequence',
                        set_cmd=None,
                        initial_value=64,
                        vals=Ints(1,2048),
                        docstring="Number of steps in a sequence"
                        " during which a measurement is performed.")

        self.add_parameter('points_total',
                            get_cmd=self._get_points_total)

        self.add_parameter('sequence_repetitions',
                        set_cmd=None,
                        initial_value=32,
                        vals=Ints(1,int(2e15)),
                        docstring="Number of steps in a sequence"
                        " during which a measurement is performed.")

        # parameters to correct for attenuation and most simple distortions
        for i in range(1,5):
            self.add_parameter('divider_ch_{}'.format(i),
                        set_cmd=None,
                        initial_value=1,
                        vals=Numbers())

            self.add_parameter('high_pass_cutoff_ch_{}'.format(i),
                        set_cmd=None,
                        initial_value=0,
                        vals=Numbers(min_value=0,max_value=1e9),
                        docstring="Cut off frequency of the high pass filter"
                        " which is to be compensated by predistorting"
                        " the AWG waveform.")


    ################### Get functions ###################

    def _get_points_total(self):
        return int(self.measurements_per_sequence()*
            self.sequence_repetitions())

    ################### Acquisiton functions ###################

    def AWG_channels_on(self):
        self.AWG.ch1_state(1)
        self.AWG.ch2_state(1)
        self.AWG.ch3_state(1)
        self.AWG.ch4_state(1)

    def AWG_channels_off(self):
        self.AWG.ch1_state(0)
        self.AWG.ch2_state(0)
        self.AWG.ch3_state(0)
        self.AWG.ch4_state(0)

    def prepare_for_acquisition(self):
        self.prepare_AWG()
        self.AWG_channels_on()
        self.prepare_MIDAS()

    def arm_acquire_reshape(self):
        self.arm_for_acquisition()
        time.sleep(1e-3)
        data = self.do_acquisition()
        self.data_raw = data
        # return data
        data = self.reshape(data)
        return data

    def prepare_AWG(self):
        """
        Uploads preprepared broadbean sequence to AWG.
        Applies scaling of the waveform based on divider parameters.
        """

        package = self.sequence.outputForAWGFile()
        # scale the waveforms based on the dividers
        for i in range(len(package._channels[0]['wfms'])):
            for j in range(4):
                package._channels[j]['wfms'][i] *= self['divider_ch_{}'.format(j+1)]()

        AWGfile = self.AWG.make_awg_file(*package[:])

        self.AWG.send_awg_file('sequence_1D',AWGfile)
        self.AWG.load_awg_file('sequence_1D')

        self.AWG.clock_freq(self.sequence.SR)

    def prepare_MIDAS(self):
        self.MIDAS.sw_mode('single_point')
        self.MIDAS.single_point_num_avgs(self.samples_per_point())

    def fn_start(self):
        self.AWG.force_trigger()

    def fn_stop(self):
        self.AWG.stop()

    def arm_for_acquisition(self):
        """
        Stop and start the execution of the sequence by
        the Tektronix to run it from the first sequence element.
        """
        self.AWG.stop()
        self.AWG.start()

    def do_acquisition(self):
        # capture_2d_trace is not really supported
        # with single-point mode by MIDAS so
        # take an approach of executing several acquisitions
        # restarting sequence each time
        # and adding a waiting time between them
        no_of_acquisitions = np.ceil(self._get_points_total() / self.POINTS_PER_BUFFER)

        data = []
        for i in range(int(no_of_acquisitions)):
            if i>0:
                self.arm_for_acquisition()
                time.sleep(0.01)
            data += [self.MIDAS.capture_1d_trace(
                                fn_start=self.fn_start,
                                fn_stop=self.fn_stop)]

        return np.array(data)

    def reshape(self, data):
        reshaped = []
        for i in range(8):
            d = data[:,i,:]
            if self.points_total()<2048:
                d = d[0,:self.points_total()]
            res = np.reshape(d, (self.sequence_repetitions(),
                                self.measurements_per_sequence()))
            avg = np.average(res, axis=0)
            reshaped.append(avg)

        return np.array(reshaped)

    def get_measurement_range(self):
        return self._measurement_range

    ################### Generating sequences ###################

    def sequence_from_keyword_sequence_table(self, bases,
            keywords, channels, segments, values,
            triggers, repeats, gotos, SR=1e9):

        '''
        Prepares a broadbean sequence object based on tables
        with sequence paramters.

        Args:
            bases (list/array): csv file names or broadbean elements
            keywords (list/array): keywords used to modify the elements
                in a sequence
            channels (list/array): channels to be modified according to
                the keyword. Many keywords don't require providing
                channel numbers. I this case the corresponding element
                in this list is ignored.
            segments (list/array): identifies a seqment in an element
                to which the changes are to be applied
            values (list/array): value to which a parameter specified
                by keyword is supposed to be set
            triggers (list/array): should AWG wait for external trigger
                before executing the corresponding
            repeats (list/array): number of consequtive repeatitions
                of the corresponding element
            gotos (list/array): number of the element in the sequence
                executed after this pulse. Numbering starts at 1!!!
                0 Indicates "next element"
            SR (float): sampling rate if AWG to be used
        '''
    
        # create an empty sequency
        seq = bb.Sequence()
        seq.setSR(SR)

        zp = zip(bases, keywords, channels, segments, values, triggers, repeats, gotos)
        for i, (b, k, c, s, v, t, r, g) in enumerate(zp):
            if type(b) is bb.element.Element:
                el = b
            else:
                el = csv.csv_to_element(b, SR=SR)
            el = modify_element(el, k, c, s, v)

            # apply correction if segment labeled 'net_zero'
            # is specified
            if 'net_zero' in el._data[1]['blueprint']._namelist:
                el = make_element_net_zero(el)

            # add a one and only element
            seq.addElement(i+1, el)
            seq.setSequencingTriggerWait(i+1, t)
            seq.setSequencingNumberOfRepetitions(i+1, r)
            seq.setSequencingGoto(i+1, g)

        for c in range(1,5):
            # UNCOMMENT (change amplitude to good values, not 1 V)
            ch_amp = self.AWG['ch'+str(c)+'_amp']()
            seq.setChannelAmplitude(c, ch_amp)
            seq.setChannelOffset(c, 0)

            if self['high_pass_cutoff_ch_{}'.format(c)]()>0:
                seq.setChannelFilterCompensation(c, 'HP',
                            order=1, f_cut=self['high_pass_cutoff_ch_{}'.format(c)]())

        self.sequence = seq

    def single_keyword_sequence(self, filename, keyword='',
                channel=None, segment=None, values=[], SR=1e9):
        """
        Prepares broadbean sequence based on a csv file
        specyfying a base element, and modifying it according to
        the provided keyword, channel and segment label.

        Args:
            filename (str):directory and name of the base csv file
            keyword (str): keyword according to which the base file is
                supposed to be configured by self.modify_element
            channel (int/None): number of the AWG channel to be modified
                according to the keyword. Some keywords do not require
                specyfying a channel or ignore it.
            segment (str/None): label of the element segment to be modified
                according to the keyword. Some keywords do not require
                specyfying a segment or ignore it.
            values (list/1d array): values passed self.modify_element
                indicating how to modify an element 
        """
        length = len(values)
        self.measurements_per_sequence(length)
        self._measurement_range = values
        base_files = [filename]*(length+1)
        keywords = ['no_marker'] + [keyword]*length
        channels = [None] + [channel]*length
        segments = [segment]*(length+1)
        triggers = [1] + [0]*length
        repeats = [5] + [1]*length
        gotos = [0]*length + [2]

        el = csv.csv_to_element(filename, SR=1e9)
        if 'net_zero' in el._data[1]['blueprint']._namelist:
                el = make_element_net_zero(el)
        self.base_element = el

        values = [0] + list(values)

        self.sequence_from_keyword_sequence_table(base_files,
                keywords, channels, segments, values,
                triggers, repeats, gotos, SR=SR)

############# ELEMENT MODIFIERS #############

def make_element_net_zero(el, channels=[1,2,3,4]):
    """
    Function for modyfying an element to make the mean voltage zero,
    in order to avoid DC offset in how the pulse is applied and
    to avoid dissipation of power on the bias-tee.

    Segment labeled 'net_zero' is identified. It's duration
    is unchanged but the applied voltage is adjusted to ensure
    mean zero voltage.

    Args:
        el (Element): element to be modified
        channels (list): list of channels to be made net-zero

    Returns:
        modified element
    """
    
    # reset correcting segment to 0
    t_total = el.duration
    SR = el.SR
    for ch in channels:
        el.changeArg(ch, 'net_zero', 'start', 0)
        el.changeArg(ch, 'net_zero', 'stop', 0)
        el.changeDuration(ch, 'net_zero', 10/SR)
    t_uncorrected = el.duration - 10/SR
    t_net_zero = t_total-t_uncorrected

    # forge single-element sequence
    seq = bb.Sequence()
    seq.addElement(1, el)
    seq.setSR(el.SR)
    forged_seq = seq.forge(includetime=True,
                            apply_delays=False,
                            apply_filters=False)

    # extract waveform for each channel
    # and adjust amplitude of the compenstaing segment
    for ch in channels: 
        # extract the waveform from the forget sequence
        waveform = forged_seq[1]['content'][1]['data'][ch]['wfm']
        # calculate the waveform integral
        integ = np.sum(waveform)/SR
        # calculate the voltage needed to achieve net zero
        v = -integ / t_net_zero

        el.changeArg(ch, 'net_zero', 'start', v)
        el.changeArg(ch, 'net_zero', 'stop', v)
        el.changeDuration(ch, 'net_zero', t_net_zero)

    return el

def modify_element(el, keyword, channel, segment, value):
    ############# ESSENTIAL KEYWORD MODIFIERS #############

    # do-not-modify keyword
    if keyword == 'pass':
        pass

    # case for changing a segment duration
    elif keyword == 'duration':
        for ch in range(1,5):
            el.changeDuration(ch, segment, value)

    # case for changing a segment duration
    elif keyword == 'no_marker':
        for name in el._data[1]['blueprint']._namelist: 
            for ch in range(1,5):
                el._data[ch]['blueprint'].removeSegmentMarker(name,1)
                el._data[ch]['blueprint'].removeSegmentMarker(name,2)

    # adjust the broadbean ramp element to have identical start
    # and stop point
    elif keyword == 'level':
        el = modify_element(el, 'start', channel, segment, value)
        el = modify_element(el, 'stop', channel, segment, value)

    ############# CUSTOM KEYWORD MODIFIERS #############

    elif keyword == 'detuning':
        r_L, r_R = 1,1
        ratio_L = r_L/np.sqrt(r_L**2 + r_R**2)
        ratio_R = r_R/np.sqrt(r_L**2 + r_R**2)

        # left gate
        el = modify_element(el, 'start', 2, segment, value*ratio_L)
        el = modify_element(el, 'stop', 2, segment, value*ratio_L)

        # right gate
        el = modify_element(el, 'start', 4, segment, -value*ratio_R)
        el = modify_element(el, 'stop', 4, segment, -value*ratio_R)


    ############# FALLBACK TO BROADBEAN #############

    # by default use a broadbean changeArg function
    else:
        el.changeArg(channel, segment, keyword, value)

    return el