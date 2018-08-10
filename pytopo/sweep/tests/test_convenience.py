import pytest

from qcodes import Parameter

from pytopo.sweep.convenience import sweep, measure
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


def test_sanity_parameter(parameters):
    p = parameters["p"]
    values = [0, 1, 2]
    so = sweep(p, values)
    assert list(so) == [{"p": value} for value in values]


def test_sanity_function(sweep_functions):
    p = sweep_functions["p"]
    values = [0, 1, 2]
    so = sweep(p, values)
    assert list(so) == [{"p": value} for value in values]


def test_error():
    """
    Setter functions need to be decorated with pytopo.setter
    """

    def no_good_setter(value):
        pass

    with pytest.raises(ValueError):
        sweep(no_good_setter, [0, 1])

