import time

from qcodes import Parameter

from pytopo.sweep.base import Sweep, Measure, Zip, CallSweepObject
from pytopo.sweep.getter_setter import parameter_setter, parameter_getter


def sweep(fun_or_param, set_points):

    if isinstance(fun_or_param, Parameter):
        fun = parameter_setter(fun_or_param)
    else:
        fun = fun_or_param

    if not callable(set_points):
        sweep_object = Sweep(fun, lambda: set_points)
    else:
        sweep_object = Sweep(fun, set_points)

    return sweep_object


def measure(fun_or_param):

    if isinstance(fun_or_param, Parameter):
        fun = parameter_getter(fun_or_param)
    else:
        fun = fun_or_param

    return Measure(fun)


def time_trace(interval_time, total_time=None, stop_condition=None):

    start_time = None   # Set when we call "generator_function"

    if total_time is None:
        if stop_condition is None:
            raise ValueError("Either specify the total time or the stop "
                             "condition")

    else:
        def stop_condition():
            global start_time
            return time.time() - start_time > total_time

    def generator_function():
        global start_time
        start_time = time.time()
        while not stop_condition():
            yield time.time() - start_time
            time.sleep(interval_time)

    time_parameter = Parameter(
        name="time", unit="s", set_cmd=None, get_cmd=None)

    return sweep(time_parameter, generator_function)


def szip(*sweep_objects):
    return Zip(*sweep_objects)


def call(call_function, *args, **kwargs):
    return CallSweepObject(call_function, *args, **kwargs)

