"""
This module is taken from QCoDeS and contains old ParamSpec class
(here renamed to QcodesParamSpec) that is used in sweep framework 
in ParamTables. QCoDeS will soon deprecate ParamSpec in favor of 
ParamSpecBase. Note that QcodesParamSpec does not have anything
that is related to ParamSpecBase (for example, base_version method
has been removed), which allows QcodesParamSpec to be truly
independent of QCoDeS.

Copy-pasting code is not good, but it allows to future-proof sweep
framework users with very little effort.
"""

from typing import Union, Sequence, List, Dict, Any, Optional
from copy import deepcopy


class QcodesParamSpec():

    allowed_types = ['array', 'numeric', 'text', 'complex']

    def __init__(self, name: str,
                 paramtype: str,
                 label: Optional[str] = None,
                 unit: Optional[str] = None,
                 inferred_from: Sequence[Union['QcodesParamSpec', str]] = None,
                 depends_on: Sequence[Union['QcodesParamSpec', str]] = None,
                 **metadata) -> None:
        """
        Args:
            name: name of the parameter
            paramtype: type of the parameter, i.e. the SQL storage class
            label: label of the parameter
            inferred_from: the parameters that this parameter is inferred from
            depends_on: the parameters that this parameter depends on
        """

        if not isinstance(paramtype, str):
            raise ValueError('Paramtype must be a string.')
        if paramtype.lower() not in self.allowed_types:
            raise ValueError("Illegal paramtype. Must be on of "
                             f"{self.allowed_types}")
        if not name.isidentifier():
            raise ValueError(f'Invalid name: {name}. Only valid python '
                             'identifier names are allowed (no spaces or '
                             'punctuation marks, no prepended '
                             'numbers, etc.)')

        self.name = name
        self.type = paramtype.lower()
        self.label = label or ''
        self.unit = unit or ''

        self._inferred_from: List[str] = []
        self._depends_on: List[str] = []

        inferred_from = [] if inferred_from is None else inferred_from
        depends_on = [] if depends_on is None else depends_on

        if isinstance(inferred_from, str):
            raise ValueError(f"QcodesParamSpec {self.name} got "
                             f"string {inferred_from} as inferred_from. "
                             f"It needs a "
                             f"Sequence of QcodesParamSpecs or strings")
        self._inferred_from.extend(
            p.name if isinstance(p, QcodesParamSpec) else p
            for p in inferred_from)

        if isinstance(depends_on, str):
            raise ValueError(f"QcodesParamSpec {self.name} got "
                             f"string {depends_on} as depends_on. It needs a "
                             f"Sequence of QcodesParamSpecs or strings")
        self._depends_on.extend(
            p.name if isinstance(p, QcodesParamSpec) else p
            for p in depends_on)

        if metadata:
            self.metadata = metadata

    @property
    def inferred_from_(self) -> List[str]:
        return deepcopy(self._inferred_from)

    @property
    def depends_on_(self) -> List[str]:
        return deepcopy(self._depends_on)

    @property
    def inferred_from(self) -> str:
        return ', '.join(self._inferred_from)

    @property
    def depends_on(self) -> str:
        return ', '.join(self._depends_on)

    def copy(self) -> 'QcodesParamSpec':
        """
        Make a copy of self
        """
        return QcodesParamSpec(self.name, self.type, self.label, self.unit,
                         deepcopy(self._inferred_from),
                         deepcopy(self._depends_on))

    def sql_repr(self):
        return f"{self.name} {self.type}"

    def __repr__(self):
        return (f"QcodesParamSpec('{self.name}', '{self.type}', '{self.label}', "
                f"'{self.unit}', inferred_from={self._inferred_from}, "
                f"depends_on={self._depends_on})")

    def __eq__(self, other):
        if not isinstance(other, QcodesParamSpec):
            return False
        string_attrs = ['name', 'type', 'label', 'unit']
        list_attrs = ['_inferred_from', '_depends_on']
        for string_attr in string_attrs:
            if getattr(self, string_attr) != getattr(other, string_attr):
                return False
        for list_attr in list_attrs:
            ours = getattr(self, list_attr)
            theirs = getattr(other, list_attr)
            if ours != theirs:
                return False
        return True

    def __hash__(self) -> int:
        """Allow QcodesParamSpecs in data structures that use hashing (i.e. sets)"""
        attrs_with_strings = ['name', 'type', 'label', 'unit']
        attrs_with_lists = ['_inferred_from', '_depends_on']

        # First, get the hash of the tuple with all the relevant attributes
        all_attr_tuple_hash = hash(
            tuple(getattr(self, attr) for attr in attrs_with_strings)
            + tuple(tuple(getattr(self, attr)) for attr in attrs_with_lists)
        )
        hash_value = all_attr_tuple_hash

        # Then, XOR it with the individual hashes of all relevant attributes
        for attr in attrs_with_strings:
            hash_value = hash_value ^ hash(getattr(self, attr))
        for attr in attrs_with_lists:
            hash_value = hash_value ^ hash(tuple(getattr(self, attr)))

        return hash_value

    def serialize(self) -> Dict[str, Any]:
        """
        Write the QcodesParamSpec as a dictionary
        """
        output: Dict[str, Any] = {}
        output['name'] = self.name
        output['paramtype'] = self.type
        output['label'] = self.label
        output['unit'] = self.unit
        output['inferred_from'] = self._inferred_from
        output['depends_on'] = self._depends_on

        return output

    @classmethod
    def deserialize(cls, ser: Dict[str, Any]) -> 'QcodesParamSpec':
        """
        Create a QcodesParamSpec instance of the current version
        from a serialized QcodesParamSpec of some version

        The version changes must be implemented as a series of transformations
        of the serialized dict.
        """
        return QcodesParamSpec(name=ser['name'],
                         paramtype=ser['paramtype'],
                         label=ser['label'],
                         unit=ser['unit'],
                         inferred_from=ser['inferred_from'],
                         depends_on=ser['depends_on'])
