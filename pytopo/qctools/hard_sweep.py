from typing import Dict, Tuple, List, Union, Sequence, Optional

import numpy as np

import qcodes as qc
from qcodes.instrument.base import Instrument


def _param_list(params, convert_to_string=True):
    if convert_to_string:
        return [str(p) for p in params]
    else:
        return params


class HardSweep(Instrument):

    def __init__(self, name: str, sweep_dims: Sequence, **kw):

        self.sweep_dims = sweep_dims
        self.sweep_units = kw.pop('sweep_units', ['' for d in self.sweep_dims])

        super().__init__(name, **kw)

        self.sweep_params = []
        for i, n in enumerate(self.sweep_dims):
            self.add_parameter(n, set_cmd=None, unit=self.sweep_units[i],
                               snapshot_value=False)
            self.sweep_params.append(getattr(self, n))

        self._meta_attrs = ['sweep_dims']

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

        super().__init__(name, **kw)

        self.set_sweeper(sweeper)

        self.inner_params = []
        for i, n in enumerate(self.inner_dims):
            self.add_parameter(n, set_cmd=None, unit=self.inner_units[i],
                               snapshot_value=False)
            self.inner_params.append(getattr(self, n))

        self._meta_attrs = ['inner_dims']

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

    def get_inner_coord_zip(self):
        return list(zip(*[s.reshape(-1) for s in self.get_inner_grid()]))

    def get_inner_coords(self, params_as_strings=True):
        return list(zip(_param_list(self.inner_params, params_as_strings),
                        [s.reshape(-1) for s in self.get_inner_grid()]))

    def get_sweep_grid(self):
        return np.meshgrid( *[p() for p in self.sweep_params], indexing='ij')

    def get_sweep_coord_zip(self):
        return list(zip(*[s.reshape(-1) for s in self.get_sweep_grid()]))

    def get_sweep_coords(self, params_as_strings=True):
        return list(zip(_param_list(self.sweep_params, params_as_strings),
                    [s.reshape(-1) for s in self.get_sweep_grid()]))
