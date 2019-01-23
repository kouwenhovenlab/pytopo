from itertools import count
from typing import Iterator, Callable

from more_itertools import take

from ...core import Sweep, Bag, run


def test_hardsweep_inside_1_d():
    """
    1D sweep with a hardware measurement inside: for each x, perform a
    hardware measurement where y values and measured a values are obtained
    from the hardware (values for y cannot be iteratively set from the
    program)
    """
    # Set function for x

    x_set = []

    def set_x(bag: Bag) -> Bag:
        x = bag.val_for('x')

        x_set.append(x)

        return bag

    # Hardware measurement function for y and a

    y_vals = [4, 5, 6]

    a_measured = []

    counter = count(start=0, step=1)

    def measure_ya() -> Iterator:
        a_vals = take(len(y_vals), counter)

        a_measured.extend(a_vals)

        return zip(y_vals, a_vals)

    class IterableFromFunc:
        """
        Needed for executing measurement functions when this object is getting
        iterated over in a for loop
        """
        def __init__(self, func: Callable[[], Iterator]):
            self._func = func

        def __iter__(self) -> Iterator:
            return self._func()

    # Helper that unpacks y and a values from ya tuples in the bag

    y_unpacked = []
    a_unpacked = []

    def unpack_ya(bag: Bag) -> Bag:
        y, a = bag.val_for('ya')

        bag.add('y', y)
        bag.add('a', a)

        bag.remove_for('ya')

        y_unpacked.append(y)
        a_unpacked.append(a)

        return bag

    # Save data function

    bags_saved = []

    def save_data(bag: Bag) -> None:
        bags_saved.append(bag.copy())

    # Setting up sweep and running it

    x_vals = [7, 8, 9]

    initial_bag = Bag()

    run([Sweep('x', x_vals, set_x),
         Sweep('ya', IterableFromFunc(measure_ya), unpack_ya)],
        initial_bag,
        lambda bag: bag,
        save_data)

    # Important assertions

    x_expected = x_vals
    assert x_expected == x_set

    y_expected = y_vals * len(x_vals)
    assert y_expected == y_unpacked

    a_expected = list(range(len(x_vals) * len(y_vals)))
    assert a_expected == a_measured
    assert a_expected == a_unpacked

    bags_expected = [[{'x': x}, {'y': y, 'a': a}]
                     for (x, y), a in zip([(x, y)
                                           for x in x_vals
                                           for y in y_vals
                                           ],
                                          a_expected)
                     ]
    assert bags_expected == bags_saved
