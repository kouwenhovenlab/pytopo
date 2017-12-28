"""
A collection of instrument tools that make life with Qcodes a bit easier.
"""

import qcodes as qc


def create_inst(cls, name, *arg, **kw):
    """
    Create new instrument of type <cls> with name <name>.
    This is just a wrapper for the qcodes instrument creation that
    prevents an exception being thrown when the instrument already 
    exists.

    optional keywords:
        force_new_instance : False
            If True, try to close instrument with given name and recreate.
    """
    force_new = kw.pop('force_new_instance', False)

    try:
        return cls(name, *arg, **kw)
    except KeyError:
        print("Instrument {} already exists.".format(name))
        if force_new:
            qc.Instrument._all_instruments[name]().close()
            return cls(name, *arg, **kw)

        return qc.Instrument._all_instruments[name]()
