from collections import OrderedDict

import numpy as np

from pytopo.qctools.dataset_export._utils import get_structure


def get_data_dict_from_dataset(ds, param_names):
    struct = get_structure(ds)
    if type(param_names) == str:
        param_names = [param_names]

    axes = struct[param_names[0]]['dependencies']
    data = OrderedDict({})

    for pn in param_names:
        if struct[pn]['dependencies'] != axes:
            raise ValueError('All parameters given need to have '
                             'the same dependencies.')

        data[pn] = np.array(ds.get_values(pn)).reshape(-1)

    return data
