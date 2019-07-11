from typing import Optional, Sequence, Dict

from qcodes.instrument.parameter import Parameter


class ConversionParameter(Parameter):
    """
    The `ConversionParameter` wraps a given source parameter `src_param`
    (similar to `DelegateParameter` from QCoDeS), and it allows to inject
    conversion functions into "setting" and "getting" of this parameter
    This means that when this parameter is set, the value gets passed 
    through the given `set_conv` function, and then is passed to `set()`
    of the source parameter `src_param`. Similarly, when this parameter is 
    being "get", the value from the `get()` call to the source parameter
    is taken, then that value is passed through `get_conv` function, and the
    result of it is returned.
    
    The reason for using a `ConversionParameter` instead of the source parameter
    directly is to provide all the functionality of the source parameter without
    changing the source parameter itself. So, `ConversionParameter` wraps the
    source parameter, and at the same time it can have its own 
    `name`/`label/`unit`/etc, and also have conversion functions on top of the 
    `get`/`set` functionality of the source parameter.
    
    `get_conv` function should always be provided. If `set_conv` is not provided,
    then it is not possible to `set` the `ConversionParameter`.
    
    Note that the snapshot of the `src_param` source parameter is included
    when snapshotting `ConversionParameter`.

    Note that `initial_value` argument is also supported, but it will
    obviously only work if `set_conv` function is provided.
    """
    
    def __init__(self, name: str, src_param: Parameter,
                 get_conv, set_conv=None, **kw):
        for ka, attr in zip(('unit', 'label', 'snapshot_value'),
                             ('unit', 'label', '_snapshot_value')):
            kw[ka] = kw.get(ka, getattr(src_param, attr))

        for cmd in ('set_cmd', 'get_cmd'):
            if cmd in kw:
                raise KeyError(f'It is not allowed to set "{cmd}" of a '
                               f'ConversionParameter because the one of the '
                               f'source parameter is supposed to be used '
                               f'together with get_conv and set_conv functions.')

        initial_value_provided = False
        initial_value = None
        if 'initial_value' in kw.keys():
            initial_value_provided = True
            initial_value = kw.pop('initial_value')

        super().__init__(name, **kw)
        
        self.src_param = src_param
        self.get_conv = get_conv
        self.set_conv = set_conv

        if initial_value_provided:
            self.set(initial_value)

    def get_raw(self):
        return self.get_conv(self.src_param())

    def set_raw(self, value):
        if self.set_conv is None:
            raise NotImplementedError("No set conversion implemented.")

        return self.src_param(self.set_conv(value))

    def snapshot_base(self, update: bool = True,
                      params_to_skip_update: Optional[Sequence[str]] = None
                      ) -> Dict:
        snapshot = super().snapshot_base(
            update=update,
            params_to_skip_update=params_to_skip_update
        )
        snapshot.update(
            {'source_parameter': self.src_param.snapshot(update=update),
             'set_conversion': self.set_conv,
             'get_conversion': self.get_conv}
        )
        return snapshot
