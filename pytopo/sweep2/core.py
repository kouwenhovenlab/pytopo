from collections import UserDict
from typing import Callable, Iterable, List, Any


class BagSection(UserDict):
    """
    A dictionary but called this way to mark that it's inside a `Bag`
    """
    pass


class Bag(list):
    """
    Stack of BagSections with top-to-bottom access to contents of all sections
    """

    NOT_FOUND = object()

    def val_for(self, key: str) -> Any:
        """
        Get value for key from the bag starting with the top of the stack
        and looking deeper if its not found
        """
        for bag_section in self[::-1]:
            value = bag_section.get(key, self.NOT_FOUND)
            if value != self.NOT_FOUND:
                return value

        raise KeyError(f'{key} not found')

    def add(self, key: str, value: Any) -> None:
        """Set key/value in the last element (top of the stack)"""
        self[-1][key] = value

    def flatten(self) -> BagSection:
        """
        Flattens the stack to a single level, ending up with a single bag
        section (list of dicts becomes a dict)
        """
        flattened = BagSection()
        for bag_section in self:
            for key, value in bag_section.items():
                flattened[key] = value
        return flattened


def bag_through(bag: Bag) -> Bag:
    return bag


def bag_in(bag: Bag) -> None:
    pass


class Sweep:
    def __init__(self,
                 param_name: str,
                 values: Iterable,
                 set_function: Callable[[Bag], Bag] = bag_through,
                 prepare_function: Callable[[Bag], None] = bag_in):
        self._param_name = param_name
        self._values = values
        self._set_function = set_function
        self._prepare_function = prepare_function

    @property
    def param_name(self) -> str:
        return self._param_name

    @property
    def values(self) -> Iterable:
        return self._values

    @property
    def set_function(self) -> Callable[[Bag], Bag]:
        return self._set_function

    @property
    def prepare_function(self) -> Callable[[Bag], None]:
        return self._prepare_function


def run(sweeps: List[Sweep],
        bag: Bag,
        measure_v: Callable[[Bag], Bag] = bag_through,
        save_data: Callable[[Bag], None] = bag_in
        ) -> None:
    if len(sweeps) == 0:
        bag = measure_v(bag)
        save_data(bag)
    else:
        sweep = sweeps[0]
        other_sweeps = sweeps[1:]

        sweep.prepare_function(bag)

        for param_value in sweep.values:
            bag.append(BagSection())
            bag.add(sweep.param_name, param_value)

            bag = sweep.set_function(bag)

            run(other_sweeps, bag, measure_v, save_data)

            bag.pop()
