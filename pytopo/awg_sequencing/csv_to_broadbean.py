import pandas as pd
import broadbean as bb
import numpy as np
from copy import deepcopy

segment_dict = {'ramp': bb.PulseAtoms.ramp,
                'sine': bb.PulseAtoms.sine,
                'gaussian': bb.PulseAtoms.gaussian}

############# SINGLE PULSE FUNCTIONS #############

def csv_to_element(filename, SR=1e9):
    # load csv file
    df = csv_to_dataframe(filename)

    # make bluprints
    blueprints = []
    for c in range(1,5):
        bp = params_to_blueprint(df['Label'],
                                df['Time'],
                                df['CH{}_type'.format(c)],
                                df['CH{}_params'.format(c)],
                                df['CH{}_M1'.format(c)],
                                df['CH{}_M2'.format(c)])
        bp.setSR(SR)
        blueprints.append(bp)

    # join blueprints into elements (pulses)
    elem = bb.Element()
    for i, bp in enumerate(blueprints):
        elem.addBluePrint(i+1, bp)
    elem.validateDurations()

    return elem

# upload a sequence which plays a single element over and over again
def upload_one_element_sequence(el, AWG, SR=1e9, high_pass_cutoff=[None]*4):
    # create a sequence
    seq = bb.Sequence()

    # set sampling rate
    seq.setSR(SR)
    AWG.clock_freq(SR)

    # apply correction if segment labeled 'net_zero'
    # is specified
    if 'net_zero' in el._data[1]['blueprint']._namelist:
        el = make_element_net_zeto(el)
    
    # add a one and only element
    seq.addElement(1, el)
    seq.setSequencingTriggerWait(1, 1)
    seq.setSequencingNumberOfRepetitions(1,0)
    seq.setSequencingGoto(1,1)

    # make sure the channel amps are correct
    for ch, f_cut in zip(range(1,5), high_pass_cutoff):
        ch_amp = AWG['ch'+str(ch)+'_amp']()
        seq.setChannelAmplitude(ch, ch_amp)
        seq.setChannelOffset(ch, 0)

        if (f_cut is None) or (f_cut == 0):
            continue
        else:
            seq.setChannelFilterCompensation(ch, 'HP',
                            order=1, f_cut=f_cut)


    # prepare a file to upload
    package = seq.outputForAWGFile()
    AWGfile = AWG.make_awg_file(*package[:])

    #upload and load to output
    AWG.send_awg_file('single_pulse',AWGfile)
    AWG.load_awg_file('single_pulse')

############# HELPER FUNCTIONS #############

def csv_to_dataframe(filename):
    # load csv file
    df = pd.read_csv(filename)

    # convert columns of the dataframe to the correct format
    df = convert_dataframe_columns(df)

    return df

# convert columns of the dataframe to the correct format
def convert_dataframe_columns(df):
    # Segment labels are strings
    df['Label'] = df['Label'].apply(str)
    # Time is a float
    df['Time'] = df['Time'].apply(float)

    # Segment types are strings
    df['CH1_type'] = df['CH1_type'].apply(str)
    df['CH2_type'] = df['CH2_type'].apply(str)
    df['CH3_type'] = df['CH3_type'].apply(str)
    df['CH4_type'] = df['CH4_type'].apply(str)

    # Segment parameters are lists of floats
    df['CH1_params'] = df['CH1_params'].apply(lambda x: [float(y) for y in x.split(',')])
    df['CH2_params'] = df['CH2_params'].apply(lambda x: [float(y) for y in x.split(',')])
    df['CH3_params'] = df['CH3_params'].apply(lambda x: [float(y) for y in x.split(',')])
    df['CH4_params'] = df['CH4_params'].apply(lambda x: [float(y) for y in x.split(',')])
    
    # Markers during segments are booleans
    df['CH1_M1'] = df['CH1_M1'].apply(bool)
    df['CH1_M2'] = df['CH1_M2'].apply(bool)
    df['CH2_M1'] = df['CH2_M1'].apply(bool)
    df['CH2_M2'] = df['CH2_M2'].apply(bool)
    df['CH3_M1'] = df['CH3_M1'].apply(bool)
    df['CH3_M2'] = df['CH3_M2'].apply(bool)
    df['CH4_M1'] = df['CH4_M1'].apply(bool)
    df['CH4_M2'] = df['CH4_M2'].apply(bool)

    return df

def params_to_blueprint(label, time, typ, params, M1, M2,):
    bp = bb.BluePrint()

    for l, t, tp, p, m1, m2 in zip(label, time, typ, params, M1, M2):
        # check if net_zero element is used
        if l == 'net_zero':
            # break
            pass

        bp.insertSegment(-1, segment_dict[tp], tuple(p), name=l, dur=t)
        if m1:
            bp.setSegmentMarker(l, (0,t), 1)
        if m2:
            bp.setSegmentMarker(l, (0,t), 2)

    return bp

def make_element_net_zeto(el, channels=[1,2,3,4]):
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

############# ELEMENT MODIFIER #############


