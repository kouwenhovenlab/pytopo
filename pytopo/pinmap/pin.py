from functools import partial

from qcodes.instrument.parameter import Parameter
# from qcodes.instrument.parameter import _BaseParameter
from pytopo.pinmap.transformations import UnityTransformation


class Pin(Parameter):
    """
    This class represents a pin or an electrode.

    It has a label that users can refer to when
    creating connections between pins.

    It also has a transformation that defines what
    happens with the values that are passed thorugh this pin.

    TODO:
    * snapshot
    * create properties for useful parts
    * QCODES Parameter-like?
    """

    def __init__(self, name, label, transformation=UnityTransformation,
                 **kwargs):
        self.transformation = transformation

        super().__init__(name,
                         get_cmd=None, set_cmd=None,
                         get_parser=partial(self.transformation.forward,
                                            self.transformation),
                         set_parser=partial(self.transformation.backward,
                                            self.transformation),
                         **kwargs)

        self.label = label  # override Parameter's label...

        self.set(0)

    def __repr__(self):
        return f'Pin {self.name!r} - {self.label!r}'
