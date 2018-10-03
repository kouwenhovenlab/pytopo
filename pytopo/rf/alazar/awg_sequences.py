import numpy as np
import qcodes as qc
import broadbean as bb
from broadbean.plotting import plotter

from pytopo.awg_sequencing import broadbean as bbtools
from pytopo.awg_sequencing.broadbean import BluePrints, BroadBeanSequence

ramp = bb.PulseAtoms.ramp
sine = bb.PulseAtoms.sine


class AlazarTestSequence(BroadBeanSequence):
    """
    A sequence that plays a pulse train of sine waves. 
    before each pulse we emit a trigger on a marker. 
    for each pulse in the sequence we can set time, frequency, phase, and amplitude.

    required channels:
        'pulse' : analog output
        'ats_trigger' : marker output
    """

    name = 'alazar_test_sequence'

    def sequence(self, pulse_times, frequencies, phases, amplitudes,
                 cycle_time=40e-6, pre_trig_time=0.1e-6, trig_time=0.1e-6):
        """
        Parameters:
        ----------                
            pulse times : sequence
                pulse times (in sec.)
                
            frequencies : sequence
                pulse frequencies (in Hz)
            
            phases : sequence
                pulse phases (in radians)
                
            amplitudes : sequence
                pulse amplitudes
                
            cycle_time : numeric, in s (default: 40e-6)
                time per pulse element (in sec.)
                difference between pulse time and cycle time results in 0 output for that time.
                
            pre_trig_time : numeric, in s (default: 100e-9)
                delay time before anything happens in the sequence.
                
            trig_time : numeric, in s (default: 100e-9)
                length of the trigger pulse. (the signal pulse starts after the trigger
                pulse ends.)
        """
        
        pulse_times = np.array(pulse_times)
        low_times = cycle_time - pulse_times - pre_trig_time - trig_time

        elements = []
        for pulse_time, low_time, frq, phase, amp in zip(pulse_times, low_times, frequencies, phases, amplitudes):
            bps = bbtools.BluePrints(chan_map=self.chan_map, length=cycle_time, sample_rate=self.SR)
            bps['pulse'].insertSegment(0, ramp, (0, 0), dur=pre_trig_time)
            bps['pulse'].insertSegment(1, ramp, (0, 0), name='trigger', dur=trig_time)
            bps['pulse'].insertSegment(2, sine, (frq, amp, 0, phase), name='pulse', dur=pulse_time)
            bps['pulse'].insertSegment(3, ramp, (0, 0), dur=low_time)
            bps['ats_trigger'] = [(pre_trig_time, trig_time)]
            elements.append(bbtools.blueprints2element(bps))
        
        return bbtools.elements2sequence(elements, self.name)


class TriggerSequence(BroadBeanSequence):
    """
    a sequence that consists of a single trigger element.

    required channels:
        'pulse' : analog output (for the 'debug' signal)
        'ats_trigger' : marker output
    """
    name = 'trigger_sequence'

    def sequence(self, trig_time=1e-6, cycle_time=10e-6,
                 pre_trig_time=1e-6, ncycles=1, debug_signal=False):

        end_buffer = 1e-6
        low_time = cycle_time - trig_time - pre_trig_time - end_buffer
        
        elements = []
        for i in range(ncycles):
            bps = bbtools.BluePrints(chan_map=self.chan_map, length=cycle_time, sample_rate=self.SR)
            if debug_signal:
                bps['pulse'].insertSegment(0, ramp, (0, 0), dur=pre_trig_time)
                bps['pulse'].insertSegment(1, ramp, (0, 0), name='trigger', dur=trig_time)
                bps['pulse'].insertSegment(2, sine, (1e6, 0.5, 0, 0), name='dbg_pulse', dur=low_time)
                bps['pulse'].insertSegment(3, ramp, (0, 0), dur=end_buffer)
            else:
                bps['pulse'].insertSegment(0, ramp, (0, 0), dur=cycle_time)
            
            bps['ats_trigger'] = [(pre_trig_time, trig_time)]
            elements.append(bbtools.blueprints2element(bps))
        
        return bbtools.elements2sequence(elements, self.name)
