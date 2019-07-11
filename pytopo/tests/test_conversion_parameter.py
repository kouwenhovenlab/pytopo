import pytest
from qcodes import Parameter

from pytopo.parameters import ConversionParameter


def test_init():
    """
    Test that the lable and unit get used from source parameter if not
    specified otherwise.
    """
    p = Parameter('testparam', set_cmd=None, get_cmd=None,
                  label='Test Parameter', unit='V')
    c = ConversionParameter('test_conversion_parameter', p,
                            lambda x: x)
    assert c.label == p.label
    assert c.unit == p.unit

    c = ConversionParameter('test_conversion_parameter', p,
                            lambda x: x, unit='Ohm')
    assert c.label == p.label
    assert not c.unit == p.unit
    assert c.unit == 'Ohm'


def test_get_set_raises():
    """
    Test that providing a get/set_cmd kwarg raises an error.
    """
    p = Parameter('testparam', set_cmd=None, get_cmd=None)
    for kwargs in ({'set_cmd': None}, {'get_cmd': None}):
        with pytest.raises(KeyError) as e:
            ConversionParameter('test_conversion_parameter', p,
                                lambda x: x, **kwargs)
        assert str(e.value).startswith('\'It is not allowed to set')


def test_no_set_conversion():
    p = Parameter('testparam', set_cmd=None, get_cmd=None)
    c = ConversionParameter('test_conversion_parameter', p,
                            lambda x: x)
    with pytest.raises(NotImplementedError,
                       match="No set conversion implemented."):
        c.set(25)


def test_with_set_conversion():
    p = Parameter('testparam', set_cmd=None, get_cmd=None)
    c = ConversionParameter('test_conversion_parameter', p,
                            lambda x: x, set_conv=lambda x: x*2,
                            unit='V')
    new_value = 25
    c.set(new_value)
    assert new_value*2 == p.get_latest()
    assert new_value == c.get_latest()


def test_with_set_conversion_and_initial_value_given():
    value = 36
    p = Parameter('testparam', set_cmd=None, get_cmd=None)
    c = ConversionParameter('test_conversion_parameter', p,
                            lambda x: x, set_conv=lambda x: x*2,
                            initial_value=value)
    assert value*2 == p.get_latest()
    assert value == c.get_latest()


def test_snapshot():
    p = Parameter('testparam', set_cmd=None, get_cmd=None)

    def divide_by_2(x):
        return x/2

    c = ConversionParameter('test_delegate_parameter', p,
                            lambda x: x*2, set_conv=divide_by_2,
                            initial_value=2)

    snapshot = c.snapshot()
    source_parameter_snapshot = snapshot.pop('source_parameter')
    assert source_parameter_snapshot == p.snapshot()

    assert snapshot['value'] == 2
    assert source_parameter_snapshot['value'] == 1.0

    assert divide_by_2.__name__ in snapshot['set_conversion']
    assert 'lambda' in snapshot['get_conversion']
