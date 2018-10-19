from collections import OrderedDict

import pandas as pd

from pytopo.qctools.dataset_export._utils import get_axes_from_dataset
from pytopo.qctools.dataset_export.datadict import get_data_dict_from_dataset


def dataset_to_data_frame(ds, param_names, multiindex=True):
    axes_names, axes_vals = get_axes_from_dataset(ds, param_names)
    data = get_data_dict_from_dataset(ds, param_names)

    if multiindex:
        mi = pd.MultiIndex.from_tuples(list(zip(*axes_vals)), names=axes_names)
        df = pd.DataFrame(data, index=mi)
    else:
        data2 = OrderedDict({})
        for n, v in zip(axes_names, axes_vals):
            data2[n] = v
        for n in data:
            data2[n] = data[n]
        df = pd.DataFrame(data2)

    return df
