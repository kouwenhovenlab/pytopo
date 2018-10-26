import time

from qcodes.instrument_drivers.tektronix.AWG5014 import Tektronix_AWG5014
from qcodes.instrument_drivers.tektronix.AWG5208 import AWG5208

def trigger_awg_when_ready(awg):
    """
    AWG-model independent trigger. waits until the AWG is ready to receive a trigger.
    """
    if isinstance(awg, AWG5208):
        while awg.run_state() != 'Waiting for trigger':
            time.sleep(0.01)
        awg.force_triggerA()
    else:
        while awg.get_state() != 'Waiting for trigger':
            time.sleep(0.01)
        awg.force_trigger()
    
    return True