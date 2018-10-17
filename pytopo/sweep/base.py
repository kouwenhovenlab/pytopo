import numpy as np

from typing import Iterator, Callable

from pytopo.sweep import param_table
from pytopo.sweep.param_table import ParamTable


class BaseSweepObject:
    """
    A sweep object is an iterable and at every iteration we produce a
    dictionary which is meant as input for the data saver class.
    """
    def __init__(self) ->None:

        self._generator: Iterator = None
        self._parameter_table: ParamTable = None
        self._measurable = False

    def _generator_factory(self) ->Iterator:
        """
        This generator should yield a dictionary at each iteration. We will
        use add_results to add this dictionary to a data set
        """
        raise NotImplementedError("Please subclass BaseSweepObject")

    def _start_iter(self) ->None:
        self._generator = self._generator_factory()

    def __iter__(self) ->'BaseSweepObject':
        self._start_iter()
        return self

    def __next__(self) ->dict:
        if self._generator is None:
            self._start_iter()

        return next(self._generator)

    def __call__(self, *sweep_objects):
        return Nest(self, Chain(*sweep_objects))

    @property
    def parameter_table(self) ->ParamTable:
        return self._parameter_table

    @property
    def measurable(self):
        return self._measurable

    @property
    def has_chain(self):
        return len(self.parameter_table.nests) > 1


class IteratorSweep(BaseSweepObject):
    """
    Sweep independent parameters by unrolling an iterator. This class is useful
    if we have "bare" parameter set iterator
    and need to create a proper sweep object as defined in the BaseSweepObject
    docstring. See the "Nest" subclass for an example.
    Parameters
    ----------
    iterator_function: callable
        A callable with no parameters, returning an iterator. Unrolling this
        iterator has the effect of setting the independent parameters.
    """

    def __init__(
            self,
            iterator_function: Callable,
            parameter_table: ParamTable=None,
            measurable: bool = False
    )->None:
        super().__init__()
        self._iterator_function = iterator_function
        self._parameter_table = parameter_table
        self._measurable = measurable

    def _generator_factory(self) ->Iterator:
        for value in self._iterator_function():
            yield value


class Nest(BaseSweepObject):
    """
    Nest multiple sweep objects. This is for example very useful when
    performing two or higher dimensional scans
    (e.g. sweep two gate voltages and measure a current at each coordinate
    (gate1, gate2).
    Notes
    -----
    We produce a nested sweep object of arbitrary depth by first defining a
    function which nests just two sweep objects
        product = two_product(so1, so2)
    A third order nest is then achieved like so:
        product = two_product(so1, two_product(so2, so3))
    A fourth order by
        product = two_product(so1, two_product(so2, two_product(so3, so4)))
    Etc...
    """

    def __init__(self, *sweep_objects: BaseSweepObject) ->None:
        super().__init__()

        if any([so.has_chain for so in sweep_objects[:-1]]):
            raise TypeError("Cannot nest in chained sweep object")

        if any(so.measurable for so in sweep_objects[:-1]):
            raise TypeError("In a nest, only the last sweep object may be "
                            "measurable")

        self._measurable = sweep_objects[-1].measurable
        self._sweep_objects = sweep_objects
        self._parameter_table = param_table.prod(
            [so.parameter_table for so in sweep_objects]
        )

    @staticmethod
    def _two_product(sweep_object1: BaseSweepObject,
                     sweep_object2: BaseSweepObject) ->IteratorSweep:
        def inner():
            for result2 in sweep_object2:
                for result1 in sweep_object1:
                    result1.update(result2)
                    yield result1

        return IteratorSweep(inner)

    def _generator_factory(self) ->Iterator:
        prod = self._sweep_objects[0]
        for so in self._sweep_objects[1:]:
            prod = self._two_product(so, prod)

        return prod


class Chain(BaseSweepObject):
    """
    Chain a list of sweep object to run one after the other
    """

    def __init__(self, *sweep_objects: BaseSweepObject) ->None:
        super().__init__()
        self._sweep_objects = sweep_objects
        self._parameter_table = param_table.add(
            [so.parameter_table for so in sweep_objects]
        )

        self._measurable = any([so.measurable for so in sweep_objects])

    def _generator_factory(self) ->Iterator:
        for so in self._sweep_objects:
            for result in so:
                yield result


class Zip(BaseSweepObject):
    def __init__(self, *sweep_objects: BaseSweepObject) ->None:
        super().__init__()
        self._sweep_objects = sweep_objects
        self._parameter_table = param_table.prod(
            [so.parameter_table for so in sweep_objects]
        )

    def _generator_factory(self) ->Iterator:
        for sos in zip(*self._sweep_objects):
            yield {k: v for d in sos for k, v in d.items()}


class Sweep(BaseSweepObject):
    """
    Sweep independent parameters by looping over set point values and setting
    a QCoDeS parameter to this value at each iteration

    Parameters
    ----------
    set_function (callable):
        A function of one argument which sets the independent parameter
    point_function (callable)
        Unrolling this iterator returns to us set values of the parameter
    """

    def __init__(
            self, set_function: Callable, parameter_table: ParamTable,
            point_function: Callable) ->None:

        super().__init__()
        self._point_function = point_function
        self._set_function = set_function
        self._parameter_table = parameter_table.copy()

    def _generator_factory(self)->Iterator:
        for set_value in self._point_function():
            yield self._set_function(*np.atleast_1d(set_value))


class Measure(BaseSweepObject):
    """
    A wrapper class which iterates once and returns the get value of a QCoDeS
    parameter. Since we are getting a parameter value, instances of
    ParameterWrapper are measurable
    """

    def __init__(self, get_function: Callable,
                 parameter_table: param_table)->None:

        super().__init__()

        self._get_function = get_function
        self._parameter_table = parameter_table.copy()
        self._measurable = True

    def _generator_factory(self)->Iterator:
        yield self._get_function()


class _CallSweepObject(BaseSweepObject):
    """
    ...

    Note: this feature DOES NOT WORK at the moment.
    """
    def __init__(self, call_function, *args, **kwargs):
        super().__init__()
        self._caller = lambda: call_function(*args, **kwargs)
        self._parameter_table = ParamTable([], nests=[[]])

    def _generator_factory(self):
        self._caller()
        yield {}
