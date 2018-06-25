from pytopo.sweep.base import (
    ParameterSweep, ParameterWrapper, Nest, Chain,
    BaseSweepObject
)

from pytopo.sweep.param_table import ParamTable


class _ConvenienceWrapper(BaseSweepObject):
    def __init__(self, sweep_object):
        super().__init__()
        self._sweep_object = sweep_object

    def _generator_factory(self):
        return self._sweep_object._generator_factory()

    def __call__(self, *sweep_objects):
        return Nest(self._sweep_object, Chain(*sweep_objects))


class CallSweepObject(BaseSweepObject):
    def __init__(self, call_function, *args, **kwargs):
        super().__init__()
        self._caller = lambda: call_function(*args, **kwargs)
        self._parameter_table = ParamTable([])

    def _generator_factory(self):
        self._caller()
        yield


def sweep(parameter, set_points):

    if not callable(set_points):
        sweep_object = ParameterSweep(parameter, lambda: set_points)
    else:
        sweep_object = ParameterSweep(parameter, set_points)

    return _ConvenienceWrapper(sweep_object)


def measure(parameter):
    return ParameterWrapper(parameter)


def call(call_function, *args, **kwargs):
    return CallSweepObject(call_function, *args, **kwargs)
