import numpy
import pytest

from qcodes import Parameter

from pytopo.sweep.base import _CallSweepObject
from pytopo.sweep.convenience import sweep, measure, _call, nest, chain
from pytopo.sweep.decorators import getter, setter

from ._test_tools import Factory


@pytest.fixture()
def parameters():
    def create_param(name):
        return Parameter(name, set_cmd=None, get_cmd=None)

    return Factory(create_param)


@pytest.fixture()
def sweep_functions():
    def create_function(name):

        @setter((name, ""))
        def sweep_function(value):
            pass

        return sweep_function

    return Factory(create_function)


def test_sanity_sweep_parameter(parameters):
    p = parameters["p"]
    values = [0, 1, 2]
    so = sweep(p, values)
    assert list(so) == [{"p": value} for value in values]
    assert 'numeric' == so.parameter_table.param_specs[0].type


def test_sweep_parameter_with_paramtype(parameters):
    p = parameters["p"]
    values = [0, 1, 2]
    so = sweep(p, values, paramtype='array')
    assert list(so) == [{"p": value} for value in values]
    assert 'array' == so.parameter_table.param_specs[0].type


def test_sanity_measure_parameter(parameters):
    pval = 12
    p = Parameter('p', set_cmd=False, get_cmd=lambda: pval)

    so = measure(p)

    assert list(so) == [{"p": pval}]
    assert 'numeric' == so.parameter_table.param_specs[0].type


def test_measure_parameter_with_paramtype(parameters):
    pval = 12
    p = Parameter('p', set_cmd=False, get_cmd=lambda: pval)

    so = measure(p, paramtype='array')

    assert list(so) == [{"p": pval}]
    assert 'array' == so.parameter_table.param_specs[0].type


def test_sanity_sweep_setter_function(sweep_functions):
    p = sweep_functions["p"]
    values = [0, 1, 2]
    so = sweep(p, values)
    assert list(so) == [{"p": value} for value in values]
    assert 'numeric' == so.parameter_table.param_specs[0].type


def test_sanity_sweep_getter_function(sweep_functions):
    qval = 123

    @getter(('q', ""))
    def measure_function():
        return qval

    p = sweep_functions["p"]
    values = [0, 1, 2]
    so = sweep(p, values)(
        measure(measure_function)
    )
    assert list(so) == [{"p": value, "q": qval} for value in values]
    assert 'numeric' == so.parameter_table.param_specs[0].type
    assert 'numeric' == so.parameter_table.param_specs[1].type


def test_error():
    """
    Setter functions need to be decorated with `setter`
    """

    def no_good_setter(value):
        pass

    with pytest.raises(ValueError):
        sweep(no_good_setter, [0, 1])


def test_sanity_call():
    var = 2
    def increment_var_by(num):
        nonlocal var
        var = var + num

    so = _call(increment_var_by, 3)

    assert isinstance(so, _CallSweepObject)
    assert False == so.has_chain
    assert False == so.measurable
    assert [[]] == so.parameter_table.nests
    assert [] == so.parameter_table.param_specs

    sweep_output = list(so)
    assert [{}] == sweep_output

    assert 5 == var


def test_call_inside_sweep(parameters):
    p = parameters["p"]
    values = [0, 1, 2]

    var = 2
    def increment_var_by(num):
        nonlocal var
        var = var + num

    so = sweep(p, values)(
        _call(increment_var_by, 3)
    )

    sweep_output = list(so)

    assert sweep_output == [{"p": value} for value in values]
    assert 2 + 3*len(values) == var


def test_call_inside_sweep_and_chain(parameters):
    p = parameters["p"]
    values = [0, 1, 2]

    var = 2
    def increment_var_by(num):
        nonlocal var
        var = var + num

    @getter(('q', ''))
    def measure_function():
        nonlocal var
        return var

    so = nest(sweep(p, values),
              chain(
                  measure(measure_function),
                  _call(increment_var_by, 3)
              )
              )

    sweep_output = list(so)

    assert 2 + 3 * len(values) == var

    # `call` should work like this:
    # assert sweep_output == [{"p": p_val, 'q': q_val}
    #                         for p_val, q_val
    #                         in zip(values,
    #                                2+3*numpy.array(range(len(values)))
    #                                )
    #                         ]

    # instead it works like this:
    # (basically, for every call of 'call' there is an extra dictionary
    # without the second parameter value)
    assert sweep_output == [item for sublist in
        [[{"p": p_val, 'q': q_val}, {"p": p_val}]
         for p_val, q_val
         in zip(values, 2 + 3 * numpy.array(range(len(values))))
         ]
        for item in sublist]


def test_call_inside_sweep_and_chain_2(parameters):
    p = parameters["p"]
    values = [0, 1, 2]

    var = 2
    def increment_var_by(num):
        nonlocal var
        var = var + num

    @getter(('q', ''))
    def measure_function():
        nonlocal var
        return var

    @getter(('v', ''))
    def measure_function_2():
        nonlocal var
        return var + 1

    so = sweep(p, values)(
        measure(measure_function),
        _call(increment_var_by, 3),
        measure(measure_function_2),
    )

    sweep_output = list(so)

    assert 2 + 3 * len(values) == var

    # `call` should work like this:
    # assert sweep_output == [{"p": p_val, 'q': q_val, 'v': v_val}
    #                         for p_val, q_val, v_val
    #                         in zip(values,
    #                                2+3*numpy.array(range(len(values))),
    #                                2+3*numpy.array(range(len(values)))+1
    #                                )
    #                         ]

    # instead it works like this:
    # (basically, there are extra dictionaries without values of some of the
    # parameters that are involved in a sweep object, and more weird stuff...)
    assert sweep_output == [{'q': 2, 'p': 0}, {'p': 0}, {'v': 6, 'p': 0},
                            {'q': 5, 'p': 1}, {'p': 1}, {'v': 9, 'p': 1},
                            {'q': 8, 'p': 2}, {'p': 2}, {'v': 12, 'p': 2}]
