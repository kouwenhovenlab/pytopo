import numpy as np
import time

from qcodes.utils.validators import Ints, Numbers, Lists, Dict
from qcodes.instrument.base import Instrument

import broadbean as bb

import pytopo.awg_sequencing.csv_to_broadbean as csv

class MidasTektronixSequencer(Instrument):

    def __init__(self, name, MIDAS_name, AWG_name, **kwargs):

        super().__init__(name, **kwargs)

        # code in the MIDAS parameters
        self.SAMPLE_TIME = (1/1.8e9)*512 # 284.44 ns
        self.POINTS_PER_BUFFER = 2048

        # UNCOMMENT ME!!!
        # self.MIDAS = self.find_instrument(MIDAS_name)
        # self.AWG = self.find_instrument(AWG_name)

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
                        vals=Ints(1,2048),
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

    def prepare_for_acquisition(self):
        self.prepare_AWG()
        self.AWG_channels_on()
        self.prepare_MIDAS()
        self.prepare_MDAC()

    def prepare_AWG(self):
        package = self.sequence.outputForAWGFile()

        # scale the waveforms based on the dividers
        for i in range(len(package._channels)):
            for j in range(4):
                package._channels[i]['wfms'][j] *= self['divider_ch_{}'.format(j+1)]()


        # UNCOMMENT
        return package

        # AWGfile = self.AWG.make_awg_file(*package[:])

        # self.AWG.send_awg_file('sequence_1D',AWGfile)
        # self.AWG.load_awg_file('sequence_1D')

    def prepare_MIDAS(self):
        self.MIDAS.sw_mode('single_point')
        self.MIDAS.single_point_num_avgs(self.samples_per_point())

    def fn_start(self):
        self.AWG.force_trigger()

    def fn_stop(self):
        self.AWG.stop()

    def arm_for_acquisition(self):
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
        for i in range(no_of_acquisitions):
            if i>0:
                self.arm_for_acquisition()
                time.sleep(0.01)
            data += [self.MIDAS.capture_1d_trace(
                                fn_start=self.fn_start,
                                fn_stop=self.fn_stop)]

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
            # ch_amp = AWG['ch'+str(c)+'_amp']()
            seq.setChannelAmplitude(c, 1)
            seq.setChannelOffset(c, 0)

            if self['high_pass_cutoff_ch_{}'.format(c)]()>0:
                seq.setChannelFilterCompensation(c, 'HP',
                            order=1, f_cut=self['high_pass_cutoff_ch_{}'.format(c)]())

        self.sequence = seq

    def single_keyword_sequence(self, filename, keyword='', channel=None, segment=None, values=[]):
        length = len(values)
        self.measurements_per_sequence(length)
        self._measurement_range = values
        base_files = [filename]*(length+1)
        keywords = ['no_marker'] + [keyword]*length
        channels = [None] + [channel]*length
        segments = [segment]*(length+1)
        triggers = [1] + [0]*length
        repeats = [10] + [1]*length
        gotos = [0]*length + [2]

        self.sequence_from_keyword_sequence_table(base_files,
                keywords, channels, segments, values,
                triggers, repeats, gotos)

############# ELEMENT MODIFIERS #############

def make_element_net_zero(el, channels=[1,2,3,4]):
    
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
    # do not modify
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

    elif keyword == 'level':
        el = modify_element(el, 'start', channel, segment, value)
        el = modify_element(el, 'stop', channel, segment, value)

    # by default use a broadbean changeArg function
    else:
        el.changeArg(channel, segment, keyword, value)

    return el