from pathlib import Path
from typing import Dict, FrozenSet, NewType, Set, Tuple

from common_types.group_types import (
    GroupIdentifier,
    GroupPath,
    GroupPinName,
    GroupType,
    Schematic,
)

KiCadComponentRef = NewType("KiCadComponentRef", str)
KiCadSheetPath = NewType("KiCadSheetPath", str)
KiCadNodePinName = NewType("KiCadNodePinName", str)
"""
globally unique descriptor for a pin
"""
GlobalKiCadPinIdentifier = NewType(
    "GlobalKiCadPinIdentifier", Tuple[KiCadComponentRef, KiCadNodePinName]
)
KiCadNodePinFunction = NewType("KiCadNodePinFunction", str)


class KiCadSheet:
    path: KiCadSheetPath


class KiCadComponent:
    ref: KiCadComponentRef
    sheetpath: KiCadSheetPath
    fields: Dict[str, str]

    def __repr__(self) -> str:
        return f"Component(ref={self.ref!r}, sheetpath={self.sheetpath!r}, fields={list(self.fields.keys())!r})"


class KiCadNode:
    """
    a pin on a component that is connected to some net(s)
    """

    ref: KiCadComponentRef
    pin: KiCadNodePinName
    pinfunction: KiCadNodePinFunction

    def __repr__(self) -> str:
        return f"Node(ref={self.ref!r}, pin={self.pin!r}, pinfunction={self.pinfunction!r})"


KiCadNet = NewType("KiCadNet", FrozenSet[KiCadNode])


class KiCadNetlist:
    source: Path
    schematic: Schematic
    sheets: Set[KiCadSheet]
    """
    Map component's ref to component.
    """
    components: Dict[KiCadComponentRef, KiCadComponent]
    nets: Set[KiCadNet]

    def __repr__(self) -> str:
        return (
            f"Netlist(source={self.source!r}, "
            f"components={len(self.components)} components, "
            f"nets={len(self.nets)} nets)"
        )


class RawGroup:
    schematic: Schematic
    path: GroupPath
    type_name: GroupType
    """
    Map key to value.
    """
    group_map_fields: Dict[str, str]

    components: Set[KiCadComponent]

    def get_id(self) -> GroupIdentifier:
        return GroupIdentifier((self.schematic, self.path, self.type_name))

    def __repr__(self) -> str:
        return (
            f"RawGroup(path={self.path!r}, type_name={self.type_name!r}, "
            f"fields={list(self.group_map_fields.keys())!r}, components={len(self.components)})"
        )


"""
mapping from group name to the info we can directly pull from the KiCad netlist
"""
RawGroupLookup = NewType("RawGroupLookup", Dict[GroupIdentifier, RawGroup])
"""
mapping from component ref to group name
"""
GroupsReverseLookup = NewType(
    "GroupsReverseLookup", Dict[KiCadComponentRef, GroupIdentifier]
)
"""
For each group this resolves the pins global identifier to the explicitly chosen pin name.
"""
GroupPinNameLookups = NewType(
    "GroupPinNameLookups",
    Dict[GroupIdentifier, Dict[GlobalKiCadPinIdentifier, GroupPinName]],
)
