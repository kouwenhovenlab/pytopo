import numpy
import pytest

from pytopo.sweep import setter, getter, sweep, measure
from pytopo.sweep.decorators import SweepFunction


def test_setter_with_2_numeric_paramtype():
    """
    ...

    Assuming the setter function has some logic that needs both set point
    values at the same time for some reason...

    This works as expected.
    """
    @getter(('luck', '#', 'numeric'))
    def luck_param():
        return 1

    n_pts = 7
    magn_vals = numpy.random.rand(n_pts)
    phas_vals = numpy.random.rand(n_pts)

    @setter(("magn", "V"), ("phas", "deg"))
    def dummy_setter(m_val, p_val):
        pass

    assert isinstance(dummy_setter, SweepFunction)

    table = dummy_setter.parameter_table
    assert table.nests == [["magn", "phas"]]

    spec_magn, spec_phas = table.param_specs
    assert spec_magn.name == "magn"
    assert spec_magn.unit == "V"
    assert spec_magn.type == "numeric"
    assert spec_phas.name == "phas"
    assert spec_phas.unit == "deg"
    assert spec_phas.type == "numeric"

    # notice the `zip` of lists in the `sweep` call
    so = sweep(dummy_setter, zip(magn_vals, phas_vals))(
        measure(luck_param)
    )

    sweep_output = list(so)

    assert isinstance(sweep_output, list)
    expected_output = [{'luck': 1, 'magn': m_val, 'phas': p_val}
                       for m_val, p_val in zip(magn_vals, phas_vals)
                       ]
    assert sweep_output == expected_output


def test_getter_with_2_array_paramtype():
    """
    ...

    Assuming the setter function has some logic that needs both set point
    values at the same time for some reason...

    This works as expected.
    """
    @getter(('luck', '#', 'numeric'))
    def luck_param():
        return 1

    n_pts = 7
    magn_vals = numpy.random.rand(n_pts)
    phas_vals = numpy.random.rand(n_pts)

    @setter(("magn", "V", "array"), ("phas", "deg", "array"))
    def dummy_setter(m_vals, p_vals):
        pass

    assert isinstance(dummy_setter, SweepFunction)

    table = dummy_setter.parameter_table
    assert table.nests == [["magn", "phas"]]

    spec_magn, spec_phas = table.param_specs
    assert spec_magn.name == "magn"
    assert spec_magn.unit == "V"
    assert spec_magn.type == "array"
    assert spec_phas.name == "phas"
    assert spec_phas.unit == "deg"
    assert spec_phas.type == "array"

    # notice the list of lists in the `sweep` call
    so = sweep(dummy_setter, [[magn_vals, phas_vals]])(
        measure(luck_param)
    )

    sweep_output = list(so)

    assert isinstance(sweep_output, list)
    assert 1 == len(sweep_output)
    assert {'luck', 'magn', 'phas'} == set(sweep_output[0].keys())
    assert 1 == sweep_output[0]['luck']
    assert numpy.allclose(magn_vals, sweep_output[0]['magn'])
    assert numpy.allclose(phas_vals, sweep_output[0]['phas'])


def test_getter_with_1_array_and_1_numeric_paramtype():
    """
    This situation is indeed weird, because it is supposed to be achieved
    with two setters - a zip (?) of one setter with numeric paramtype,
    and another one with array paramtype.

    Due to the implementation of the setter and some other classes (Sweep,
    IteratorSweep), this case will not work (see the caught exception)
    """
    @getter(('luck', '#', 'numeric'))
    def luck_param():
        return 1

    n_pts = 7
    phas_vals = numpy.random.rand(n_pts)
    magn_val = 42

    @setter(("magn", "V"), ("phas", "deg", "array"))
    def dummy_setter(magn_val, phas_vals):
        pass

    assert isinstance(dummy_setter, SweepFunction)

    table = dummy_setter.parameter_table
    assert table.nests == [["magn", "phas"]]

    spec_magn, spec_phas = table.param_specs
    assert spec_magn.name == "magn"
    assert spec_magn.unit == "V"
    assert spec_magn.type == "numeric"
    assert spec_phas.name == "phas"
    assert spec_phas.unit == "deg"
    assert spec_phas.type == "array"

    # the exception originates from `numpy.atleast_1d` call in `Sweep` class
    # that is used by `setter` through `IteratorSweep`
    with pytest.raises(ValueError, match="setting an array element with a "
                                         "sequence."):
        so = sweep(dummy_setter, [[magn_val, phas_vals]])(
            measure(luck_param)
        )

        sweep_output = list(so)

        assert isinstance(sweep_output, list)
        assert 1 == len(sweep_output)
        assert magn_val == sweep_output[0]['magn']
        assert 1 == sweep_output[0]['luck']
        assert numpy.allclose(sweep_output[0]['phas'], phas_vals)
