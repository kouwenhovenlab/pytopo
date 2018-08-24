from pytopo.pinmap.devices import Device
from pytopo.pinmap.transformations import nest_transformation


def connect_pins(of: Device, to: Device, using_map: dict):
    of_pins_from_map = list(using_map.keys())
    to_pins_from_map = list(using_map.values())

    of_pin_labels = [pin.label for pin in of.pins]
    if not all(of_pin in of_pin_labels for of_pin in of_pins_from_map):
        raise Exception(f'Not all {of_pins_from_map!r} are in device {of!s}')

    to_pin_labels = [pin.label for pin in to.pins]
    if not all(to_pin in to_pin_labels for to_pin in to_pins_from_map):
        raise Exception(f'Not all {of_pins_from_map!r} are in device {of!s}')

    for of_pin, to_pin in using_map.items():
        of.pin_by_label(of_pin).transformation = nest_transformation(
            this=to.pin_by_label(to_pin).transformation,
            into=of.pin_by_label(of_pin).transformation
        )

    print('done!')
