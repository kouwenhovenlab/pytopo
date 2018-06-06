import numpy as np
from qcodes.dataset.measurements import Measurement

class MeasurementExt(Measurement):

    def __init__(self, station, exp=None,
                 hard_sweep_detector=None, soft_sweep_params=[], soft_data_params=[]):

        super().__init__(exp, station)

        self._params = {}
        self._hard_sweep_detector = None

        for p in soft_sweep_params:
            self.register_parameter(p)
            self._params[str(p)] = p

        for p in soft_data_params:
            self.register_parameter(p, setpoints=soft_sweep_params)
            self._params[str(p)] = p

        if hard_sweep_detector is not None:
            self._hard_sweep_detector = hard_sweep_detector
            for p in hard_sweep_detector.sweep_params:
                self.register_parameter(p)
            for p in hard_sweep_detector.data_params:
                self.register_parameter(p, setpoints=soft_sweep_params + hard_sweep_detector.sweep_params)

    def get_result(self, **kw):
        result = []
        if self._hard_sweep_detector is not None:
            result = self._hard_sweep_detector.get_all()

        for n, p in self._params.items():
            if p in kw:
                value = kw[p]
            else:
                value = p()
            if isinstance(value, np.ndarray):
                value = value.reshape(-1)
            result.append((p, value))

        return result
