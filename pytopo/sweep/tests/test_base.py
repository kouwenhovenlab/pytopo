import itertools
import pytest

from qcodes import Parameter, ParamSpec
from pytopo.sweep.base import Sweep, Measure, Nest, Chain
from pytopo.sweep.param_table import ParamTable

from ._test_tools import Factory


@pytest.fixture()
def indep_params():
    """
    Fixture of making independent parameters
    """
    def mk_tuple(name):

        param = Parameter(name, set_cmd=None, get_cmd=None)

        def setter(value):
            param.set(value)
            return {name: value}

        return param, setter, ParamTable([ParamSpec(name, "numeric")])

    return Factory(mk_tuple)


@pytest.fixture()
def dep_params():
    """
    Fixture of making dependent parameters
    """
    def mk_tuple(name):

        param = Parameter(name, set_cmd=None, get_cmd=None)

        def getter():
            return {name: param.get()}

        return param, getter, ParamTable([ParamSpec(name, "numeric")])

    return Factory(mk_tuple)


def test_sweep_parameter(indep_params):

    px, x, table = indep_params["x"]

    sweep_values = [0, 1, 2]
    parameter_sweep = Sweep(x, table, lambda: sweep_values)

    assert list(parameter_sweep) == [{"x": value} for value in sweep_values]


def test_nest(indep_params, dep_params):

    px, x, tablex = indep_params["x"]
    pi, i, tablei = dep_params["i"]

    def f(value): return value**2

    pi.get = lambda: f(px())

    sweep_values = [0, 1, 2]

    nest = Nest(
        Sweep(x, tablex, lambda: sweep_values),
        Measure(i, tablei)
    )

    assert list(nest) == [{"x": xval, "i": f(xval)} for xval in sweep_values]


def test_nest_2d(indep_params, dep_params):
    px, x, tablex = indep_params["x"]
    py, y, tabley = indep_params["y"]

    def f(vx, vy): return vx**2 + vy**2

    pi, i, tablei = dep_params["i"]
    pi.get = lambda: f(px(), py())

    sweep_values_x = [0, 1, 2]
    sweep_values_y = [5, 6, 7]

    nest = Nest(
        Sweep(x, tablex, lambda: sweep_values_x),
        Sweep(y, tabley, lambda: sweep_values_y),
        Measure(i, tablei)
    )

    assert list(nest) == [
        {"x": xval, "y": yval, "i": f(xval, yval)}
        for xval, yval in itertools.product(sweep_values_x, sweep_values_y)
    ]


def test_nest_3d(indep_params, dep_params):
    px, x, tablex = indep_params["x"]
    py, y, tabley = indep_params["y"]
    pz, z, tablez = indep_params["z"]

    def f(vx, vy, vz): return vx**2 + vy**2 + vz**2

    pi, i, tablei = dep_params["i"]
    pi.get = lambda: f(px(), py(), pz())

    sweep_values_x = [0, 1, 2]
    sweep_values_y = [5, 6, 7]
    sweep_values_z = [8, 9, 10]

    nest = Nest(
        Sweep(x, tablex, lambda: sweep_values_x),
        Sweep(y, tabley, lambda: sweep_values_y),
        Sweep(z, tablez, lambda: sweep_values_z),
        Measure(i, tablei)
    )

    assert list(nest) == [
        {"x": xval, "y": yval, "z": zval, "i": f(xval, yval, zval)}
        for xval, yval, zval in itertools.product(
            sweep_values_x, sweep_values_y, sweep_values_z)
    ]


def test_error_no_nest_in_measurable(indep_params, dep_params):
    px, x, tablex = indep_params["x"]
    pi, i, tablei = dep_params["i"]

    with pytest.raises(TypeError):
        Nest(
            Measure(i, tablei),
            Sweep(x, tablex, lambda: [])
        )


def test_chain_simple(indep_params):
    px, x, tablex = indep_params["x"]
    py, y, tabley = indep_params["y"]

    sweep_values_x = [0, 1, 2]
    sweep_values_y = [4, 5, 6]

    parameter_sweep = Chain(
        Sweep(x, tablex, lambda: sweep_values_x),
        Sweep(y, tabley, lambda: sweep_values_y)
    )

    expected_result = [{"x": value} for value in sweep_values_x]
    expected_result.extend([{"y": value} for value in sweep_values_y])

    assert list(parameter_sweep) == expected_result


def test_nest_chain(indep_params, dep_params):
    px, x, tablex = indep_params["x"]
    py, y, tabley = indep_params["y"]

    pi, i, tablei = dep_params["i"]
    pj, j, tablej = dep_params["j"]

    def f(vx, vy):
        return vx**2 + vy**3

    pi.get = lambda: f(px(), py())

    def g(vx, vy):
        return vx**2 + vy**2

    pj.get = lambda: g(px(), py())

    sweep_values_x = [0, 1, 2]
    sweep_values_y = [4, 5, 6]

    sweep_object = Nest(
        Sweep(x, tablex, lambda: sweep_values_x),
        Sweep(y, tabley, lambda: sweep_values_y),
        Chain(
            Measure(i, tablei),
            Measure(j, tablej)
        )
    )

    for xvalue in sweep_values_x:
        for yvalue in sweep_values_y:
            assert next(sweep_object) == {
                "x": xvalue, "y": yvalue, "i": f(xvalue, yvalue)}
            assert next(sweep_object) == {
                "x": xvalue, "y": yvalue, "j": g(xvalue, yvalue)}


def test_interleave_1d_2d(indep_params, dep_params):
    px, x, tablex = indep_params["x"]
    py, y, tabley = indep_params["y"]

    pi, i, tablei = dep_params["i"]
    pj, j, tablej = dep_params["j"]

    def f(vx):
        return vx ** 2

    pi.get = lambda: f(px())

    def g(vx, vy):
        return vx ** 2 + vy ** 2

    pj.get = lambda: g(px(), py())

    sweep_values_x = [0, 1, 2]
    sweep_values_y = [4, 5, 6]

    sweep_object = Nest(
        Sweep(x, tablex, lambda: sweep_values_x),
        Chain(
            Measure(i, tablei),
            Nest(
                Sweep(y, tabley, lambda: sweep_values_y),
                Measure(j, tablej)
            )
        )
    )

    for xvalue in sweep_values_x:
        assert next(sweep_object) == {"x": xvalue, "i": f(xvalue)}
        for yvalue in sweep_values_y:
            assert next(sweep_object) == {"x": xvalue, "y": yvalue,
                                          "j":g(xvalue, yvalue)}


def test_error_no_nest_in_chain(indep_params, dep_params):
    px, x, tablex = indep_params["x"]
    py, y, tabley = indep_params["y"]

    pi, i, tablei = dep_params["i"]

    sweep_values_x = [0, 1, 2]
    sweep_values_y = [4, 5, 6]

    with pytest.raises(TypeError):
        Nest(
            Chain(
                Sweep(x, tablex, lambda: sweep_values_x),
                Sweep(y, tabley, lambda: sweep_values_y)
            ),
            Measure(i, tablei)
        )


def test_error_no_nest_in_chain_2(indep_params, dep_params):
    px, x, tablex = indep_params["x"]
    pi, i, tablei = dep_params["i"]
    pj, j, tablej = dep_params["j"]

    sweep_values = [0, 1, 2]

    sweep_object = Nest(
        Sweep(x, tablex, lambda: sweep_values),
        Chain(
            Measure(i, tablei)
        )
    )

    with pytest.raises(TypeError):
        Nest(
            sweep_object,
            Measure(j, tablej)
        )
