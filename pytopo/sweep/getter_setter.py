from functools import partial

from qcodes import Parameter


def _getter_setter(names_units, tp):
    def decorator(func):
        def inner():

            params = []
            for name, unit in names_units:
                kwargs = {
                    "name": name,
                    "unit": unit,
                    tp: func
                }
                params.append(Parameter(**kwargs))

            return params

        inner.is_getter_setter = True
        return inner
    return decorator

getter = partial(_getter_setter, tp="get_cmd")
setter = partial(_getter_setter, tp="set_cmd")
