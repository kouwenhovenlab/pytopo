from qcodes.instrument.parameter import Parameter

class ConversionParameter(Parameter):

    def __init__(self, name, src_param, get_conv, set_conv=None, **kw):
        super().__init__(name, **kw)
        self.src_param = src_param
        self.get_conv = get_conv
        self.set_conv = set_conv

    def get_raw(self):
        return self.get_conv(self.src_param())

    def set_raw(self, value):
        if self.set_conv is None:
            raise NotImplementedError("No set conversion implemented.")

        return self.src_param(self.set_conv(value))
