import numpy as np

from qcodes import ParamSpec
from pytopo.sweep import param_table
from pytopo.sweep.param_table import ParamTable


def _generate_tables(names_units):
    return [ParamTable([ParamSpec(
        name=name,
        paramtype='numeric',
        unit=unit,
        label=name
    )]) for name, unit in names_units]


def getter(*names_units):

    table = param_table.add(_generate_tables(names_units))

    def decorator(func):
        def inner():
            def wrapper():
                results = np.atleast_1d(func())
                return {k[0]: v for k, v in zip(names_units, results)}

            return wrapper, table

        inner.getter_setter_decorated = True
        return inner

    return decorator


def setter(*names_units):

    table = param_table.prod(_generate_tables(names_units))

    def decorator(func):
        def inner():
            def wrapper(*set_values):
                func(*set_values)
                return {k[0]: v for k, v in zip(names_units, set_values)}

            return wrapper, table

        inner.getter_setter_decorated = True
        return inner
    return decorator


def parameter_setter(parameter):
    names_units = (parameter.full_name, parameter.unit)
    return setter(names_units)(parameter.set)


def parameter_getter(parameter):
    names_units = (parameter.full_name, parameter.unit)
    return getter(names_units)(parameter.get)
