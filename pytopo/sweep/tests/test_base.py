import itertools
import pytest

from qcodes import Parameter
from pytopo.sweep.base import Sweep, Measure, Nest, Chain
from pytopo.sweep.getter_setter import parameter_setter, parameter_getter


@pytest.fixture()
def params():
    x = Parameter("x", set_cmd=None, get_cmd=None)
    y = Parameter("y", set_cmd=None, get_cmd=None)

    x.set(0)
    y.set(0)

    fx_call = lambda xv: xv**2
    fxy_call = lambda xv, yv: xv**2 + yv**2

    fx = Parameter("fx", get_cmd=lambda: fx_call(x()))
    fxy = Parameter("fxy", get_cmd=lambda: fxy_call(x(), y()))

    xstr = parameter_setter(x)
    ystr = parameter_setter(y)

    xstr.get = x.get
    ystr.get = y.get

    fxgtr = parameter_getter(fx)
    fxygtr = parameter_getter(fxy)

    fxgtr.get = fx_call
    fxygtr.get = fxy_call

    return xstr, ystr, fxgtr, fxygtr


def test_sweep_parameter(params):

    x, y, fx, fxy = params
    sweep_values = [0, 1, 2]
    parameter_sweep = Sweep(x, lambda: sweep_values)

    assert list(parameter_sweep) == [{"x": value} for value in sweep_values]


def test_parameter_wrapper(params):
    x, y, fx, fxy = params
    assert list(Measure(fx)) == [{"fx": fx.get(x.get())}]


def test_nest(params):
    x, y, fx, fxy = params
    sweep_values = [0, 1, 2]

    nest = Nest(
        Sweep(x, lambda: sweep_values),
        Measure(fx)
    )

    assert list(nest) == [{"x": xval, "fx": fx.get(xval)}
                          for xval in sweep_values]


def test_nest_2d(params):
    x, y, fx, fxy = params

    sweep_values_x = [0, 1, 2]
    sweep_values_y = [5, 6, 7]

    nest = Nest(
        Sweep(x, lambda: sweep_values_x),
        Sweep(y, lambda: sweep_values_y),
        Measure(fxy)
    )

    assert list(nest) == [
        {"x": xval, "y": yval, "fxy": fxy.get(xval, yval)}
        for xval, yval in itertools.product(sweep_values_x, sweep_values_y)
    ]


def test_error_no_nest_in_measurable(params):
    x, y, fx, fxy = params

    with pytest.raises(TypeError):
        Nest(
            Measure(fx),
            Sweep(x, lambda: [])
        )


def test_chain_simple(params):
    x, y, fx, fxy = params

    sweep_values_x = [0, 1, 2]
    sweep_values_y = [4, 5, 6]

    parameter_sweep = Chain(
        Sweep(x, lambda: sweep_values_x),
        Sweep(y, lambda: sweep_values_y)
    )

    expected_result = [{"x": value} for value in sweep_values_x]
    expected_result.extend([{"y": value} for value in sweep_values_y])

    assert list(parameter_sweep) == expected_result


def test_nest_chain(params):
    x, y, fx, fxy = params

    sweep_values_x = [0, 1, 2]
    sweep_values_y = [4, 5, 6]

    sweep_object = Nest(
        Sweep(x, lambda: sweep_values_x),
        Sweep(y, lambda: sweep_values_y),
        Chain(
            Measure(fx),
            Measure(fxy)
        )
    )

    for xvalue in sweep_values_x:
        for yvalue in sweep_values_y:
            assert next(sweep_object) == {
                "x": xvalue, "y": yvalue, "fx": fx.get(xvalue)}
            assert next(sweep_object) == {
                "x": xvalue, "y": yvalue, "fxy": fxy.get(xvalue, yvalue)}


def test_interleave_1d_2d(params):
    x, y, fx, fxy = params

    sweep_values_x = [0, 1, 2]
    sweep_values_y = [7, 6, 5]

    sweep_object = Nest(
        Sweep(x, lambda: sweep_values_x),
        Chain(
            Measure(fx),
            Nest(
                Sweep(y, lambda: sweep_values_y),
                Measure(fxy)
            )
        )
    )

    for xvalue in sweep_values_x:
        assert next(sweep_object) == {"x": xvalue, "fx": fx.get(xvalue)}
        for yvalue in sweep_values_y:
            assert next(sweep_object) == {"x": xvalue, "y": yvalue,
                                          "fxy": fxy.get(xvalue, yvalue)}


def test_error_no_nest_in_chain(params):
    x, y, fx, fxy = params

    sweep_values_x = [0, 1, 2]
    sweep_values_y = [4, 5, 6]

    with pytest.raises(TypeError):
        Nest(
            Chain(
                Sweep(x, lambda: sweep_values_x),
                Sweep(y, lambda: sweep_values_y)
            ),
            Measure(fx)
        )


def test_error_no_nest_in_chain_2(params):
    x, y, fx, fxy = params
    sweep_values = [0, 1, 2]

    sweep_object = Nest(
        Sweep(x, lambda: sweep_values),
        Chain(
            Measure(fx)
        )
    )

    with pytest.raises(TypeError):
        Nest(
            sweep_object,
            Measure(fxy)
        )
