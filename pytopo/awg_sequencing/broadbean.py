"""
broadbean.py
A set of tools to make working with the broadbean awg sequencer a bit more convenient.
"""

import numpy as np
import broadbean as bb
from broadbean.plotting import plotter

from qcodes.instrument_drivers.tektronix.AWG5208 import AWG5208
from qcodes.instrument_drivers.tektronix.AWG5014 import Tektronix_AWG5014 as AWG5014

ramp = bb.PulseAtoms.ramp


def default_chan_settings(nchans=4, nmarkers=2):
    settings = {}
    for i in range(nchans):
        settings[i+1] = {}
        settings[i+1]['Vpp'] = 1.0
        settings[i+1]['offset'] = 0.0
        settings[i+1]['marker_lo'] = [0.0] * nmarkers
        settings[i+1]['marker_hi'] = [1.0] * nmarkers
    return settings


def blueprints2element(bps):
    """
    Create a bb element from a BluePrints object.
    """
    e = bb.Element()
    for n, bp in bps():
        e.addBluePrint(n, bp)
    return e


def elements2sequence(element_lst, name='sequence', wait='first'):
    """
    Create a sequence from a list of elements.
    Sequence will just be 1 element per list item, in that order.

    Parameters:
    -----------
    element_lst : list of bb elements

    name : str (default: 'sequence')
    
    wait : str (default: 'first')
        if 'first', then we set the trigger wait to True for the first element.
        all other values are ignored at the Moment.

    Returns:
    --------
    the generated bb sequence.
    """
    seq = bb.Sequence()
    seq.name = name
    for i, e in enumerate(element_lst):
        seq.addElement(i+1, e)
        seq.setSequencingTriggerWait(i+1, int(wait=='each'))
        seq.setSequencingNumberOfRepetitions(i+1, 1)
        
    if wait == 'first':
        seq.setSequencingTriggerWait(1, 1)
            
    seq.setSequencingGoto(i+1, 1)
    return seq


class BluePrints(object):

    FILL_TOKENS = [f'EMPTY_{i}' for i in range(1,9)]
    
    def __init__(self, chan_map, sample_rate=1e9, 
                 autofill=True, detect_autofill=True, length=None):
        self.bps = {}
        self.map = {}
        chan_map = chan_map.copy()
        
        for i, lst in chan_map.items():
            self.bps[i] = bb.BluePrint()
            self.bps[i].setSR(sample_rate)

            if detect_autofill:
                if lst[0] is None and len(lst) > 1:
                    for elt in lst[1:]:
                        if elt not in [None, '']:
                            lst[0] = self.FILL_TOKENS[i-1]

            for j, name in enumerate(lst):     
                if name is not None:
                    self.map[name] = (i, j)

                if autofill and length is not None and name in self.FILL_TOKENS:
                    self[name].insertSegment(0, ramp, (0, 0), dur=length, name=name+'_segment')
                    
    def __getitem__(self, name):
        if self.map[name][1] == 0:
            return self.bps[self.map[name][0]]
        else:
            return getattr(self.bps[self.map[name][0]], 'marker{}'.format(self.map[name][1]))
        
    def __setitem__(self, name, value):
        if self.map[name][1] == 0:
            self.bps[self.map[name][0]] = value
        else:
            setattr(self.bps[self.map[name][0]], 'marker{}'.format(self.map[name][1]), value)
        
    def __call__(self):
        return list(self.bps.items())


class BroadBeanSequence():
    
    chan_map = {}
    chan_settings = None
    wait = 'first'
    repeat_mode = 'sequence'
    name = 'sequence'
        
    def __init__(self, awg, name=None, chan_map=None, SR=1e9, chan_settings=None):
        self.awg = awg
        self.SR = SR
        if name is not None:
            self.name = name
        
        if chan_map is not None:
            self.chan_map = chan_map

        if self.chan_settings is None:
            self.chan_settings = default_chan_settings()
        else:
            _chan_settings = default_chan_settings()
            for i, settings in self.chan_settings.items():
                _chan_settings[i].update(settings)
            self.chan_settings = _chan_settings

            if chan_settings is not None:
                for i, settings in chan_settings.items():
                    self.chan_settings[i].update(settings)
        
    def sequence(self, **kw):
        raise NotImplementedError
        
    def setup_awg(self, program_awg=True, start_awg=True, stop_awg=True, plot=False, **kw):       
        if stop_awg:
            self.awg.stop()
        
        if program_awg:
            
            seq = self.sequence(**kw)
            seq.setSR(self.SR)
            
            # for ch_no, ch_set in self.chan_settings.items():
            #     seq.setChannelAmplitude(ch_no, ch_set['Vpp'] * 0)
            #     seq.setChannelOffset(ch_no, ch_set['offset'])
            
            if self.wait == 'first':
                seq.setSequencingTriggerWait(1, 1)
            elif self.wait == 'off':
                seq.setSequencingTriggerWait(1, 0)
            elif self.wait == None:
                pass
            else:
                raise ValueError("Unknown sweep_wait setting '{}".format(self.wait))

            if self.repeat_mode == 'sequence':
                seq.setSequencingGoto(seq.length_sequenceelements, 1)
            elif self.repeat_mode == None:
                pass
            else:
                raise ValueError("Unknown sweep_repeat setting '{}".format(self.repeat_mode))

            # plot if required
            if plot:
                plotter(seq)

            if isinstance(self.awg, AWG5014):
                pkg = seq.outputForAWGFile()
                self.awg.make_send_and_load_awg_file(*pkg[:])

                for ch_no in self.chan_map.items():
                    self.awg.set('ch{}_state'.format(ch_no), 1)

                for ch_no, ch_set in self.chan_settings.items():
                    self.awg.set('ch{}_amp'.format(ch_no), ch_set['Vpp'])
                    self.awg.set('ch{}_offset'.format(ch_no), ch_set['offset'])

                self.awg.clock_freq(self.SR)

            elif isinstance(self.awg, AWG5208):
                # forge the sequence
                forged_sequence = seq.forge()

                # create a sequence file
                seqx_file = self.awg.make_SEQX_from_forged_sequence(
                    forged_sequence, [1 for i in self.chan_map.keys()], seq.name)
                seqx_file_name = f'{seq.name}.seqx'

                # clear lists of sequences and waveforms on the instrument in order
                # to prevent cluttering
                self.awg.clearSequenceList()
                self.awg.clearWaveformList()

                # send the sequence file to the instrument and load it
                self.awg.sendSEQXFile(seqx_file, filename=seqx_file_name)
                self.awg.loadSEQXFile(seqx_file_name)

                self.awg.sample_rate(self.SR)

                # load seqs to channels
                for ch_no, ch_desc in self.chan_map.items():
                    chan = self.awg.channels[ch_no-1]

                    track_number = 1
                    chan.setSequenceTrack(seq.name, track_number)

                    chan.resolution(12)
                    chan.set('state', 1)

                for ch_no, ch_set in self.chan_settings.items():
                    self.awg.channels[ch_no-1].set('awg_amplitude', ch_set['Vpp'])
                    for i in range(1, len(ch_set['marker_hi'])+1):
                        self.awg.channels[ch_no-1].set('marker{}_high'.format(i), ch_set['marker_hi'][i-1])
                        self.awg.channels[ch_no-1].set('marker{}_low'.format(i), ch_set['marker_lo'][i-1])

            
        if start_awg:
            if isinstance(self.awg, AWG5014):
                self.awg.start()
            elif isinstance(self.awg, AWG5208):
                self.awg.play()


