from collections import defaultdict
from functools import wraps

import numpy

from pytopo.sweep import setter, sweep, measure, getter, chain


def test_adaptive_freq_fit():
    """
    This test simulates the use case of an adaptive sweep experiment. The
    point of it is that there is one experiment results of which are fed into
    a fitting routine, results of which are used to set some value, and then
    a second measurement is performed the data from which is the main purpose
    of the whole experiment.

    so = \
        sweep(set_x_0, fit_x(
                sweep(set_freq, [...])(
                    measure(get_x)
                )
                )
        )(
            sweep(set_g, [...])(
                measure(get_y)
            )
        )
    """

    # Let's first define the inner sweep object that returns the data that
    # shall be used for the fit

    freq = 0

    @setter(('freq', 'Hz'))
    def set_freq(freq_val):
        nonlocal freq
        freq = freq_val

    @getter(('x', 'V'))
    def get_x():
        return freq*2

    freq_values = numpy.array([1, 2])

    so1 = sweep(set_freq, freq_values)(
        measure(get_x)
    )

    assert [{'freq': f, 'x': x}
            for f, x in zip(freq_values, freq_values*2)] == list(so1)

    # Now let's see how we can define a function that performs a fit of data
    # that a given sweep object spits out

    def empty_decorator(fun):
        return fun
    sink = empty_decorator

    @sink
    def fit_x(so):
        """
        This sink takes a sweep object that measures freq and x, so that this
        sink can perform a fit, and return the value.
        """
        data = defaultdict(list)
        for item in so:
            for k, v in item.items():
                data[k].append(v)

        x_fit = max(data['x'])

        x_fit = numpy.atleast_1d(x_fit).tolist()  # this is needed to make
        # this function be consumable as a setpoint function (i.e. it has to
        # return an iterable)

        return x_fit

    assert [max(freq_values)*2] == fit_x(so1)

    # Let's see how to use that sink. For example, lets use the value that is
    # returns as an iterable to sweep on with the sweep convenience

    x_0 = 0

    @setter(('x_0', 'V'))
    def set_x_0(x_0_val):
        nonlocal x_0
        x_0 = x_0_val

    so11 = sweep(set_x_0, fit_x(so1))

    assert [{'x_0': max(freq_values)*2}] == list(so11)

    assert max(freq_values) * 2 == x_0

    # Now let's wrap that "sink" into another sweep object that is supposed
    # to use that sink

    g = 0

    @setter(('g', 'V'))
    def set_g(g_val):
        nonlocal g
        g = g_val

    @getter(('y', 'ns'))
    def get_y():
        return g * 3 + x_0

    g_values = numpy.array([5, 6])

    so2 = \
        sweep(set_x_0, fit_x(so1))(
            sweep(set_g, g_values)(
                measure(get_y)
            )
        )

    assert [{'x_0': x_0, 'g': g, 'y': y}
            for g, y in zip(g_values, g_values * 3 + x_0)] == list(so2)
