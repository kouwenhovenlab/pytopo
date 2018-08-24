class Transformation:
    """
    Interface for defining how value is propagated forward and backward

    TODO:
    * should it work on value or on Parameter or Pin?
    """

    def forward(self, value):
        raise NotImplemented

    def backward(self, value):
        raise NotImplemented


class UnityTransformation(Transformation):
    def forward(self, value):
        return value

    def backward(self, value):
        return value


class AddOneTransformation(Transformation):
    def forward(self, value):
        return value + 1

    def backward(self, value):
        return value - 1


class NestedTransformation(Transformation):
    def __init__(self, outer: Transformation, inner: Transformation):
        super().__init__()
        self._inner = inner
        self._outer = outer

    def forward(self, value):
        return self._outer.forward(self._inner.forward(value))

    def backward(self, value):
        return self._inner.backward(self._outer.backward(value))


def nest_transformation(this: Transformation,
                        into: Transformation) -> Transformation:
    return NestedTransformation(into, this)
