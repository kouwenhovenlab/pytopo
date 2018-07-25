class GroupSetter:
    def __init__(self, *parameters):
        self._parameters = parameters

    def set(self, values):

        if len(values) != len(self._parameters):
            raise ValueError(f"I need {len(self._parameters)} to set all "
                             f"parameters")

        for p, v in zip(self._parameters, values):
            p.set(v)
