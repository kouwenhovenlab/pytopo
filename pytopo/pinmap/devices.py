from qcodes.instrument.base import InstrumentBase

# probably should be some sort of generic class of 'SmthWithPins'
from pytopo.pinmap.pin import Pin
from pytopo.pinmap.transformations import UnityTransformation


class Device(InstrumentBase):
    """
    The device represents one device on a chip/die.

    It contains pins. They are accessible as attributes.

    TODO:
    * adding pins
    * snapshot
    * properties?
    * make loadable/creatable from yaml file
    """

    def __init__(self, name):
        super().__init__(name)

    def add_pin(self, name, label, transformation=UnityTransformation):
        self.add_parameter(name, label=label, transformation=transformation,
                           parameter_class=Pin)

    def pin_by_label(self, pin_label):
        pins_with_this_label = [p for p in self.pins if p.label == pin_label]
        if len(pins_with_this_label) != 1:
            raise KeyError(
                f'More than one pin found with label {pin_label!r}: {pins_with_this_label!r}')
        return pins_with_this_label[0]

    @property
    def pins(self):
        return [getattr(self, p) for p in self.parameters if
                isinstance(getattr(self, p), Pin)]

    def __repr__(self):
        str_ = f'Device {self.name!r}\n'
        str_ += '\n'.join([f'{p!r}' for p in self.pins])
        return str_


class Chip(InstrumentBase):
    """
    Just comprises one or more devices, nothing more.

    TODO:
    * properties?
    * should pins of devices be directly accessible or only via devices attributes?
    * seems like chip needs some smart method of forwarding "conneciton" to device's pins...
    * make loadable/creatable from yaml file
    * snapshot
    """

    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)

    #         self.name = name

    def add_device(self, device, device_name=None):
        if not isinstance(device, Device):
            raise ValueError(
                'Device has to be of class "Device", but it is {device.__class__!r}')
        if not device_name:
            device_name = device.name
        self.add_submodule(device_name, device)

    @property
    def pins(self):
        return [pin
                for device in self.devices
                for pin in device.pins
                ]

    def pin_by_label(self, pin_label):
        pins_with_this_label = [p for p in self.pins if p.label == pin_label]
        if len(pins_with_this_label) != 1:
            raise KeyError(
                f'More than one pin found with label {pin_label!r}: {pins_with_this_label!r}')
        return pins_with_this_label[0]

    @property
    def devices(self):
        return [getattr(self, d) for d in self.submodules if
                isinstance(getattr(self, d), Device)]

    def __repr__(self):
        str_ = f'Chip {self.name!r}\n'
        str_ += '\n'.join([f'{d!r}' for d in self.devices])
        return str_


Daughterboard = Device
Motherboard = Device
Fridge = Device
BreakoutBox = Device
# TODO: what for the case of MDAC? a wrapper?
# TODO: viasualization of all connections