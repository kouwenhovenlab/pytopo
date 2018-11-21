from typing import TypeVar, Callable, Tuple
from typing_extensions import Protocol
from qcodes.math.field_vector import FieldVector

T = TypeVar('T')

class GettableParameter(Protocol[T]):
    def __call__(self) -> T:
        pass

class SettableParameter(Protocol[T]):
    def __call__(self, value : T) -> None:
        pass

class ParameterProtocol(GettableParameter[T], SettableParameter[T], Protocol[T]):
    pass

class HasField(Protocol):
    field_measured : GettableParameter[FieldVector]

class ControlsField(HasField, Protocol):
    field_target : SettableParameter[FieldVector]
    field_ramp_rate : ParameterProtocol[FieldVector]
    
    def ramp(self) -> None:
        pass
