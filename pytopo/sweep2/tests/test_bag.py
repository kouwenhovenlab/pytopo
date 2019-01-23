import pytest

from ..core import Bag, BagSection


def test_adding_sections():
    """
    Test that adding a new bag section to a bag means that a new
    dictionary is added to the end of the list of dictionaries
    """
    bag = Bag()

    assert [] == bag

    bag.append(BagSection())

    assert [{}] == bag

    bag.append(BagSection())

    assert [{}, {}] == bag


def test_adds_key_to_top_only():
    bag = Bag()
    bag.append(BagSection())

    bag.add('x', 1)
    assert [{'x': 1}] == bag

    bag.add('y', 3)
    assert [{'x': 1, 'y': 3}] == bag

    bag.append(BagSection())

    bag.add('z', 5)
    assert [{'x': 1, 'y': 3}, {'z': 5}] == bag


def test_finds_key_on_top_first():
    bag = Bag()

    bag.append(BagSection())
    bag.add('x', 1)
    bag.add('y', 3)

    bag.append(BagSection())
    bag.add('y', 42)

    assert 42 == bag.val_for('y')

    assert 1 == bag.val_for('x')


def test_error_for_unknown_key():
    bag = Bag()

    with pytest.raises(KeyError, match='x not found'):
        bag.val_for('x')

    bag.append(BagSection())

    with pytest.raises(KeyError, match='x not found'):
        bag.val_for('x')

    bag.add('y', 1)

    with pytest.raises(KeyError, match='x not found'):
        bag.val_for('x')

    bag.append(BagSection())

    with pytest.raises(KeyError, match='x not found'):
        bag.val_for('x')

    bag.add('z', 21)

    with pytest.raises(KeyError, match='x not found'):
        bag.val_for('x')


def test_removes_key_from_top_first():
    bag = Bag()

    bag.append(BagSection())
    bag.add('x', 1)
    bag.add('y', 3)

    bag.append(BagSection())
    bag.add('y', 42)

    assert [{'x': 1, 'y': 3}, {'y': 42}] == bag

    bag.remove_for('y')
    assert [{'x': 1, 'y': 3}, {}] == bag

    bag.remove_for('y')
    assert [{'x': 1}, {}] == bag


def test_error_for_removing_key():
    bag = Bag()

    with pytest.raises(KeyError, match='x not found'):
        bag.remove_for('x')

    bag.append(BagSection())

    with pytest.raises(KeyError, match='x not found'):
        bag.remove_for('x')

    bag.add('y', 1)

    with pytest.raises(KeyError, match='x not found'):
        bag.remove_for('x')

    bag.append(BagSection())

    with pytest.raises(KeyError, match='x not found'):
        bag.remove_for('x')

    bag.add('z', 21)

    with pytest.raises(KeyError, match='x not found'):
        bag.remove_for('x')


def test_flatten():
    bag = Bag()

    assert {} == bag.flatten()

    bag.append(BagSection())

    assert {} == bag.flatten()

    bag.add('x', 1)

    assert {'x': 1} == bag.flatten()

    bag.add('y', 2)

    assert {'x': 1, 'y': 2} == bag.flatten()

    bag.append(BagSection())

    assert {'x': 1, 'y': 2} == bag.flatten()

    bag.add('z', 3)

    assert {'x': 1, 'y': 2, 'z': 3} == bag.flatten()

    bag.remove_for('y')

    assert {'x': 1, 'z': 3} == bag.flatten()
