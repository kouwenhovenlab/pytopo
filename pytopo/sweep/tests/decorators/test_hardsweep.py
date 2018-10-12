import numpy
import pytest

from pytopo.sweep.base import IteratorSweep
from pytopo.sweep.decorators import hardsweep, setter, getter
from pytopo.sweep.convenience import sweep, measure


def test_hardsweep():
    """
    Test hardsweep decorator and the properties of the created sweep object
    """
    @hardsweep(ind=[("time", "us"), ("space", "m", "array")],
               dep=[("magn", "V")])
    def measure_with_alazar():
        pass

    hardsweep_sweep_object = measure_with_alazar()

    assert isinstance(hardsweep_sweep_object, IteratorSweep)
    assert True == hardsweep_sweep_object.measurable

    table = hardsweep_sweep_object.parameter_table
    assert table.nests == [["time", "space", "magn"]]

    time_spec, space_spec, magn_spec = table.param_specs
    assert time_spec.name == "time"
    assert time_spec.unit == "us"
    assert time_spec.type == "numeric"
    assert space_spec.name == "space"
    assert space_spec.unit == "m"
    assert space_spec.type == "array"
    assert magn_spec.name == "magn"
    assert magn_spec.unit == "V"
    assert magn_spec.type == "numeric"


def test_hardsweep_with_1_ind_numeric_and_1_dep_numeric():
    """
    ...

    This works as expected.
    """
    @setter(('repetition', '#', 'numeric'))
    def repetition_param(repetition):
        """
        The purpose of this setter is to simulate a qcodes parameter without
        the need of importing it
        """
        pass

    n_pts = 7
    time_vals = numpy.random.rand(n_pts)
    magn_vals = numpy.random.rand(n_pts)

    @hardsweep(ind=[("time", "us")],
               dep=[("magn", "V")])
    def measure_with_alazar():
        return time_vals, magn_vals

    so = sweep(repetition_param, [1])(
        measure_with_alazar()
    )

    sweep_output = list(so)

    assert isinstance(sweep_output, list)
    assert n_pts == len(sweep_output)
    expected_output = [{'repetition': 1, 'magn': m_val, 'time': t_val}
                       for t_val, m_val in zip(time_vals, magn_vals)]
    assert expected_output == sweep_output


def test_hardsweep_with_1_ind_array_and_1_dep_array():
    """
    ...

    This works as expected.
    """
    @setter(('repetition', '#', 'numeric'))
    def repetition_param(repetition):
        """
        The purpose of this setter is to simulate a qcodes parameter without
        the need of importing it
        """
        pass

    n_pts = 7
    time_vals = numpy.random.rand(n_pts)
    magn_vals = numpy.random.rand(n_pts)

    @hardsweep(ind=[("time", "us", "array")],
               dep=[("magn", "V", "array")])
    def measure_with_alazar():
        return time_vals, magn_vals

    so = sweep(repetition_param, [1])(
        measure_with_alazar()
    )

    sweep_output = list(so)

    assert isinstance(sweep_output, list)
    assert 1 == len(sweep_output)
    assert {'repetition', 'time', 'magn'} == set(sweep_output[0].keys())
    assert 1 == sweep_output[0]['repetition']
    assert numpy.allclose(magn_vals, sweep_output[0]['magn'])
    assert numpy.allclose(time_vals, sweep_output[0]['time'])


def test_hardsweep_with_1_ind_numeric_and_1_dep_array():
    """
    ...

    This works as expected
    """
    @setter(('repetition', '#', 'numeric'))
    def repetition_param(repetition):
        pass

    n_pts = 7
    time_val = 42
    magn_vals = numpy.random.rand(n_pts)

    @hardsweep(ind=[("time", "us")],  # 'numeric'
               dep=[("magn", "V", "array")])
    def measure_with_alazar():
        return time_val, magn_vals

    so = sweep(repetition_param, [1])(
        measure_with_alazar()
    )

    sweep_output = list(so)

    assert isinstance(sweep_output, list)
    assert 1 == len(sweep_output)
    assert 1 == sweep_output[0]['repetition']
    assert numpy.allclose(magn_vals, sweep_output[0]['magn'])
    assert time_val == sweep_output[0]['time']


def test_hardsweep_with_1_ind_array_and_1_dep_numeric():
    """
    ...

    This works as expected.
    """
    @setter(('repetition', '#', 'numeric'))
    def repetition_param(repetition):
        """
        The purpose of this setter is to simulate a qcodes parameter without
        the need of importing it
        """
        pass

    n_pts = 7
    time_vals = numpy.random.rand(n_pts)
    magn_val = 32

    @hardsweep(ind=[("time", "us", "array")],
               dep=[("magn", "V")])  # 'numeric'
    def measure_with_alazar():
        return time_vals, magn_val

    so = sweep(repetition_param, [1])(
        measure_with_alazar()
    )

    sweep_output = list(so)

    assert isinstance(sweep_output, list)
    assert 1 == len(sweep_output)
    assert 1 == sweep_output[0]['repetition']
    assert numpy.allclose(time_vals, sweep_output[0]['time'])
    assert magn_val == sweep_output[0]['magn']


def test_hardsweep_with_2_ind_array_and_2_dep_array():
    """
    ...

    This works as expected
    """
    @setter(('repetition', '#', 'numeric'))
    def repetition_param(repetition):
        pass

    n_pts = 7
    time_vals = numpy.random.rand(n_pts)
    space_vals = numpy.random.rand(n_pts)
    magn_vals = numpy.random.rand(n_pts)
    phas_vals = numpy.random.rand(n_pts)

    @hardsweep(ind=[("time", "us", "array"), ("space", "nm", "array")],
               dep=[("magn", "V", "array"), ("phas", "V", "array")])
    def measure_with_alazar():
        ind_vals = numpy.vstack((time_vals, space_vals))
        dep_vals = numpy.vstack((magn_vals, phas_vals))
        return ind_vals, dep_vals

    so = sweep(repetition_param, [1])(
        measure_with_alazar()
    )

    sweep_output = list(so)

    assert isinstance(sweep_output, list)
    assert 1 == len(sweep_output)
    assert {'repetition', 'time', 'magn', 'phas', 'space'} \
           == set(sweep_output[0].keys())
    assert 1 == sweep_output[0]['repetition']
    assert numpy.allclose(magn_vals, sweep_output[0]['magn'])
    assert numpy.allclose(phas_vals, sweep_output[0]['phas'])
    assert numpy.allclose(space_vals, sweep_output[0]['space'])
    assert numpy.allclose(time_vals, sweep_output[0]['time'])


def test_hardsweep_with_2_ind_numeric_and_2_dep_numeric():
    """
    ...

    This works as expected
    """
    @setter(('repetition', '#', 'numeric'))
    def repetition_param(repetition):
        pass

    n_pts = 7
    time_vals = numpy.random.rand(n_pts)
    space_vals = numpy.random.rand(n_pts)
    magn_vals = numpy.random.rand(n_pts)
    phas_vals = numpy.random.rand(n_pts)

    @hardsweep(ind=[("time", "us"), ("space", "nm")],
               dep=[("magn", "V"), ("phas", "V")])
    def measure_with_alazar():
        ind_vals = numpy.vstack((time_vals, space_vals))
        dep_vals = numpy.vstack((magn_vals, phas_vals))
        return ind_vals, dep_vals

    so = sweep(repetition_param, [1])(
        measure_with_alazar()
    )

    sweep_output = list(so)

    assert isinstance(sweep_output, list)
    expected_output = [{'repetition': 1,
                        'time': t_val, 'magn': m_val,
                        'phas': p_val, 'space': s_val}
                       for t_val, s_val, m_val, p_val
                       in zip(time_vals, space_vals, magn_vals, phas_vals)]
    assert expected_output == sweep_output
