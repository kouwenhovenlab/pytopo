import qcodes as qc
import broadbean as bb
from broadbean.plotting import plotter

ramp = bb.PulseAtoms.ramp
sine = bb.PulseAtoms.sine

def make_test_sequence_5208(awg, plot=False, start=True):
    """
    Makes a simple test sequence for an awg5208:
    * one element in the sequence, playing on channel 1
    * consists of a 10 us cycle that contains an 8 us 1 MHz sine wave
    * trigger high (marker 1) together with the sine pulse.
    """

    # some constants
    SR = 1e9
    lvl = 0.05
    cycle_time = 45e-6
    pre_trig_time = 0.1e-6
    pulse_time = 35e-6
    low_time = cycle_time - pulse_time - pre_trig_time

    # define our sole element. mostly hardcoded at this point.
    e = bb.Element()
    e_ch1 = bb.BluePrint()
    e_ch1.setSR(SR)
    e_ch1.insertSegment(0, ramp, (0, 0), dur=pre_trig_time)
    e_ch1.insertSegment(1, sine, (1e6, lvl, 0, 0), name='pulse', dur=pulse_time)
    e_ch1.insertSegment(2, ramp, (0, 0), dur=low_time)
    e_ch1.setSegmentMarker('pulse', (0, pulse_time), 1)
    e_ch1.setSegmentMarker('pulse', (0, pulse_time), 2)
    e.addBluePrint(1, e_ch1)

    # create sequence, and program the flow (1 element, keep repeating)
    seq = bb.Sequence()
    seq.name = 'sequence'
    seq.addElement(1, e)   
    seq.setSequencingTriggerWait(1, 0)
    seq.setSequencingNumberOfRepetitions(1, 1)
    seq.setSequencingGoto(1, 1)

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

    waveform_list = awg.waveformList
    waveform_name = waveform_list[0]
    awg.ch1.setWaveform(waveform_name)
    awg.ch1.resolution(12)
    awg.ch1.set('state', 1)

    if start:
        awg.play()

    return True

