from pytopo.pinmap.connect import connect_pins
from pytopo.pinmap.devices import Device, Chip, Daughterboard
from pytopo.pinmap.transformations import AddOneTransformation


def test_1():
    qubit = Device('qubit')
    qubit.add_pin('source', '1')
    qubit.add_pin('drain', '2')
    qubit.add_pin('cutter', '3')

    majorana = Device('majorana')
    majorana.add_pin('source', '21')
    majorana.add_pin('drain', '22')
    majorana.add_pin('plunger', '33')

    chip = Chip('chip-1255GHER')
    chip.add_device(qubit)
    chip.add_device(majorana)

    # print(chip)

    daughter = Daughterboard('daughter-D123')
    for i in range(8):
        daughter.add_pin(f'p{i+1}', f'{i+1}',
                         transformation=AddOneTransformation)

    # print(daughter)

    # TODO: this does not seem to be the behavior of Parameter that I want
    daughter.p5(25)
    assert 25 == daughter.p5()
    assert 25 == daughter.p5.get_latest()
    assert 24 == daughter.p5.raw_value
    assert 25 == daughter.p5._latest['value']
    assert 24 == daughter.p5._latest['raw_value']

    chip_to_daughter = {
        '1': '1',
        '22': '3',
        '3': '5'
    }

    connect_pins(of=chip, to=daughter, using_map=chip_to_daughter)

    assert 1 == chip.qubit.cutter()
    assert 1 == chip.qubit.source()
    assert 0 == chip.qubit.drain()

    # for p in daughter.pins:
    #     print(f'{p.name} ({p.label}) = {p()}')

    assert daughter.p5() - 1 == chip.qubit.cutter()


