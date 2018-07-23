from functools import partial

from qcodes import Parameter


def _getter_setter(tp, name, unit):
    def decorator(func):
        def inner():

            kwargs = {
                "name": name,
                "unit": unit,
                tp: func
            }
            return Parameter(**kwargs)
        return inner
    return decorator

getter = partial(tp="get_cmd")
setter = partial(tp="set_cmd")
