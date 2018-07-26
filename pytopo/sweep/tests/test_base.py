import itertools
import pytest

from qcodes import Parameter
from pytopo.sweep.base import Sweep, Measure, Nest, Chain


def test_sweep_parameter():

    x = Parameter("x", set_cmd=None, get_cmd=None)
    sweep_values = [0, 1, 2]
    parameter_sweep = Sweep(x, lambda: sweep_values)

    assert list(parameter_sweep) == [{x.name: value} for value in sweep_values]


def test_parameter_wrapper():
    m = Parameter("m", set_cmd=None, get_cmd=None)
    m.set(3)
    param_wrapper = Measure(m)

    assert list(param_wrapper) == [{m.name: m.get()}]


def test_nest():

    def f(xvalue):
        return xvalue**2

    x = Parameter("x", set_cmd=None, get_cmd=None)
    m = Parameter("m", get_cmd=lambda: f(x()))

    sweep_values = [0, 1, 2]

    nest = Nest(
        Sweep(x, lambda: sweep_values),
        Measure(m)
    )

    assert list(nest) == [{x.name: xval, m.name: f(xval)}
                          for xval in sweep_values]


def test_nest_2d():

    def f(xvalue, yvalue):
        return xvalue**2 + yvalue

    x = Parameter("x", set_cmd=None, get_cmd=None)
    y = Parameter("y", set_cmd=None, get_cmd=None)
    m = Parameter("m", get_cmd=lambda: f(x(), y()))

    sweep_values_x = [0, 1, 2]
    sweep_values_y = [5, 6, 7]

    nest = Nest(
        Sweep(x, lambda: sweep_values_x),
        Sweep(y, lambda: sweep_values_y),
        Measure(m)
    )

    assert list(nest) == [
        {x.name: xval, y.name: yval, m.name: f(xval, yval)}
        for xval, yval in itertools.product(sweep_values_x, sweep_values_y)
    ]


def test_nest_3d():

    def f(xvalue, yvalue, zvalue):
        return xvalue**2 + yvalue / zvalue

    x = Parameter("x", set_cmd=None, get_cmd=None)
    y = Parameter("y", set_cmd=None, get_cmd=None)
    z = Parameter("z", set_cmd=None, get_cmd=None)
    m = Parameter("m", get_cmd=lambda: f(x(), y(), z()))

    sweep_values_x = [0, 1, 2]
    sweep_values_y = [5, 6, 7]
    sweep_values_z = [3, 6, 9]

    nest = Nest(
        Sweep(x, lambda: sweep_values_x),
        Sweep(y, lambda: sweep_values_y),
        Sweep(z, lambda: sweep_values_z),
        Measure(m)
    )

    assert list(nest) == [
        {x.name: xval, y.name: yval, z.name: zval, m.name: f(xval, yval, zval)}
        for xval, yval, zval in
        itertools.product(sweep_values_x, sweep_values_y, sweep_values_z)
    ]


def test_error_no_nest_in_measurable():

    x = Parameter("x")
    m = Parameter("m")

    with pytest.raises(TypeError):
        Nest(
            Measure(m),
            Sweep(x, lambda: [])
        )


def test_chain_simple():

    x = Parameter("x", set_cmd=None, get_cmd=None)
    y = Parameter("y", set_cmd=None, get_cmd=None)

    sweep_values_x = [0, 1, 2]
    sweep_values_y = [4, 5, 6]

    parameter_sweep = Chain(
        Sweep(x, lambda: sweep_values_x),
        Sweep(y, lambda: sweep_values_y)
    )

    expected_result = [{x.name: value} for value in sweep_values_x]
    expected_result.extend([{y.name: value} for value in sweep_values_y])

    assert list(parameter_sweep) == expected_result


def test_nest_chain():

    def f(xvalue):
        return xvalue**2

    def g(xvalue):
        return xvalue + 2

    x = Parameter("x", set_cmd=None, get_cmd=None)
    m = Parameter("m", get_cmd=lambda: f(x()))
    n = Parameter("n", get_cmd=lambda: g(x()))

    sweep_values = [0, 1, 2]

    sweep_object = Nest(
        Sweep(x, lambda: sweep_values),
        Chain(
            Measure(m),
            Measure(n)
        )
    )

    for xvalue in sweep_values:
        assert next(sweep_object) == {x.name: xvalue, m.name: f(xvalue)}
        assert next(sweep_object) == {x.name: xvalue, n.name: g(xvalue)}


def test_interleave_1d_2d():
    def f(xvalue):
        return xvalue**2

    def g(xvalue, yvalue):
        return xvalue + 2 - yvalue

    x = Parameter("x", set_cmd=None, get_cmd=None)
    y = Parameter("y", set_cmd=None, get_cmd=None)
    m = Parameter("m", get_cmd=lambda: f(x()))
    n = Parameter("n", get_cmd=lambda: g(x(), y()))

    sweep_values_x = [0, 1, 2]
    sweep_values_y = [7, 6, 5]

    sweep_object = Nest(
        Sweep(x, lambda: sweep_values_x),
        Chain(
            Measure(m),
            Nest(
                Sweep(y, lambda: sweep_values_y),
                Measure(n)
            )
        )
    )

    for xvalue in sweep_values_x:
        assert next(sweep_object) == {x.name: xvalue, m.name: f(xvalue)}
        for yvalue in sweep_values_y:
            assert next(sweep_object) == {x.name: xvalue, y.name: yvalue,
                                          n.name: g(xvalue, yvalue)}


def test_error_no_nest_in_chain():
    x = Parameter("x", set_cmd=None, get_cmd=None)
    y = Parameter("y", set_cmd=None, get_cmd=None)
    m = Parameter("m", set_cmd=None, get_cmd=None)

    sweep_values_x = [0, 1, 2]
    sweep_values_y = [4, 5, 6]

    with pytest.raises(TypeError):
        Nest(
            Chain(
                Sweep(x, lambda: sweep_values_x),
                Sweep(y, lambda: sweep_values_y)
            ),
            Measure(m)
        )


def test_error_no_nest_in_chain_2():
    def f(xvalue):
        return xvalue**2

    def g(xvalue):
        return xvalue + 2

    x = Parameter("x", set_cmd=None, get_cmd=None)
    m = Parameter("m", get_cmd=lambda: f(x()))
    n = Parameter("n", get_cmd=lambda: g(x()))

    sweep_values = [0, 1, 2]

    sweep_object = Nest(
        Sweep(x, lambda: sweep_values),
        Chain(
            Measure(m)
        )
    )

    with pytest.raises(TypeError):
        Nest(
            sweep_object,
            Measure(n)
        )
