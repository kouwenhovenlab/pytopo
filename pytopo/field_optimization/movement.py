import time
import numpy as np
from typing import Callable, Optional, TypeVar, Tuple, Union, Dict, Any
from typing_extensions import Final
from pytopo.field_optimization.typing import GettableParameter, HasField, ControlsField, ParameterProtocol
from qcodes.math.field_vector import FieldVector
from contextlib import contextmanager
import matplotlib.pyplot as plt

T = TypeVar('T')
Interval = Tuple[T, T]
OptionalExtra = Union[T, Tuple[T, Dict[str, Any]]]

IPYTHON : Final[bool] = '__IPYTHON__' in locals()
if IPYTHON:
    try:
        import ipywidgets as ipw
    except ImportError:
        ipw = None

    from IPython.display import display
else:
    ipw = None
    display = print


@contextmanager
def temporary_setting(parameter : ParameterProtocol[T], value : T) -> None:
    old_value = parameter()
    try:
        parameter(value)
        yield
    finally:
        parameter(old_value)

class FieldOptimizationProblem(object):
    """
    Represents optimization problems such as alignment of a magnetic field
    which require varying the parameters of a field controller.

    Args:
        instrument: A QCoDeS instrument that controls a magnetic
            field.
        objective: A gettable QCoDeS parameter that returns
            estimates of the value to be optimized.
        objective_uncertainty: A gettable QCoDeS parameter that returns
            estimates of the uncertainty in estimates of the
            objective.
    """

    instrument : ControlsField
    objective : GettableParameter[float]
    objective_uncertainty : Optional[GettableParameter[float]]

    def __init__(self,
                 instrument : ControlsField,
                 objective : GettableParameter[float],
                 objective_uncertainty : Optional[GettableParameter[float]]):
        self.instrument = instrument
        self.objective = objective
        self.objective_uncertainty = objective_uncertainty

    
    def set_field(self,
                  target_field : FieldVector,
                  n_steps : int = 10,
                  absolute : bool = True,
                  ramp_rate : float = 1e-3,
                  observer_fn : Optional[Callable[[FieldVector], None]] = None,
                  verbose : bool = False,
                  threshold : float = 1e-6
                 ) -> None:
        """
        Sets the field controlled by this problem's instrument to a
        given target field by taking small steps, measuring, and then
        updating the target accordingly.

        Args:
            target_field: The value of the field that should be set,
                or the difference between the current and target field
                if `absolute=True`.
            n_steps: The number of steps that should be taken in order
                to reach the given target.
            absolute: Indicates whether `target_field` is the target field,
                or a difference from the current field to the target.
            ramp_rate: A rate at which the field can be safely swept between
                points.
            observer_fn: A callable which gets called after each small step.
            threshold: If the norm of the difference between the current and
                target field is smaller than this value, no further steps
                will be taken.
        """
        if IPYTHON and ipw is not None:
            status = ipw.Label()
            def update(field : FieldVector):
                status.value = field.repr_spherical()
            def finish():
                status.value = "Move complete."
            display(status)
        else:
            def update(field : FieldVector):
                print(f'Magnet reached (r, phi, theta) = ({field.r}, {field.phi}, {field.theta})', end='\r')
            def finish():
                print("Move complete.")
        
        target = FieldVector()
        if absolute:
            target.copy(target_field)
        else:
            initial = self.instrument.field_measured()
            target = target_field + initial
            
        with temporary_setting(self.instrument.field_ramp_rate,
                            FieldVector(x=ramp_rate, y=ramp_rate, z=ramp_rate)):

            for step_amount in np.linspace(0, 1, n_steps + 1)[1:]:
                current = self.instrument.field_measured()
                intermediate_target = step_amount * (target - current) + current

                if (intermediate_target - current).norm() <= threshold:
                    print("Step threshold met, stopping move early.")
                    break
                
                if verbose:
                    print(f"Setting field target to {intermediate_target.repr_spherical()}")
                self.instrument.field_target(intermediate_target)
                self.instrument.ramp()

                time.sleep(0.1)
                current = self.instrument.field_measured()
                if observer_fn is not None:
                    observer_fn(current)
                update(current)
                time.sleep(0.1)

        finish()

    def optimize_at_fixed_magnitude(self,
                                    r : float,
                                    phi_range : Interval[float], n_phi : int,
                                    theta_range : Interval[float], n_theta : int,
                                    return_extra : bool = False,
                                    n_steps : int = 5,
                                    plot : bool = False,
                                    verbose : bool = False,
                                    ramp_rate : float = 1.5e-3
                                    ) -> OptionalExtra[FieldVector]:
        """
        Given the magnitude of a magnetic field, maximizes the objective
        over the spherical coordinates phi and theta by an exhaustive
        search.

        Args:
            r: The magnitude of the magnetic field to be optimized over
                angles.
            phi_range: The interval over which phi will be searched.
            n_phi: The number of distinct values of phi to be evaluated.
            theta_range: The interval over which theta will be searched.
            n_theta: The number of distinct values of theta to be evaluated.
            return_extra: If `True`, this method will return additional
                data as a dictionary.
            plot: If `True`, produces a plot of the path that this
                method took to find the optimal objective value.

        Returns:
            The optimal field found by an exhaustive seach.
            If `return_extra=True`, this method returns a tuple of the
            optimal field and a dictionary containing diagnostic data.
        """

        locations = []
        objectives_meas = []
        
        still_to_visit = [
            FieldVector(r=r, phi=phi, theta=theta)
            for phi in np.linspace(phi_range[0], phi_range[1], n_phi)
            for theta in np.linspace(theta_range[0], theta_range[1], n_theta)
        ]
        
        def observe(current_field : FieldVector):
            new_loc = FieldVector()
            new_loc.copy(current_field)
            locations.append(new_loc)
            objectives_meas.append(self.objective())
            
        while still_to_visit:
            # Find the nearest point.
            current = self.instrument.field_measured()
            nearest = min(still_to_visit, key=current.distance)
            still_to_visit.remove(nearest)
            print(f"Evaluating at phi = {nearest.phi}, theta = {nearest.theta}")
            self.set_field(
                nearest,
                absolute=True, n_steps=n_steps, ramp_rate=ramp_rate,
                observer_fn=observe,
                verbose=verbose
            )
            observe(self.instrument.field_measured())
            
        extra = {
            'objectives': objectives_meas,
            'field_vectors': locations
        }
        idx_flat_best = np.argmax(objectives_meas)
        optimum = FieldVector()
        optimum.copy(locations[idx_flat_best])

        # Renormalize to desired B.
        optimum['r'] = r
        
        # Move the field before returning.
        print(f"Found optimum for |B| = {r} at ({optimum.phi}, {optimum.theta}).")
        self.set_field(optimum, absolute=True)
        
        
        if plot:
            plt_xs = [vec.phi for vec in extra['field_vectors']]
            plt_ys = [vec.theta for vec in extra['field_vectors']]
            plt.figure()
            plt.plot(
                plt_xs,
                plt_ys,
            )
            plt.scatter(
                plt_xs,
                plt_ys,
                c=extra['objectives']
            )
            plt.colorbar()
        
        if return_extra:
            return optimum, extra
        else:
            return optimum

    def optimize_and_ramp_magnitude(self,
                                    initial_r : float, final_r : float, n_r_steps: int,
                                    initial_phi : float, phi_window : float, n_phis : int,
                                    initial_theta : float, theta_window : float, n_thetas : int,
                                    reoptimization_threshold : float = 0.5,
                                    n_steps : int = 5,
                                    ramp_rate : float = 1e-3,
                                    return_extra : bool = False,
                                    verbose : bool = False
                                   ) -> OptionalExtra[FieldVector]:
        """
        Ramps the magnitude of a magnetic field from a given start point,
        optimizing the objective by exhaustive search at each increment in
        field magnitude.

        Returns:
            The optimal field found by an exhaustive seach.
            If `return_extra=True`, this method returns a tuple of the
            optimal field and a dictionary containing diagnostic data.

        Args:
            initial_r: Initial magnitude of the magnetic field.
            final_r: Target magnitude of the magnetic field.
            n_r_steps: The number of steps to take in field magnitude.
            initial_phi: Initial value of phi to use in the exhaustive
                search at `initial_r`.
            phi_window: The size of the window around each value of phi
                to be searched.
            n_phis: The number of discrete values of phi to be searched
                at each field magnitude.
            initial_theta: Initial value of theta to use in the exhaustive
                search at `initial_r`.
            theta_window: The size of the window around each value of theta
                to be searched.
            n_thetas: The number of discrete values of theta to be searched
                at each field magnitude.
            reoptimization_threshold: If an increment in field magnitude
                changes the objective by more than this threshold, as
                scaled by the uncertainty, then an exhaustive search
                will be performed after incrementing. This is useful to
                avoid situations in which an objective value has changed
                by less than a "line width."
            return_extra: If `True`, this method will return additional
                data as a dictionary.

        Returns:
            The optimal field found by an exhaustive seach.
            If `return_extra=True`, this method returns a tuple of the
            optimal field and a dictionary containing diagnostic data.
        """

        extra = {}

        print("Moving to initial field vector...")
        self.set_field(FieldVector(r=initial_r, phi=initial_phi, theta=initial_theta), absolute=True)
        
        rs = np.linspace(initial_r, final_r, n_r_steps)
        
        # Find the FWHM, so that we can compare line widths.
        prev_objective = None
        prev_uncertainty = None

        objective_history = []
        optima_history = []
        
        for r in rs:
            print(f"Optimizing at |B| = {r}...")
            current = self.instrument.field_measured()
            self.set_field(
                FieldVector(r=r, theta=current.theta, phi=current.phi),
                absolute=True,
                n_steps=n_steps, ramp_rate=ramp_rate,
                verbose=verbose
            )
            
            current_objective = self.objective()
            current_uncertainty = self.objective_uncertainty()

            objective_history.append(current_objective)

            # Check if we can skip this iteration.
            # We force optimization at the final iteration.
            if self.objective_uncertainty is not None and r != rs[-1] and prev_objective is not None:
                scaled_distance = np.abs(current_objective - prev_objective) / np.mean([prev_uncertainty, current_uncertainty])
                if scaled_distance < reoptimization_threshold:
                    prev_objective = current_objective
                    prev_uncertainty = current_uncertainty
                    print(f"Within {reoptimization_threshold} line widths, not re-optimizing yet.")
                    continue
                else:
                    print(f"Current and previous objectives differ by {scaled_distance} line widths, thus re-optimizing.")
            
            current_best = self.optimize_at_fixed_magnitude(
                r,
                (current.phi - phi_window / 2, current.phi + phi_window / 2), n_phis,
                (current.theta - theta_window / 2, current.theta + theta_window / 2), n_thetas,
                ramp_rate=ramp_rate,n_steps=n_steps, verbose=verbose
            )
            optima_history.append(current_best)

            # Find the FWHM at the point optimized by align_at, and save
            # to "prev" so that it's ready for the next iteration.
            if self.objective_uncertainty is not None:
                prev_objective = current_objective
                prev_uncertainty = current_uncertainty

        
        if return_extra:
            extra['history'] = {
                'rs': rs,
                'objectives': objective_history,
                'optima': optima_history
            }
            return current_best, extra
        else:
            return current_best

