import numpy
import pytest

from pytopo.sweep import setter, getter, sweep, measure
from pytopo.sweep.decorators import MeasureFunction


def test_getter_with_2_numeric_paramtype():
    @setter(('repetition', '#', 'numeric'))
    def repetition_param(repetition):
        """
        The purpose of this setter is to simulate a qcodes parameter without
        the need of importing it
        """
        pass

    n_pts = 7
    rep_vals = list(range(n_pts))
    magn_vals = numpy.random.rand(n_pts)
    magn_vals_iter = iter(magn_vals)
    phas_vals = numpy.random.rand(n_pts)
    phas_vals_iter = iter(phas_vals)

    @getter(("magn", "V"), ("phas", "deg"))
    def alazar_output():
        return next(magn_vals_iter), next(phas_vals_iter)

    assert isinstance(alazar_output, MeasureFunction)

    table = alazar_output.parameter_table
    assert table.nests == [["magn"], ["phas"]]

    spec_magn, spec_phas = table.param_specs
    assert spec_magn.name == "magn"
    assert spec_magn.unit == "V"
    assert spec_magn.type == "numeric"
    assert spec_phas.name == "phas"
    assert spec_phas.unit == "deg"
    assert spec_phas.type == "numeric"

    so = sweep(repetition_param, rep_vals)(
        measure(alazar_output)
    )

    sweep_output = list(so)

    assert isinstance(sweep_output, list)
    expected_output = [{'repetition': r_val, 'magn': m_val, 'phas': p_val}
                       for r_val, m_val, p_val
                       in zip(rep_vals, magn_vals, phas_vals)]
    assert sweep_output == expected_output


def test_getter_with_2_array_paramtype():
    @setter(('repetition', '#', 'numeric'))
    def repetition_param(repetition):
        """
        The purpose of this setter is to simulate a qcodes parameter without
        the need of importing it
        """
        pass

    n_pts = 7
    magn_vals = numpy.random.rand(n_pts)
    phas_vals = numpy.random.rand(n_pts)

    @getter(("magn", "V", "array"), ("phas", "deg", "array"))
    def alazar_output():
        return magn_vals, phas_vals

    assert isinstance(alazar_output, MeasureFunction)

    table = alazar_output.parameter_table
    assert table.nests == [["magn"], ["phas"]]

    spec_magn, spec_phas = table.param_specs
    assert spec_magn.name == "magn"
    assert spec_magn.unit == "V"
    assert spec_magn.type == "array"
    assert spec_phas.name == "phas"
    assert spec_phas.unit == "deg"
    assert spec_phas.type == "array"

    so = sweep(repetition_param, [1])(
        measure(alazar_output)
    )

    sweep_output = list(so)

    assert isinstance(sweep_output, list)
    assert 1 == len(sweep_output)
    assert {'repetition', 'magn', 'phas'} == set(sweep_output[0].keys())
    assert 1 == sweep_output[0]['repetition']
    assert numpy.allclose(magn_vals, sweep_output[0]['magn'])
    assert numpy.allclose(phas_vals, sweep_output[0]['phas'])


def test_getter_with_1_array_and_1_numeric_paramtype():
    """
    This situation is indeed weird, because it is supposed to be achieved
    with two getters - a chain of one getter with numeric paramtype,
    and another one with array paramtype.

    Due to the implementation of the getter, this case will not work (see the
    caught exception)
    """
    @setter(('repetition', '#', 'numeric'))
    def repetition_param(repetition):
        """
        The purpose of this setter is to simulate a qcodes parameter without
        the need of importing it
        """
        pass

    n_pts = 7
    phas_vals = numpy.random.rand(n_pts)
    magn_val = 42

    @getter(("magn", "V"), ("phas", "deg", "array"))
    def alazar_output():
        return magn_val, phas_vals

    assert isinstance(alazar_output, MeasureFunction)

    table = alazar_output.parameter_table
    assert table.nests == [["magn"], ["phas"]]

    spec_magn, spec_phas = table.param_specs
    assert spec_magn.name == "magn"
    assert spec_magn.unit == "V"
    assert spec_magn.type == "numeric"
    assert spec_phas.name == "phas"
    assert spec_phas.unit == "deg"
    assert spec_phas.type == "array"

    # the exception originates from `numpy.atleast_1d` call in `getter`
    with pytest.raises(ValueError, match="setting an array element with a "
                                         "sequence."):
        so = sweep(repetition_param, [1])(
            measure(alazar_output)
        )

        sweep_output = list(so)

        assert isinstance(sweep_output, list)
        assert 1 == len(sweep_output)
        assert magn_val == sweep_output[0]['magn']
        assert 1 == sweep_output[0]['repetition']
        assert numpy.allclose(sweep_output[0]['phas'], phas_vals)
