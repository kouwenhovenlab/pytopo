import numpy as np
import qcodes as qc
import broadbean as bb
from broadbean.plotting import plotter

ramp = bb.PulseAtoms.ramp
sine = bb.PulseAtoms.sine


def make_test_sequence(awg, pulse_times, frequencies, phases, amplitudes,
                       SR=1e9, cycle_time=40e-6, pre_trig_time=0.1e-6, 
                       trig_time=0.1e-6, plot=True, start_awg=True):
    """
    make a sequence that plays a pulse train of sine waves on ch1. 
    before each pulse we emit a trigger on ch1/m1. 
    for each pulse in the sequence we can set time, frequency, phase, and amplitude.
    
    at the moment only implemented for AWG5208.
    
    Note: length of pulse_times, frequencies, phases and amplitudes have to match.
    you have to set each for every pulse.
    
    Parameters:
    ----------
        awg : qcodes instrument instance
            awg instrument
            
        pulse times : sequence
            pulse times (in sec.)
            
        frequencies : sequence
            pulse frequencies (in Hz)
        
        phases : sequence
            pulse phases (in radians)
            
        amplitudes : sequence
            pulse amplitudes
            
        SR : numeric, in Hz (default: 1e9)
            AWG sample rate
            
        cycle_time : numeric, in s (default: 40e-6)
            time per pulse element (in sec.)
            difference between pulse time and cycle time results in 0 output for that time.
            
        pre_trig_time : numeric, in s (default: 100e-9)
            delay time before anything happens in the sequence.
            
        trig_time : numeric, in s (default: 100e-9)
            length of the trigger pulse. (the signal pulse starts after the trigger
            pulse ends.)
              
        plot : bool (default: True)
            if True, plot the sequence (with broadbean plot method)
            
        start_awg : bool (default : True)
            if True, start the AWG.
        
    """
    
    if awg.model != '5208':
        raise ValueError('Only AWG5208 implemented right now.')
    
    pulse_times = np.array(pulse_times)
    low_times = cycle_time - pulse_times - pre_trig_time - trig_time

    # define our elements. one per length.
    elements = []
    for pulse_time, low_time, frq, phase, amp in zip(pulse_times, low_times, frequencies, phases, amplitudes):
        e = bb.Element()
        e_ch1 = bb.BluePrint()
        e_ch1.setSR(SR)
        e_ch1.insertSegment(0, ramp, (0, 0), dur=pre_trig_time)
        e_ch1.insertSegment(1, ramp, (0, 0), name='trigger', dur=trig_time)
        e_ch1.insertSegment(2, sine, (frq, amp, 0, phase), name='pulse', dur=pulse_time)
        e_ch1.insertSegment(3, ramp, (0, 0), dur=low_time)
        e_ch1.setSegmentMarker('trigger', (0, trig_time), 1)
        e_ch1.setSegmentMarker('trigger', (0, trig_time), 2)
        e.addBluePrint(1, e_ch1)
        elements.append(e)

    # create sequence, and program the flow (1 element, keep repeating)
    seq = bb.Sequence()
    seq.name = 'acquisition_test_sequence'
    for i, e in enumerate(elements):
        seq.addElement(i+1, e)
        seq.setSequencingTriggerWait(i+1, 0)
        seq.setSequencingNumberOfRepetitions(i+1, 1)
    seq.setSequencingGoto(i+1, 1)

    # output options (sample rate, amplitude, ...)
    seq.setSR(SR)
    seq.setChannelAmplitude(1, 1)
    seq.setChannelOffset(1, 0)

    # plot if required
    if plot:
        plotter(seq)

    # make the sequence file and program the awg
    forged_sequence = seq.forge()
    seqx_file = awg.make_SEQX_from_forged_sequence(forged_sequence, [1,], seq.name)
    seqx_file_name = f'{seq.name}.seqx'

    awg.clearSequenceList()
    awg.clearWaveformList()
    awg.sendSEQXFile(seqx_file, filename=seqx_file_name)
    awg.loadSEQXFile(seqx_file_name)
    awg.sample_rate(SR)
    awg.ch1.setSequenceTrack(seq.name, 1)

    awg.ch1.resolution(12)
    awg.ch1.set('state', 1)

    if start_awg:
        awg.play()


def make_trigger_sequence(awg, chan=1, marker=1, trig_time=1e-6, cycle_time=10e-6,
                          pre_trig_time=1e-6, ncycles=1,
                          debug_signal=False, wait=True, SR=1e7, start_awg=True):
    """
    make a sequence that consists of a single trigger element.
    """
    if awg.model != '5208':
        raise ValueError('Only AWG5208 implemented right now.')

    end_buffer = 1e-6
    low_time = cycle_time - trig_time - pre_trig_time - end_buffer

    elements = []
    for i in range(ncycles):
        e = bb.Element()
        bp = bb.BluePrint()
        bp.setSR(SR)
        bp.insertSegment(0, ramp, (0, 0), dur=pre_trig_time)
        bp.insertSegment(1, ramp, (0, 0), name='trigger', dur=trig_time)
        if debug_signal:
            bp.insertSegment(2, sine, (1e6, 0.5, 0, 0), name='dbg_pulse', dur=low_time)
        else:
            bp.insertSegment(2, ramp, (0, 0), dur=low_time)
        bp.insertSegment(3, ramp, (0, 0), dur=end_buffer)
        bp.setSegmentMarker('trigger', (0, trig_time), marker)
        e.addBluePrint(chan, bp)
        elements.append(e)

    # create sequence, and program the flow (1 element, keep repeating)
    seq = bb.Sequence()
    seq.name = 'trigger_sequence'
    for i, e in enumerate(elements):
        seq.addElement(i+1, e)
    seq.setSequencingTriggerWait(1, int(wait))
    seq.setSequencingGoto(i+1, 1)

    # output options (sample rate, amplitude, ...)
    seq.setSR(SR)
    seq.setChannelAmplitude(chan, 1)
    seq.setChannelOffset(chan, 0)

    # make the sequence file and program the awg
    forged_sequence = seq.forge()
    seqx_file = awg.make_SEQX_from_forged_sequence(forged_sequence, [1,], seq.name)
    seqx_file_name = f'{seq.name}.seqx'

    awg.clearSequenceList()
    awg.clearWaveformList()
    awg.sendSEQXFile(seqx_file, filename=seqx_file_name)
    awg.loadSEQXFile(seqx_file_name)
    awg.sample_rate(SR)
    awg.channels[chan-1].setSequenceTrack(seq.name, 1)

    awg.channels[chan-1].resolution(12)
    awg.channels[chan-1].set('state', 1)

    if start_awg:
        awg.play(timeout=20)


if __name__ == '__main__':
    awg = None
    try:
        awg = qc.Instrument.find_instrument('awg')
    except:
        print('Could not find AWG automatically.')

    if awg is not None:
        N = 10
        pulse_times = [10e-6] * N
        amplitudes = np.arange(N) * 0.02
        frequencies = [1e6] * N
        phases = np.arange(N) * 10.

        make_test_sequence(awg, pulse_times, frequencies, phases, amplitudes)
