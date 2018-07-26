from qcodes.instrument.base import Instrument

class HeterodyneSource(Instrument):
    """
    Meta instrument to controll a heterodyne setup based on two
    generators. Instead of controlling RF and LO, we control
    RF and IF frequencies. 
    Setting RF and IF will set the LO automatically (LO = RF - IF).
    Assumes that RF and LO have a parameter 'frequency', given in Hz.
    """
    
    def __init__(self, name, RF, LO, *arg, **kw):
        super().__init__(name, *arg, **kw)
        
        self.RF = RF
        self.LO = LO
        
        self.add_parameter('IF', set_cmd=None, initial_value=20e6)
        self.add_parameter('frequency', unit='Hz',
                           get_cmd=self.RF.frequency, 
                           set_cmd=self._set_freq)
        
        self.frequency(self.frequency())
    
    def _set_freq(self, frq):
        self.RF.frequency(frq)
        self.LO.frequency(frq-self.IF())
