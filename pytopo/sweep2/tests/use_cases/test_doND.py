from itertools import count

from ...core import Bag, Sweep, run


def test_do_1_d():
    """1D sweep case: sweep over x, measure y for each x"""
    # Set function for x

    x_set = []

    def set_x(bag: Bag) -> Bag:
        x = bag.val_for('x')

        x_set.append(x)

        return bag

    # Measure function for y

    y_measured = []

    counter = count(start=0, step=1)

    def measure_y(bag: Bag) -> Bag:
        y = next(counter)

        bag.add('y', y)

        y_measured.append(y)

        return bag

    # Save data function

    bags_saved = []

    def save_data(bag: Bag) -> None:
        bags_saved.append(bag.copy())

    # Setting up sweep and running it

    x_vals = [7, 8, 9]

    initial_bag = Bag()

    run([Sweep('x', x_vals, set_x),
         ],
        initial_bag,
        measure_y,
        save_data
        )

    # Important assertions

    x_expected = x_vals
    assert x_expected == x_set

    y_expected = list(range(len(x_vals)))
    assert y_expected == y_measured

    bags_expected = [[{'x': x, 'y': y}]
                     for x, y in zip(x_vals, y_expected)]
    assert bags_expected == bags_saved


def test_do_2_d():
    """
    2D sweep case: sweep over x, for each x sweep over y, for each y (and
    hence for each x) measure z
    """
    # Set function for x

    x_set = []

    def set_x(bag: Bag) -> Bag:
        x = bag.val_for('x')

        x_set.append(x)

        return bag

    # Set function for y

    y_set = []

    def set_y(bag: Bag) -> Bag:
        y = bag.val_for('y')

        y_set.append(y)

        return bag

    # Measure function for z

    z_measured = []

    counter = count(start=0, step=1)

    def measure_z(bag: Bag) -> Bag:
        z = next(counter)

        bag.add('z', z)

        z_measured.append(z)

        return bag

    # Save data function

    bags_saved = []

    def save_data(bag: Bag) -> None:
        bags_saved.append(bag.copy())

    # Setting up sweep and running it

    x_vals = [7, 8, 9]
    y_vals = [4, 5]

    initial_bag = Bag()

    run([Sweep('x', x_vals, set_x),
         Sweep('y', y_vals, set_y)
         ],
        initial_bag,
        measure_z,
        save_data
        )

    # Important assertions

    x_expected = x_vals
    assert x_expected == x_set

    y_expected = y_vals * len(x_vals)
    assert y_expected == y_set

    z_expected = list(range(len(x_vals) * len(y_vals)))
    assert z_expected == z_measured

    bags_expected = [[{'x': x}, {'y': y, 'z': z}]
                     for (x, y), z in zip([(x, y)
                                           for x in x_vals
                                           for y in y_vals
                                           ],
                                          z_expected)
                     ]
    assert bags_expected == bags_saved


def test_do_3_d():
    """
    3D sweep case: sweep over x, for each x sweep over y, for each y (and
    hence for each x) sweep over z, for each z (and hence for each x and y)
    measure a
    """
    # Set function for x

    x_set = []

    def set_x(bag: Bag) -> Bag:
        x = bag.val_for('x')

        x_set.append(x)

        return bag

    # Set function for y

    y_set = []

    def set_y(bag: Bag) -> Bag:
        y = bag.val_for('y')

        y_set.append(y)

        return bag

    # Set function for z

    z_set = []

    def set_z(bag: Bag) -> Bag:
        z = bag.val_for('z')

        z_set.append(z)

        return bag

    # Measure function for a

    a_measured = []

    counter = count(start=0, step=1)

    def measure_a(bag: Bag) -> Bag:
        a = next(counter)

        bag.add('a', a)

        a_measured.append(a)

        return bag

    # Save data function

    bags_saved = []

    def save_data(bag: Bag) -> None:
        bags_saved.append(bag.copy())

    # Setting up sweep and running it

    x_vals = [7, 8, 9]
    y_vals = [4, 5]
    z_vals = [42]

    initial_bag = Bag()

    run([Sweep('x', x_vals, set_x),
         Sweep('y', y_vals, set_y),
         Sweep('z', z_vals, set_z)
         ],
        initial_bag,
        measure_a,
        save_data
        )

    # Important assertions

    x_expected = x_vals
    assert x_expected == x_set

    y_expected = y_vals * len(x_vals)
    assert y_expected == y_set

    z_expected = z_vals * len(x_vals) * len(y_vals)
    assert z_expected == z_set

    a_expected = list(range(len(x_vals) * len(y_vals) * len(z_vals)))
    assert a_expected == a_measured

    bags_expected = [[{'x': x}, {'y': y}, {'z': z, 'a': a}]
                     for (x, y, z), a in zip([(x, y, z)
                                              for x in x_vals
                                              for y in y_vals
                                              for z in z_vals
                                              ],
                                             a_expected)
                     ]
    assert bags_expected == bags_saved
