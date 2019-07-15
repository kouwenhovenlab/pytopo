"""
This is mostly copy-paste of test_base but the test cases are user to
test correct registering of parameters in SweepMeasurement.
"""
try:
    from qcodes.dataset.descriptions.param_spec import ParamSpecBase
except ImportError:
    # QCoDeS prio to version 0.4.0
    from qcodes.dataset.param_spec import ParamSpecBase

from pytopo.sweep.measurement import SweepMeasurement
from pytopo.sweep.base import Sweep, Measure, Nest, Chain

from .test_base import indep_params, dep_params


def test_sweep_parameter(indep_params):

    px, x, table = indep_params["x"]

    sweep_values = [0, 1, 2]
    parameter_sweep = Sweep(x, table, lambda: sweep_values)

    meas = SweepMeasurement()
    meas.register_sweep(parameter_sweep)

    interdeps = meas._interdeps
    assert interdeps.dependencies == {}
    assert interdeps.inferences == {}
    assert interdeps.standalones == {ParamSpecBase('x', 'numeric', '', '')}


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

    meas = SweepMeasurement()
    meas.register_sweep(nest)

    interdeps = meas._interdeps
    assert interdeps.dependencies == {
        ParamSpecBase('i', 'numeric', '', ''): (ParamSpecBase('x', 'numeric', '', ''),)}
    assert interdeps.inferences == {}
    assert interdeps.standalones == set()


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

    meas = SweepMeasurement()
    meas.register_sweep(nest)

    interdeps = meas._interdeps
    assert interdeps.dependencies == {
        ParamSpecBase('i', 'numeric', '', ''): (ParamSpecBase('x', 'numeric', '', ''), ParamSpecBase('y', 'numeric', '', ''))}
    assert interdeps.inferences == {}
    assert interdeps.standalones == set()



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

    meas = SweepMeasurement()
    meas.register_sweep(nest)

    interdeps = meas._interdeps
    assert interdeps.dependencies == {
        ParamSpecBase('i', 'numeric', '', ''): (ParamSpecBase('x', 'numeric', '', ''), ParamSpecBase('y', 'numeric', '', ''), ParamSpecBase('z', 'numeric', '', ''))}
    assert interdeps.inferences == {}
    assert interdeps.standalones == set()


def test_chain_simple(indep_params):
    px, x, tablex = indep_params["x"]
    py, y, tabley = indep_params["y"]

    sweep_values_x = [0, 1, 2]
    sweep_values_y = [4, 5, 6]

    parameter_sweep = Chain(
        Sweep(x, tablex, lambda: sweep_values_x),
        Sweep(y, tabley, lambda: sweep_values_y)
    )

    meas = SweepMeasurement()
    meas.register_sweep(parameter_sweep)

    interdeps = meas._interdeps
    assert interdeps.dependencies == {}
    assert interdeps.inferences == {}
    assert interdeps.standalones == {
        ParamSpecBase('y', 'numeric', '', ''), ParamSpecBase('x', 'numeric', '', '')}


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

    meas = SweepMeasurement()
    meas.register_sweep(sweep_object)

    interdeps = meas._interdeps
    assert interdeps.dependencies == {
        ParamSpecBase('i', 'numeric', '', ''): (ParamSpecBase('x', 'numeric', '', ''),
                                                ParamSpecBase('y', 'numeric', '', '')),
        ParamSpecBase('j', 'numeric', '', ''): (ParamSpecBase('x', 'numeric', '', ''),
                                                ParamSpecBase('y', 'numeric', '', ''))}
    assert interdeps.inferences == {}
    assert interdeps.standalones == set()


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

    meas = SweepMeasurement()
    meas.register_sweep(sweep_object)

    interdeps = meas._interdeps
    assert interdeps.dependencies == {
        ParamSpecBase('i', 'numeric', '', ''): (ParamSpecBase('x', 'numeric', '', ''),),
        ParamSpecBase('j', 'numeric', '', ''): (ParamSpecBase('x', 'numeric', '', ''),
                                                ParamSpecBase('y', 'numeric', '', ''))}
    assert interdeps.inferences == {}
    assert interdeps.standalones == set()


def test_nest_in_chain_2_whatever(indep_params, dep_params):
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

    meas = SweepMeasurement()
    meas.register_sweep(sweep_object)

    interdeps = meas._interdeps
    assert interdeps.dependencies == {
        ParamSpecBase('i', 'numeric', '', ''): (ParamSpecBase('x', 'numeric', '', ''),)}
    assert interdeps.inferences == {}
    assert interdeps.standalones == set()
