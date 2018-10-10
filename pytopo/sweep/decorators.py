import numpy as np

from typing import List, Iterable, Tuple, Callable, Any

from qcodes import ParamSpec
from pytopo.sweep import param_table
from pytopo.sweep.param_table import ParamTable
from pytopo.sweep.base import IteratorSweep


class _GetterSetterFunction:
    def __init__(self, cablle, table):
        self._caller = cablle
        self._table = table

    def __call__(self, *args, **kwargs):
        return self._caller(*args, **kwargs)

    @property
    def parameter_table(self):
        return self._table


class MeasureFunction(_GetterSetterFunction):
    pass


class SweepFunction(_GetterSetterFunction):
    pass


def _generate_tables(names_units: Iterable[Tuple]) ->List[ParamTable]:
    """
    Generates ParamTables from a simple input list of tuples which describe
    the parameters.

    Args:
        names_units
            List of tuples with parameter names and units; optionally,
            'paramtype' can be supplied that defines the way the parameter
            values are saved ('numeric' is a default).
            Example: [("gate", "V"), ("Isd", "A", "array")]

    Returns:
        A list of ParamTable with each table containing a single ParamSpec
    """
    param_tables = []

    for name_unit in names_units:
        name = name_unit[0]
        unit = name_unit[1]

        if len(name_unit) > 2:
            paramtype = name_unit[2]
        else:
            paramtype = 'numeric'

        param_tables.append(
            ParamTable([
                ParamSpec(
                    name=name,
                    paramtype=paramtype,
                    unit=unit,
                    label=name
                )
            ])
        )

    return param_tables


def getter(*names_units: Tuple) ->Callable:
    """
    Args:
        names_units
            List of tuples with parameter names and units (and optionally
            'paramtype' that defines how the data is saved),
            e.g. [("gate", "V"), ("Isd", "A", "array")]

    Returns:
        A decorator. The decorated function returns a callable and a parameter
        table. The callable calls the decorated function which should return
        measurement values.

    For more information about 'paramtype' argument, see `register_parameter`
    method of `Measurement` class in QCoDeS.
    """

    table = param_table.add(_generate_tables(names_units))

    def decorator(func: Callable) ->MeasureFunction:
        def inner() ->dict:
            results = np.atleast_1d(func())
            return {k[0]: v for k, v in zip(names_units, results)}

        return MeasureFunction(inner, table.copy())
    return decorator


def setter(*names_units: Tuple) ->Callable:
    """
    Args:
        names_units
            List of tuples with parameter names and units (and optionally
            'paramtype' that defines how the data is saved),
            e.g. [("gate", "V"), ("Isd", "A", "array")]

    Returns:
        A decorator. The decorated function returns a callable and a parameter
        table. The callable calls the decorated function this the argument
        provided. This will set independent parameters

    For more information about 'paramtype' argument, see `register_parameter`
    method of `Measurement` class in QCoDeS.
    """

    table = param_table.prod(_generate_tables(names_units))

    def decorator(func: Callable) ->SweepFunction:
        def inner(*set_values) ->dict:
            func(*set_values)
            return {k[0]: v for k, v in zip(names_units, set_values)}

        return SweepFunction(inner, table)
    return decorator


def hardsweep(ind: List[Tuple], dep: List[Tuple]) ->Callable:
    """
    Args:
        ind: List of independent parameters, defined as tuples of names and
                units (and optionally 'paramtype').
        dep: List of dependent parameters, defined as tuples of names and
                units (and optionally 'paramtype').

    Returns:
        A decorator which returns a sweep object, which can be directly used
        in pytopo.do_experiment to run an experiment.

    Example:
        >>> import pytopo
        >>> @hardsweep(ind=[("x", "V"), ("y", "V")], dep=[("i", "A")])
        >>> def some_function():
        >>> ... # Some code setting up instruments and performing measurements
        >>> ... return set_points, measurements
        >>> pytopo.do_experiement("name/sample", some_function)

        Since we have defined to independent parameters, `x` and `y`, the
        returned `set_points` should be a 2-by-N numpy array, where `N` is the
        number of set points. We have one dependent parameters, `i`, therefor
        `measurements` is an 1-by-N numpy array.

        The signature of `some_function` can be anything the user desires.
        However, the return value of this function has to consist of two numpy
        arrays with the aforementioned shape.

        Note that if any of the parameters has 'array' paramtype, then the
        arrays that are potentially returned by the decorated function will
        not be iterated through. Instead, they will be passed "as is"
        together with the 'numeric' values (if any).

        Please see pytopo/sweep/docs/hardsweep.ipynb for a more elaborate
        example
    """
    # If we have two independent parameters, say `x` and `y`, then we are
    # sampling in an inner product space spanned by two axes. Hence we need to
    # use the `prod` operator to generate the appropriate table
    ind_table = param_table.prod(_generate_tables(ind))

    # Each dependent parameter adds a seperate measurement. Hence we need to
    # use the `add` operator
    dep_table = param_table.add(_generate_tables(dep))

    # Each dependent parameter needs to be nested in the table of independent
    # parameters. This is performed with the `prod` operator.
    table = param_table.prod([ind_table, dep_table])

    def decorator(func: Callable) ->Callable:
        def inner(*args, **kwargs) ->IteratorSweep:

            ind_paramtypes = [i[2] if len(i) > 2 else 'numeric' for i in ind]
            dep_paramtypes = [d[2] if len(d) > 2 else 'numeric' for d in dep]
            any_array = np.any(np.array([ind_paramtypes + dep_paramtypes])
                               == 'array')

            def wrapper() ->dict:
                spoints, measurements = func(*args, **kwargs)

                spoints = np.atleast_2d(spoints)
                measurements = np.atleast_2d(measurements)

                if spoints.shape[0] != len(ind) or \
                   measurements.shape[0] != len(dep):

                    raise ValueError("The number of points or measurements "
                                     "returned does not match the number of "
                                     "dependent and/or independent parameters")
                if any_array:
                    res = {k[0]: v for k, v in zip(ind, spoints)}
                    res.update({k[0]: v for k, v in zip(dep, measurements)})
                    yield res
                else:
                    for spoint, measurement in zip(spoints.T, measurements.T):
                        res = {k[0]: v for k, v in zip(ind, spoint)}
                        res.update({k[0]: v for k, v in zip(dep, measurement)})
                        yield res

            sweep_object = IteratorSweep(
                wrapper, parameter_table=table.copy(), measurable=True
            )
            return sweep_object

        return inner
    return decorator


def parameter_setter(parameter, paramtype: str = None):
    if paramtype:
        names_units = (parameter.full_name, parameter.unit, paramtype)
    else:
        names_units = (parameter.full_name, parameter.unit)
    return setter(names_units)(parameter.set)


def parameter_getter(parameter, paramtype: str = None):
    if paramtype:
        names_units = (parameter.full_name, parameter.unit, paramtype)
    else:
        names_units = (parameter.full_name, parameter.unit)
    return getter(names_units)(parameter.get)
