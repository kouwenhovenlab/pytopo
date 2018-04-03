import os
import time
import numpy as np
import qcodes as qc
import pandas as pd

from collections import OrderedDict
from pandas.core.indexes.multi import MultiIndex

from qcodes import load_by_id
from qcodes.dataset.data_set import DataSet
from qcodes.dataset.sqlite_base import transaction, one, get_dependencies, get_dependents, get_layout

# TODO
# * documentation
# * specify axis order
# * how to split up multidimensional data?
# * include experiment/sample into data name?
# * run_ids are not strictly unique -- need a mechanism to prevent overwriting files
#   (add time stamp or so if file exists)

def get_timestamp(run_id):
    DB = qc.config["core"]["db_location"]

    d = DataSet(DB)
    sql = """
    SELECT run_timestamp
    FROM
      runs
    WHERE
      run_id= ?
    """
    c = transaction(d.conn, sql, run_id)
    run_timestamp = one(c, 'run_timestamp')
    return run_timestamp


def timestamp_to_fmt(ts, fmt):
    return time.strftime(fmt, time.gmtime(ts))


def get_basepath(run_id, pathspec, make_path=True):
    ts = get_timestamp(run_id)
    path = timestamp_to_fmt(ts, pathspec)
    if not os.path.exists(path):
        os.makedirs(path)

    return os.path.join(path, str(run_id).zfill(4))


def get_data_export_path(run_id, suffix=''):
    try:
        base = qc.config['user']['data_export_dir']
    except KeyError:
        base = os.path.join(os.getcwd(), 'data')
    basepath = get_basepath(run_id, base)

    if suffix == '' or suffix[0] == '.':
        return basepath + suffix
    else:
        return basepath + '_' + suffix


def get_structure(ds):
    structure = OrderedDict({})

    # for each data param (non-independent param)
    for dependent_id in get_dependents(ds.conn, ds.run_id):

        # get name etc.
        layout = get_layout(ds.conn, dependent_id)
        name = layout['name']
        structure[name] = {'unit' : layout['unit']}
        structure[name]['dependencies'] = []

        # find dependencies (i.e., axes) and add their names/units in the right order
        dependencies = get_dependencies(ds.conn, dependent_id)
        for dep_id, iax in dependencies:
            dep_layout = get_layout(ds.conn, dep_id)
            dep_struct = {'name' : dep_layout['name'], 'unit' : dep_layout['unit']}
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


def get_data_dict_from_dataset(ds, param_names):
    struct = get_structure(ds)
    if type(param_names) == str:
        param_names = [param_names]

    axes = struct[param_names[0]]['dependencies']
    data = OrderedDict({})

    for pn in param_names:
        if struct[pn]['dependencies'] != axes:
            raise ValueError('All parameters given need to have the same dependencies.')

        data[pn] = np.array(ds.get_values(pn)).reshape(-1)

    return data


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


def write_spyview_meta(fn, axes_names, axes_vals, col_names):
    naxes = len(axes_names)
    ncols = len(col_names)

    with open(fn, 'w') as f:
        for i, n, vals in zip(range(naxes), axes_names, axes_vals):
            v0, v1 = vals[0], vals[-1]
            f.write("{}\n{}\n{}\n{}\n".format(vals.size, v0, v1, n))

        for i in range(3 - naxes):
            f.write("{}\n{}\n{}\n{}\n".format(1,0,0,'None'))

        for i, n in zip(range(naxes+1, naxes+1+ncols), col_names):
            f.write("{}\n{}\n".format(i, n))


def export_dataset_to_spyview(ds, param_names, fn=None):
    if type(param_names) == str:
        param_names = [param_names]

    if fn is None:
        fn = get_data_export_path(ds.run_id, suffix=",".join(param_names).replace(' ', '_') + '.dat')

    meta_fn = os.path.splitext(fn)[0] + '.meta.txt'
    df = dataset_to_data_frame(ds, param_names)
    mi = df.index

    axes_names, axes_vals = list(mi.names), list(mi.levels)
    new_block_indicator = axes_vals[0][0]

    write_spyview_meta(meta_fn, axes_names, axes_vals, param_names)

    df2 = df.reset_index()
    with open(fn, 'w') as f:
        for i in range(len(df2)):
            if i != 0 and df2[df2.columns[0]][i] == new_block_indicator:
                f.write("\n")

            line = "\t".join(["{}".format(float(df2[k][i])) for k in df2.columns]) + "\n"
            f.write(line)

class SpyviewExporter:

    def __init__(self, dataset, param_names, fn=None):
        if type(param_names) == str:
            param_names = [param_names]

        if fn is not None:
            self.fn = fn
        else:
            self.fn = get_data_export_path(dataset.run_id,
                                           suffix=",".join(param_names).replace(' ', '_') + '.dat')

        self.meta_fn = os.path.splitext(self.fn)[0] + '.meta.txt'
        self.param_names = param_names

        self.ds = dataset
        self.ds_structure = self._get_ds_structure()
        self.ds_parameters = self.ds.get_parameters()
        self.axes_names, _ = get_axes_from_dataset(self.ds, param_names[0])

        axes = self.ds_structure[param_names[0]]['dependencies']
        for pn in param_names:
            if self.ds_structure[pn]['dependencies'] != axes:
                raise ValueError('All parameters given need to have the same dependencies.')

        self.df_cols = self.axes_names + self.param_names
        self.axes_vals = OrderedDict({n: np.array([]) for n in self.axes_names})
        self.new_block_indicator = None
        self.new_file = True

    def _get_ds_structure(self):
        return get_structure(self.ds)

    def _results_to_df(self, results):
        data = {}
        for p, vals in zip(self.ds_parameters, zip(*results)):
            if p.name in self.df_cols:
                data[p.name] = np.array(vals)

        return pd.DataFrame(data)

    def write_meta_file(self):
        write_spyview_meta(self.meta_fn, self.axes_names,
                           [v for (k, v) in self.axes_vals.items()], self.param_names)

    def __call__(self, results, length, state=None):
        df = self._results_to_df(results)

        if self.new_block_indicator is None:
            self.new_block_indicator = df[self.axes_names[0]][0]
        for n in self.axes_names:
            self.axes_vals[n] = np.unique(np.append(self.axes_vals[n], df[n]))
            # print(self.axes_vals)
        self.write_meta_file()

        with open(self.fn, 'a') as f:
            for i in range(len(df)):
                if not self.new_file and df[df.columns[0]][i] == self.new_block_indicator:
                    f.write("\n")
                line = "\t".join(["{}".format(float(df[k][i])) for k in df.columns]) + "\n"
                f.write(line)
                self.new_file = False
