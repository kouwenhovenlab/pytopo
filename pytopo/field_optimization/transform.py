from .typing import ParameterProtocol, HasField, ControlsField
from qcodes import Parameter
from qcodes.math.field_vector import FieldVector
import numpy as np
from typing import Optional, Type, TypeVar
T = TypeVar('T')

## Transform matrices ##

def rescale(x_scale : float, y_scale : float, z_scale : float
        ) -> np.ndarray:
    return np.diag([x_scale, y_scale, z_scale, 1])

def rotate_x(angle : float) -> np.ndarray:
    c = np.cos(angle)
    s = np.sin(angle)
    return np.array([
        [ 1,  0,  0],
        [ 0,  c, -s],
        [ 0,  s,  c]
    ])

def rotate_y(angle : float) -> np.ndarray:
    c = np.cos(angle)
    s = np.sin(angle)
    return np.array([
        [ c,  0,  s],
        [ 0,  1,  0],
        [-s,  0,  c]
    ])

def rotate_z(angle : float) -> np.ndarray:
    c = np.cos(angle)
    s = np.sin(angle)
    return np.array([
        [ c, -s,  0],
        [ s,  c,  0],
        [ 0,  0,  1]
    ])

def shift(offset : FieldVector) -> np.ndarray:
    mtx = np.eye(4)
    mtx[:, -1] = offset.as_homogeneous()
    return mtx

def _normalize_transform(transform : Optional[np.ndarray]) -> np.ndarray:
    transform = transform if transform is not None else np.eye(4)
    # If we were given a 3x3 matrix, extend to homogeneous coordinates.
    if transform.shape[0] == 3 and transform.shape[1] == 3:
        transform = np.block([
            [transform, np.zeros((3, 1))],
            [np.zeros((1, 3)), np.ones((1, 1))]
        ])

    # Check if the transformation matrix is singular.
    if np.abs(np.linalg.det(transform)) <= 1e-10:
        raise ValueError("Transformation matrix cannot be singular.")

    return transform

class Transformable(object):
    def rescale(self : T,
                 x_scale : float, y_scale : float, z_scale : float
                ) -> T:
        return self._build(rescale(x_scale, y_scale, z_scale))

    def rotate_x(self : T, angle : float) -> T:
        return self._build(rotate_x(angle))

    def rotate_x_deg(self : T, angle : float) -> T:
        return self.rotate_x(np.degrees(angle))

    def rotate_y(self : T, angle : float) -> T:
        return self._build(rotate_y(angle))

    def rotate_y_deg(self : T, angle : float) -> T:
        return self.rotate_y(np.degrees(angle))

    def rotate_z(self : T, angle : float) -> T:
        return self._build(rotate_z(angle))
        
    def rotate_z_deg(self : T, angle : float) -> T:
        return self.rotate_z(np.degrees(angle))

    def shift(self : T, offset : FieldVector) -> T:
        return self._build(shift(offset))

# The __new__ method causes all sorts of confusion, so we make a function that
# pretends to be a class.
def TransformedFieldParameter(param):
    return _TransformedFieldParameter.from_param(param)

class _TransformedFieldParameter(Parameter, Transformable):
    """
    Args:

    """
    _underlying_parameter : ParameterProtocol[FieldVector]
    _transform : np.ndarray
    _inverse : np.ndarray

    def __new__(cls, name : str, *args,
                underlying_parameter : ParameterProtocol[FieldVector],
                transform : Optional[np.ndarray] = None,
                **kwargs
               ):

        transform = _normalize_transform(transform)
        
        # If the underlying parameter is already a transformed parameter,
        # collapse the two together rather than chaining calls.
        if isinstance(underlying_parameter, _TransformedFieldParameter):
            transform = transform @ underlying_parameter._transform
            underlying_parameter = underlying_parameter._underlying_parameter
        
        inverse = np.linalg.inv(transform)


        def _get() -> FieldVector:
            orig = underlying_parameter()
            return type(orig).from_homogeneous(transform @ orig.as_homogeneous())

        def _set(field : FieldVector):
            transformed = inverse @ field.as_homogeneous()
            underlying_parameter(FieldVector.from_homogeneous(transformed))

        param = super(_TransformedFieldParameter, cls).__new__(cls)
        Parameter.__init__(param, name, *args, get_cmd=_get, set_cmd=_set, **kwargs)
        param._underlying_parameter = underlying_parameter
        param._transform = transform
        param._inverse = inverse
        return param

    def __init__(self, name, underlying_parameter, transform=None):
        # We handled everything in __new__.
        pass

    def _build(self : T, mtx : np.ndarray) -> T:
        return type(self)(name=self.name, underlying_parameter=self, transform=mtx)
        
    @classmethod
    def from_param(cls : Type[T], param : Parameter, transform : Optional[np.ndarray] = None) -> T:
        name = getattr(param, 'name', 'param')
        return cls(
            name,
            underlying_parameter=param,
            transform=transform
        )


class TransformedController(ControlsField, Transformable):    
    _underlying_controller : ControlsField
    _transform : np.ndarray
    _inverse : np.ndarray

    def _build(self : T, mtx : np.ndarray) -> T:
        return type(self)(self, mtx)

    def __init__(self,
                 underlying_controller : ControlsField,
                 transform : Optional[np.ndarray] = None
                ):

        transform = _normalize_transform(transform)
        self.field_target = _TransformedFieldParameter.from_param(
            underlying_controller.field_target, transform
        )
        self.field_measured = _TransformedFieldParameter.from_param(
            underlying_controller.field_measured,
            transform
        )
        # DON'T TRANSFORM THE RAMP RATE
        self.field_ramp_rate = underlying_controller.field_ramp_rate
        self.ramp = underlying_controller.ramp

_TransformedFieldParameter.__name__ = _TransformedFieldParameter.__name__[1:]
