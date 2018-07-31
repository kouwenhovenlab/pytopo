import numpy as np

from typing import List, Iterable, Tuple, Callable, Any

from qcodes import ParamSpec
from pytopo.sweep import param_table
from pytopo.sweep.param_table import ParamTable


def _generate_tables(names_units: Iterable[Tuple]) ->List[ParamTable]:
    """
    Args:
        names_units: List of tuples with parameter names and units, e.g.
            [("gate", "V"), ("Isd", "A")]

    Returns:
        A list of ParamTable with each table containing a single spec
    """
    return [ParamTable([ParamSpec(
        name=name,
        paramtype='numeric',
        unit=unit,
        label=name
    )]) for name, unit in names_units]


def getter(*names_units: Tuple) ->Callable:

    table = param_table.add(_generate_tables(names_units))

    def decorator(func: Callable) ->Callable:
        def inner() ->Tuple[Callable, ParamTable]:

            def wrapper() ->dict:
                results = np.atleast_1d(func())
                return {k[0]: v for k, v in zip(names_units, results)}

            return wrapper, table

        inner.getter_setter_decorated = True
        return inner

    return decorator


def setter(*names_units: Tuple) ->Callable:

    table = param_table.prod(_generate_tables(names_units))

    def decorator(func: Callable) ->Callable:
        def inner() ->Tuple[Callable, ParamTable]:

            def wrapper(*set_values: Any) ->dict:
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
