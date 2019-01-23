from itertools import count
from ...core import Bag, Sweep, run


def test_measure_on_1_d_in_2_d_sweep():
    """
    2D sweep with measure functions after the first dimensions and the
    second dimension as well: for each x, measure a, and also
    for each y (and hence each x) measure b
    """
    # Set function for x

    x_set = []

    def set_x(bag: Bag) -> Bag:
        x = bag.val_for('x')

        x_set.append(x)

        return bag

    # Measure function for a

    a_measured = []

    counter_a = count(start=0, step=1)

    def measure_a(bag: Bag) -> Bag:
        a = next(counter_a)

        bag.add('a', a)

        a_measured.append(a)

        return bag

    # Set x and measure a functions combined

    def set_x_and_measure_a(bag: Bag) -> Bag:
        bag_after_set = set_x(bag)
        bag_after_measure = measure_a(bag_after_set)
        return bag_after_measure

    # Set function for y

    y_set = []

    def set_y(bag: Bag) -> Bag:
        y = bag.val_for('y')

        y_set.append(y)

        return bag

    # Measure function for b

    b_measured = []

    counter_b = count(start=10, step=1)

    def measure_b(bag: Bag) -> Bag:
        b = next(counter_b)

        bag.add('b', b)

        b_measured.append(b)

        return bag

    # Save data function

    bags_saved = []

    def save_data(bag: Bag) -> None:
        bags_saved.append(bag.copy())

    # Setting up sweep and running it

    x_vals = [7, 8, 9]
    y_vals = [4, 5]

    initial_bag = Bag()

    run([Sweep('x', x_vals, set_x_and_measure_a),
         Sweep('y', y_vals, set_y)
         ],
        initial_bag,
        measure_b,
        save_data)

    # Important assertions

    x_expected = x_vals
    assert x_expected == x_set

    y_expected = y_vals * len(x_vals)
    assert y_expected == y_set

    a_expected = list(range(len(x_vals)))
    assert a_expected == a_measured

    b_expected = list(range(10, 10 + len(x_vals) * len(y_vals), 1))
    assert b_expected == b_measured

    bags_expected = [[{'x': x, 'a': a}, {'y': y, 'b': b}]
                     for ((x, a), y), b in zip([((x, a), y)
                                                for x, a in zip(x_vals,
                                                                a_expected)
                                                for y in y_vals],
                                               b_expected)
                     ]
    assert bags_expected == bags_saved
