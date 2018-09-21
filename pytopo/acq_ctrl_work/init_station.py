from importlib import reload

import qcodes as qc
import broadbean as bb
from pytopo.qctools import instruments as instools
from pytopo.qctools.instruments import create_inst, add2station

def init_instruments():
    inst_list = []

    # Create all instruments
    from qcodes.instrument_drivers.AlazarTech import utils
    from pytopo.instrument_drivers.ATS9373 import AlazarTech_ATS9373
    alazar = instools.create_inst(AlazarTech_ATS9373, 'alazar', force_new_instance=True)
    inst_list.append(alazar)
    
    from qcodes.instrument_drivers.tektronix.AWG5208 import AWG5208
    awg5208_1 = instools.create_inst(
        AWG5208, 'awg5208_1', 
        address='TCPIP0::169.254.200.177::inst0::INSTR',
        force_new_instance=True)
    inst_list.append(awg5208_1)

    from pytopo.rf.alazar_acquisition import (
        RawAcqCtl, AvgBufCtl, AvgDemodCtl, AvgIQCtl, 
        AvgRecCtl, AvgRecDemodCtl, AvgRecIQCtl
        )
    
    raw_acq = instools.create_inst(RawAcqCtl, 'raw_acq', 'alazar', force_new_instance=True)
    inst_list.append(raw_acq)

    station = qc.Station(*inst_list)

    # some reasonable defaults for all instruments
    # TBD

    return station


def setup_alazar_ext_trigger(nsamples, nrecords, nbuffers, 
                             allocated_buffers=1, 
                             SR=2e8, int_time=None):
    
    alazar = qc.Instrument.find_instrument('alazar')
    
    SR = int(SR)
    if int_time is not None:
        SPR = int(int_time * SR // 128 * 128)
    else: 
        SPR = nsamples
    
    with alazar.syncing():
        alazar.clock_source('INTERNAL_CLOCK')
        alazar.clock_edge('CLOCK_EDGE_RISING')
        alazar.decimation(1)
        alazar.coupling1('DC')
        alazar.coupling2('DC')
        alazar.channel_range1(0.4)
        alazar.channel_range2(0.4)
        alazar.impedance1(50)
        alazar.impedance2(50)
        alazar.trigger_source1('EXTERNAL')
        alazar.trigger_level1(128 + 5)
        alazar.external_trigger_coupling('DC')
        alazar.external_trigger_range('ETR_TTL')
        alazar.trigger_delay(0)
        alazar.timeout_ticks(int(1e7))
        alazar.buffer_timeout(10000)

        alazar.sample_rate(SR)
        alazar.records_per_buffer(nrecords)
        alazar.buffers_per_acquisition(nbuffers)
        alazar.samples_per_record(SPR)
        alazar.allocated_buffers(allocated_buffers)


if __name__ == '__main__':
    qc.config['core']['db_location'] = r"C:\Users\Administrator\OneDrive\TestSetup\Data\experiments.db"
    station = init_instruments()
