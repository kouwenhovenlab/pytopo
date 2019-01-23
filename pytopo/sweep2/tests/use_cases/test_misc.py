from itertools import product
from random import random
from typing import List

from ...core import Sweep, run, Bag


def test_2_level_sweep():
    bags = []

    def capturing_bag(func):
        def wrapped(bag):
            new_bag = func(bag)

            # for func which don't return a bag
            bag_to_use = bag if new_bag is None else new_bag

            bags.append(bag_to_use.copy())

            print(f'    Bag is {bag_to_use}')

            return new_bag

        return wrapped

    @capturing_bag
    def set_x(bag: Bag) -> Bag:
        x = bag.val_for('x')
        print(f'Set x to {x}')
        return bag

    @capturing_bag
    def set_y(bag: Bag) -> Bag:
        y = bag.val_for('y')
        print(f'Set y to {y}', end=', ')

        w = y**2
        bag.add('w', w)
        print(f'Add also w as {w}')

        return bag

    @capturing_bag
    def prepare_x(bag: Bag) -> None:
        print(f'Reset x')

    @capturing_bag
    def prepare_y(bag: Bag) -> None:
        print(f'Reset y')

    @capturing_bag
    def measure_v(bag: Bag) -> Bag:
        v = random()
        bag.add('v', v)
        print(f'Measured v as {v}')

        return bag

    @capturing_bag
    def save_data(bag: Bag) -> None:
        print(f'Saved flattened bag {bag.flatten()} to database')

    initial_bag = Bag()

    run([Sweep('x', [1, 2, 3], set_x, prepare_x),
         Sweep('y', [4, 5, 6], set_y, prepare_y)
         ],
        initial_bag,
        measure_v,
        save_data
        )


def test_deduct_bag_level_number():
    sweeps = [
        Sweep('x', [1, 2, 3], lambda bag: bag, lambda bag: None),
        Sweep('y', [4, 5, 6], lambda bag: bag, lambda bag: None)
    ]

    def deduct_levels(sweeps: List[Sweep], last_level: int) -> None:
        if len(sweeps) == 0:
            return
        else:
            sweep = sweeps[0]
            other_sweeps = sweeps[1:]

            new_level = last_level + 1

            print(f'Sweep for {sweep.param_name!r} should have a add '
                  f'function for a bag with at most {new_level} stack levels')

            deduct_levels(other_sweeps, new_level)

    deduct_levels(sweeps, 0)


def test_equivalent_sweeps():
    # 1

    def use_x(x):
        print(f'Setting x to {x}')

    def use_y(y):
        print(f'Setting y to {y}')

    def set_x(bag):
        use_x(bag.val_for("x"))
        print(f'    Bag is {bag}')
        return bag

    def set_y(bag):
        use_y(bag.val_for("y"))
        print(f'    Bag is {bag}')
        return bag

    sweeps = [
        Sweep('x', [1, 2, 3], set_x, lambda bag: None),
        Sweep('y', [4, 5, 6], set_y, lambda bag: None)
    ]

    # 2

    current_x = None
    current_y = None

    def set_xy(bag):
        nonlocal current_x, current_y

        new_x = bag.val_for('xy')[0]

        if current_x is None:
            current_x = new_x
            use_x(current_x)
        else:
            if new_x == current_x:
                pass
            else:
                current_x = new_x
                use_x(current_x)

        new_y = bag.val_for('xy')[1]

        if current_y is None:
            current_y = new_y
            use_y(current_y)
        else:
            if new_y == current_y:
                pass
            else:
                current_y = new_y
                use_y(current_y)

        print(f'    Bag is {bag}')

        return bag

    eq_sweeps = [
        Sweep('xy', list(product([1, 2, 3], [4, 5, 6])),
              set_xy, lambda bag: None)
    ]

    # compare

    def save_data(bag: Bag) -> None:
        print(f'Saved bag {bag} to database')

    run(sweeps, Bag(), lambda bag: bag, save_data)

    run(eq_sweeps, Bag(), lambda bag: bag, save_data)
