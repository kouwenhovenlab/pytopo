from collections import OrderedDict

import numpy as np
from qcodes.dataset.sqlite_base import get_dependents, get_layout, \
    get_dependencies


def get_structure(ds):
    structure = OrderedDict({})

    # for each data param (non-independent param)
    for dependent_id in get_dependents(ds.conn, ds.run_id):

        # get name etc.
        layout = get_layout(ds.conn, dependent_id)
        name = layout['name']
        structure[name] = {'unit': layout['unit']}
        structure[name]['dependencies'] = []

        # find dependencies (i.e., axes) and
        # add their names/units in the right order
        dependencies = get_dependencies(ds.conn, dependent_id)
        for dep_id, iax in dependencies:
            dep_layout = get_layout(ds.conn, dep_id)
            dep_struct = {'name': dep_layout['name'],
                          'unit': dep_layout['unit']}
            structure[name]['dependencies'].insert(iax, dep_struct)

    return structure


def get_axes_from_dataset(ds, param_name):
    struct = get_structure(ds)
    axes_names = []
    axes_vals = []

    if type(param_name) == list:
        param_name = param_name[0]

    axes_info = struct[param_name]['dependencies']
    for ax in axes_info:
        n = "{}".format(ax['name'])
        if ax['unit'] != '':
            n += " ({})".format(ax['unit'])

        v = np.array(ds.get_values(n)).reshape(-1)

        axes_names.append(n)
        axes_vals.append(v)

    return axes_names, axes_vals
