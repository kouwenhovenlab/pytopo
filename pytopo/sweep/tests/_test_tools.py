class Factory(dict):
    def __init__(self, func):
        super().__init__()
        self._factory = func

    def __getitem__(self, name):
        if name not in self:
            self[name] = self._factory(name)

        return super().__getitem__(name)