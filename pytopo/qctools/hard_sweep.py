from typing import Dict, Tuple, List, Union, Sequence, Optional

import numpy as np

import qcodes as qc
from qcodes.dataset.data_set import new_data_set
from qcodes.instrument.base import Instrument
from qcodes.dataset.measurements import Measurement, ParamSpec


def _param_list(params, convert_to_string=True):
    if convert_to_string:
        return [str(p) for p in params]
    else:
        return params


# def make_paramspec(param, paramtype='numeric', depends_on=[]):
#     return ParamSpec(name=str(param), paramtype=paramtype,
#                      label=param.label, unit=param.unit,
#                      depends_on=[str(p) for p in depends_on])


# def configure_dataset(ds, hard_sweep_detector=None, soft_sweep_params=[], soft_data_params=[]):
#     for p in soft_sweep_params:
#         ds.add_parameter(make_paramspec(p))
#     for p in soft_data_params:
#         ds.add_parameter(make_paramspec(p, depends_on=soft_sweep_params))
#     if hard_sweep_detector is not None:
#         for p in hard_sweep_detector.sweep_params:
#             ds.add_parameter(make_paramspec(p, paramtype='array'))
#         for p in hard_sweep_detector.data_params:
#             ds.add_parameter(make_paramspec(p, paramtype='array',
#                                             depends_on=hard_sweep_detector.sweep_params + soft_sweep_params))
#     return ds


# def make_dataset(name='', exp_id=None, **kw):
#     ds = new_data_set(name)
#     return configure_dataset(ds, **kw)


# def configure_measurement(m, hard_sweep_detector=None, soft_sweep_params=[], soft_data_params=[]):
#     for p in soft_sweep_params:
#         m.register_parameter(p)
#     for p in soft_data_params:
#         m.register_parameter(p, setpoints=soft_sweep_params)
#     if hard_sweep_detector is not None:
#         for p in hard_sweep_detector.sweep_params:
#             m.register_parameter(p)
#         for p in hard_sweep_detector.data_params:
#             m.register_parameter(p, setpoints=soft_sweep_params + hard_sweep_detector.sweep_params)
#     return m


# def make_measurement(name='', exp=None, **kw):
#     write_period = kw.pop('write_period', 5)

#     m = Measurement(exp=exp)
#     m.write_period = write_period
#     m.name = name

#     m = configure_measurement(m, **kw)
#     return m


class HardSweep(Instrument):

    def __init__(self, name: str, sweep_dims: Sequence, **kw):

        self.sweep_dims = sweep_dims
        self.sweep_units = kw.pop('sweep_units', ['' for d in self.sweep_dims])
        self.sweep_shape = None

        super().__init__(name, **kw)

        self.sweep_params = []
        for i, n in enumerate(self.sweep_dims):
            self.add_parameter(n, set_cmd=None, unit=self.sweep_units[i],
                               snapshot_value=False)
            self.sweep_params.append(getattr(self, n))

        self._meta_attrs = ['sweep_dims', 'sweep_shape', 'sweep_units']

    def setup(self):
        self.sweep_shape = tuple([len(p()) for p in self.sweep_params])

    def get_sweep_grid(self):
        return np.meshgrid( *[p() for p in self.sweep_params], indexing='ij')

    def get_sweep_coord_zip(self):
        return list(zip(*[s.reshape(-1) for s in self.get_sweep_grid()]))

    def get_sweep_coords(self, params_as_strings=True):
        return list(zip(_param_list(self.sweep_params, params_as_strings),
                        [s.reshape(-1) for s in self.get_sweep_grid()]))


class HardSweepDetector(Instrument):

    def __init__(self, name: str, inner_dims: Sequence,
                 sweeper: Optional[HardSweep]=None, **kw):

        self.inner_dims = inner_dims
        self.inner_units = kw.pop('inner_units', ['' for d in self.inner_dims])
        self.data_params = []
        self.inner_shape = None
        self.sweep_shape = None
        self.sweep_dims = inner_dims

        super().__init__(name, **kw)

        self.set_sweeper(sweeper)

        self.add_parameter('soft_average', set_cmd=None)

        self.inner_params = []
        for i, n in enumerate(self.inner_dims):
            self.add_parameter(n, set_cmd=None, unit=self.inner_units[i],
                               snapshot_value=False)
            self.inner_params.append(getattr(self, n))

        self._meta_attrs = ['inner_dims', 'inner_shape', 'inner_units',
            'sweep_dims', 'sweep_shape', 'sweep_units']

    def set_sweeper(self, swp):
        self.sweeper = swp

    def setup(self):
        self.inner_shape = tuple([len(p()) for p in self.inner_params])
        self.sweep_shape = [] if self.sweeper is None else list(self.sweeper.sweep_shape).copy()
        self.sweep_shape += self.inner_shape
        self.sweep_shape = tuple(self.sweep_shape)

        self.sweep_dims = [] if self.sweeper is None else self.sweeper.sweep_dims.copy()
        self.sweep_dims += self.inner_dims

        self.sweep_units = [] if self.sweeper is None else self.sweeper.sweep_units.copy()
        self.sweep_units += self.inner_units

        self.sweep_params = [] if self.sweeper is None else self.sweeper.sweep_params.copy()
        self.sweep_params += self.inner_params

    def get_inner_grid(self):
        return np.meshgrid( *[p() for p in self.inner_params], indexing='ij')

    def get_inner_coords(self, params_as_strings=False):
        return list(zip(_param_list(self.inner_params, params_as_strings),
                        [s.reshape(-1).astype(float) for s in self.get_inner_grid()]))

    def get_sweep_grid(self):
        return np.meshgrid( *[p() for p in self.sweep_params], indexing='ij')

    def get_sweep_coords(self, params_as_strings=False):
        return list(zip(_param_list(self.sweep_params, params_as_strings),
                    [s.reshape(-1).astype(float) for s in self.get_sweep_grid()]))

    def get_sweep_coords_for_ds(self):
        return self.get_sweep_coords(True)

    def get_data_params(self, params_as_strings=False):
        return list(zip(_param_list(self.data_params, params_as_strings),
                    [p().reshape(-1).astype(float) for p in self.data_params]))

    def get_data_params_for_ds(self):
        return self.get_data_params(True)

    def get_all(self, params_as_strings=False):
        return self.get_sweep_coords(params_as_strings) + self.get_data_params(params_as_strings)
