from qcodes.instrument.base import Instrument
from .parameters import ConversionParameter

class IVVISetup(Instrument):

    def __init__(self, name, ivvi, **kw):
        super().__init__(name, **kw)
        self.ivvi = ivvi

    @staticmethod
    def corrected_bias(current, bias, series_resistance=0):
        return bias - current * series_resistance

    @staticmethod
    def corrected_dIdV(lockin_signal, lockin_dV, current_gain=1):
        return lockin_signal / (lockin_dV) / current_gain

    @staticmethod
    def amppervolt_to_2e2perh(val):
        return val / 7.7481e-5

    def add_dac_voltage_src(self, name, dac_number, multiplier=1):
        self.add_parameter(name + '_voltage', unit='V',
                           parameter_class=ConversionParameter,
                           src_param=getattr(self.ivvi, 'dac{}'.format(dac_number)),
                           get_conv=lambda x: x*(multiplier * 1e-3),
                           set_conv=lambda x: x/(multiplier * 1e-3))

    def add_voltage_src(self, name, param, multiplier=1):
        self.add_parameter(name + '_voltage', unit='V',
                           parameter_class=ConversionParameter,
                           src_param=param,
                           get_conv=lambda x: x*(multiplier),
                           set_conv=lambda x: x/(multiplier))

    def add_current_meas(self, name, voltage_param, gain=1):
        self.add_parameter(name + '_current', unit='A',
                           parameter_class=ConversionParameter,
                           src_param=voltage_param,
                           get_conv=lambda x: x/gain)

    def add_conductance_meas(self, name, param, gain=1, r_series=1e3, lockin_dV=10e-6):
        self.add_parameter(name + '_conductance', unit='2e2/h',
                           parameter_class=ConversionParameter,
                           src_param=param,
                           get_conv=lambda x: 12906/((gain*lockin_dV/x)-r_series))