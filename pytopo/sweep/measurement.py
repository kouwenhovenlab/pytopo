from qcodes.dataset.measurements import Measurement
from pytopo.sweep.base import BaseSweepObject


class SweepMeasurement(Measurement):
    def register_sweep(self, sweep_object: BaseSweepObject) -> None:

        sweep_object.parameter_table.resolve_dependencies()
        param_specs = sweep_object.parameter_table.param_specs

        # We sort by the length of `depends_on_` of ParamSpec so that 
        # standalone parameters are registered first
        param_specs_sorted = sorted(param_specs,
                                    key=lambda p: len(p.depends_on_))

        for p in param_specs_sorted:
            self.register_custom_parameter(
                name=p.name,
                label=p.label,
                unit=p.unit,
                basis=p.inferred_from_,
                setpoints=p.depends_on_,
                paramtype=p.type)
