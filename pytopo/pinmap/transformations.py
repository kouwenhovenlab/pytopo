from pytopo.pinmap.pin import Pin


class Transformation:
    """
    Interface for defining how value is propagated forward and backward

    TODO:
    * should it work on value or on Parameter or Pin?
    """
    def __init__(self):
        super().__init__()

    def forward(self, value):
        raise NotImplemented

    def backward(self, value):
        raise NotImplemented


class UnityTransformation(Transformation):
    def __init__(self):
        super().__init__()

    def forward(self, value):
        return value

    def backward(self, value):
        return value


class AddOneTransformation(Transformation):
    def __init__(self):
        super().__init__()

    def forward(self, value):
        return value + 1

    def backward(self, value):
        return value - 1


class PinConnectionTransformation(Transformation):
    def __init__(self, pin: Pin, via: Transformation):
        super().__init__()
        self._pin = pin
        self._via_transformation = via

    def forward(self, value):
        return self._via_transformation.forward(self._pin.get())

    def backward(self, value):
        return self._pin.set(self._via_transformation.backward(value))


def connect(pin: Pin, via: Transformation) -> Transformation:
    return PinConnectionTransformation(pin, via)
