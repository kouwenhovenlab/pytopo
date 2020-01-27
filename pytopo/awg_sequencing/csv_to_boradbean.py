import pandas as pd
import broadbean as bb
import numpy as np

segment_dict = {'ramp': bb.PulseAtoms.ramp,
                'sine': bb.PulseAtoms.sine,
                'gaussian': bb.PulseAtoms.gaussian}

def csv_to_broadbean(filename, SR=1e9):
    # load csv file
    df = pd.read_csv(filename)

    # convert columns of the dataframe to the correct format
    df = convert_dataframe_columns(df)

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
    df['CH1_params'] = df['CH1_params'].apply(lambda x: tuple([float(y) for y in x.split(', ')]))
    df['CH2_params'] = df['CH2_params'].apply(lambda x: tuple([float(y) for y in x.split(', ')]))
    df['CH3_params'] = df['CH3_params'].apply(lambda x: tuple([float(y) for y in x.split(', ')]))
    df['CH4_params'] = df['CH4_params'].apply(lambda x: tuple([float(y) for y in x.split(', ')]))
    
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
        bp.insertSegment(-1, segment_dict[tp], p, name=l, dur=t)
        if m1:
            bp.setSegmentMarker(l, (0,t), 1)
        if m2:
            bp.setSegmentMarker(l, (0,t), 2)
    
    return bp