from qcodes import Instrument, Parameter, InstrumentChannel
from qcodes.utils.validators import (Enum, Numbers, Bool, PermissiveMultiples, 
                                     MultiTypeAnd)
from typing import Any, Literal
from spirack import D5c_module
from functools import partial

NUM_DACS = 8
DAC_RAMP_TIME_MULTIPLE = 5e-6
TOGGLE_TIME_MULTIPLE = 100e-9
MIN_TOGGLE_TIME = 5e-6
HOLDOFF_TIME_MULTIPLE = 100e-9
MIN_HOLDOFF_TIME = 30e-6

COARSE_RATIO = 1.052631
FINE_RATIO = 20

class D5c_DAC(InstrumentChannel):
    """
    TODO: INSERT DOCSTRING.

    TODO: APPARENTLY LATER THE D5C WILL BE COMPATIBLE WITH ANY RAMP TIME
    LARGER THAN 5us AND WHICH IS A MULTIPLE OF 100ns, IMPLEMENT THIS WHEN
    THAT IS THE CASE
    """

    def __init__(self, parent_instrument, name, d5c_module, dac,
                 reset_voltages=False, update_dac=True, mode=None, span=None,
                 **kwargs):
        super().__init__(parent_instrument, name, **kwargs)

        self.d5c = d5c_module
        self._dac = dac

        self.add_parameter('update',
                           docstring=("Whether or not to update span/voltage"
                                      "immediately when setting it, or later"
                                      " with the next span/value update."),
                           get_cmd=None,
                           set_cmd=None,
                           vals=Bool(),
                           initial_value=update_dac)
        self.add_parameter('span',
                           get_cmd=lambda: self.d5c.get_DAC_span(self._dac),
                           set_cmd=lambda v: self.d5c.set_DAC_span(self._dac, v, 
                                                                   update=self.update()),
                           vals=Enum('4V_uni', '8V_uni','4V_bi', '8V_bi', 
                                       '2V_bi'))
        self.add_parameter('mode',
                           get_cmd=lambda: self.d5c.get_DAC_mode(i),
                           set_cmd=lambda v: self.d5c.set_DAC_mode(self._dac, v),
                           vals=Enum('DC', 'toggle', 'single', 'repeated'))
        self.add_parameter('voltage',
                           get_cmd=lambda: self.d5c.get_DAC_voltages(self._dac)[0],
                           set_cmd=lambda v: set_DAC_voltage(self._dac, v, 
                                                             update=self.update()),
                           unit='V')
        self.add_parameter('pos_toggle_voltage',
                           get_cmd=lambda: self.d5c.get_DAC_voltages(self._dac)[2],
                           set_cmd=lambda v: self.d5c.set_DAC_pos_toggle_voltage(self._dac, v),
                           unit='V')
        self.add_parameter('neg_toggle_voltage',
                           get_cmd=lambda: self.d5c.get_DAC_voltages(self._dac)[1],
                           set_cmd=lambda v: self.d5c.set_DAC_neg_toggle_voltage(self._dac, v),
                           unit='V')
        self.add_parameter('ramp_time',
                           get_cmd=lambda: self.d5c.get_DAC_ramp_time(self._dac),
                           set_cmd=lambda v: self.d5c.set_DAC_ramp_time_in_seconds(self._dac, v),
                           vals=MultiTypeAnd(PermissiveMultiples(divisor=DAC_RAMP_TIME_MULTIPLE),
                                             Numbers(min_value=DAC_RAMP_TIME_MULTIPLE)),
                           unit='s')
        if mode is not None:
            self.mode(mode)
        if span is not None:
            self.span(span)


class D5c_OUTPUT(InstrumentChannel):
    """
    TODO: INSERT DOCSTRING.

    THIS CLASS REPRESENTS AN OUTPUT, WITH COARSE AND FINE DAC ABSTRACTED AWAy
    """

    def __init__(self, parent_instrument, name, d5c_module, output, mode=None, span=None,
                 **kwargs):
        super().__init__(parent_instrument, name, **kwargs)

        self.d5c = d5c_module
        self._dac_coarse = (output-1)*2+1
        self._dac_fine = (output-1)*2
        self.add_parameter('span',
                           get_cmd=lambda: self.d5c.get_DAC_span(self._dac),
                           set_cmd=lambda v: self.d5c.set_DAC_span(self._dac, v, 
                                                                   update=self.update()),
                           vals=Enum('4V_uni', '8V_uni','4V_bi', '8V_bi', 
                                       '2V_bi'))
        self.add_parameter('mode',
                           get_cmd=lambda: self.d5c.get_DAC_mode(i),
                           set_cmd=lambda v: self.d5c.set_DAC_mode(self._dac, v),
                           vals=Enum('DC', 'toggle', 'single', 'repeated'))
        self.add_parameter('voltage',
                           get_cmd=lambda: self.d5c.get_DAC_voltages(self._dac)[0],
                           set_cmd=lambda v: set_DAC_voltage(self._dac, v, 
                                                             update=self.update()),
                           unit='V')
        self.add_parameter('ramp_time',
                           get_cmd=lambda: self.d5c.get_DAC_ramp_time(self._dac),
                           set_cmd=lambda v: self.d5c.set_DAC_ramp_time_in_seconds(self._dac, v),
                           vals=MultiTypeAnd(PermissiveMultiples(divisor=DAC_RAMP_TIME_MULTIPLE),
                                             Numbers(min_value=DAC_RAMP_TIME_MULTIPLE)),
                           unit='s')
        if mode is not None:
            self.mode(mode)
        if span is not None:
            self.span(span)


class D5c(Instrument):
    """
    dacs 0, 1, 2, 3: waveform outputs
    dacs 0 & 2: fine ramp dacs
    dacs 4, 5, 6, 7: trigger outputs
    TODO: INSERT DOCSTRING.

    # TODO: ADJUST DAC NAMES AND CONFIGURATIONS TO ACCOUNT FOR PECULIARITIES
        OF EACH DAC: SOME ARE TRIGGERS, SOME ARE FOR RAMPING, ETC
    """

    def __init__(self, name, spi_rack, module, 
                 reset_voltages=False, # BE VERY SURE THAT YOU WANT TO CHANGE THIS
                 dacs_to_initialize=[0, 1, 2, 3, 4, 5, 6, 7],
                 update_dacs=True,
                 **kwargs):
        super().__init__(name, **kwargs)

        self.d5c = D5c_module(spi_rack, module, reset_voltages=reset_voltages)

        # [FKM] do we want this here?
        # All 8 channels are not supposed to be directly user-accessible
        for i in dacs_to_initialize:
            self.add_submodule(f'dac{i}',
                               D5c_DAC(self,
                                       f'dac{i}', 
                                       self.d5c, i, 
                                       reset_voltages=reset_voltages, 
                                       update_dac=update_dacs),
                               **kwargs)
        # [FKM] instead I suggest two "outputs" that are abstracted away
        # from dacs, and include appropriate hardware addition



        self.add_parameter('clock_source', 
                           get_cmd=self.d5c.get_clock_source,
                           set_cmd=self.d5c.set_clock_source,
                           vals=Enum('internal', 'external'))
        self.add_parameter('start_holdoff_time',
                           get_cmd=self.d5c.get_start_holdoff_time,
                           set_cmd=self.d5c.set_start_holdoff_time,
                           unit='s',
                           vals=MultiTypeAnd(PermissiveMultiples(divisor=HOLDOFF_TIME_MULTIPLE),
                                             Numbers(min_value=MIN_HOLDOFF_TIME)))
        self.add_parameter('toggle_amount',
                           get_cmd=self.d5c.get_toggle_amount,
                           set_cmd=self.d5c.set_toggle_amount,
                           unit='',
                           vals=MultiTypeAnd(PermissiveMultiples(divisor=2),
                                             Numbers(min_value=0)))
        self.add_parameter('toggle_time',
                           get_cmd=self.d5c.get_toggle_time_in_seconds,
                           set_cmd=self.d5c.set_toggle_time,
                           unit='s',
                           vals=MultiTypeAnd(PermissiveMultiples(divisor=TOGGLE_TIME_MULTIPLE),
                                             Numbers(min_value=MIN_TOGGLE_TIME)))
        self.add_parameter('synchronization_mode',
                           get_cmd=lambda: self.d5c._synch_mode,
                           set_cmd=self.d5c.configure_synchronization,
                           vals=Enum('none', 'user', 'auto'),
                           initial_value='user')

    @property
    def dacs(self):
        return tuple(subm 
                     for subm in self.submodules.values() 
                     if isinstance(subm, D5c_DAC))

    @property
    def dac_voltages(self):
        return tuple(d.voltage() for d in self.dacs)

    def print_dac_voltages(self):
        for i, v in enumerate(self.dac_voltages):
            print(f"DAC{i}: {v} V")
    

    def get_run_time(self):
        """Wrapper for self.d5c.get_run_time_in_seconds()"""
        return self.d5c.get_run_time_in_seconds()

    def reset_run(self):
        """Wrapper for self.d5c.reset_run()"""
        self.d5c.reset_run()

    def is_running(self): 
        """Wrapper for self.d5c.is_running()"""
        return self.d5c.is_running()

    def software_start(self):
        """Wrapper for self.d5c.software_start()"""
        self.d5c.software_start()

