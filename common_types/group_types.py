import glob
import re
from datetime import datetime
from enum import Enum
from pathlib import Path
import sys
from typing import Dict, FrozenSet, List, NewType, Set, Tuple

Schematic = NewType("Schematic", str)
"""
The path's nodes are separated with `/`.
There must be a leading slash and no trailing slash.
"""
GroupPath = NewType("GroupPath", str)
GroupPathNode = NewType("GroupPathNode", str)
GroupType = NewType("GroupType", str)
GroupIdentifier = NewType("GroupIdentifier", Tuple[Schematic, GroupPath, GroupType])
GroupPinName = NewType("GroupPinName", str)

GlobalGroupPinIdentifier = NewType(
    "GlobalGroupPinIdentifier", Tuple[GroupIdentifier, GroupPinName]
)
"""
These pins are connected.
"""
MutableGroupNet = NewType("MutableGroupNet", Set[GlobalGroupPinIdentifier])
GroupNet = NewType("GroupNet", FrozenSet[GlobalGroupPinIdentifier])

GroupGlob = NewType("GroupGlob", FrozenSet[re.Pattern[str]])


class Group:
    schematic: Schematic
    path: GroupPath
    type_name: GroupType
    """
    Map key to value.
    """
    group_map_fields: Dict[str, str]
    # TODO: remove one-to-many map
    """
    If we are generating a one-to-many map (OtherGroupPinType.ONE_TO_MANY), map group pin name to connected root group pin name.
    If this is the root group the value is always None.
    If we are generating a group netlist (OtherGroupPinType.NO_PINS), the value is also always None.
    If we are generating a many-to-many map (OtherGroupPinType.MANY_TO_MANY), the value is a set of all connected pins.
    """
    pins: Dict[GroupPinName, GroupPinName | None | Set[GlobalGroupPinIdentifier]]

    def get_id(self) -> GroupIdentifier:
        return GroupIdentifier((self.schematic, self.path, self.type_name))

    def _get_pins_to_glob(
        self, glob_str: str
    ) -> Dict[GroupPinName, Set[GlobalGroupPinIdentifier]]:
        """
        Return all pins of this group.
        For each returned pin, return a set of the pins on other groups that match `glob_str`.
        This means that all other groups that don't match are ignored.
        """
        pattern = compile_group_glob(glob_str)
        pins: Dict[GroupPinName, Set[GlobalGroupPinIdentifier]] = dict()
        for pin, other_pins in self.pins.items():
            # This should be Set[GlobalGroupPinIdentifier] but that isn't known at runtime.
            assert type(other_pins) is set
            pins[pin] = {
                GlobalGroupPinIdentifier((other_group, other_pin))
                for (other_group, other_pin) in other_pins
                if does_match_pattern(pattern, other_group)
            }
        return pins

    # def get_pins_to_glob_reduced(
    #     self, glob_str: str
    # ) -> Dict[GroupPinName, Set[GlobalGroupPinIdentifier]]:
    #     """
    #     Same as get_pins_to_glob but with all pins that aren't connected to anything removed.
    #     """
    #     return {
    #         pin: other_pins
    #         for (pin, other_pins) in self._get_pins_to_glob(glob_str).items()
    #         if len(other_pins) > 0
    #     }

    def get_single_pin_to_glob(
        self, pin_name: GroupPinName, other_group_glob_str: str
    ) -> GlobalGroupPinIdentifier | None:
        """
        Check if the given pin with name `pin_name` is connected to an other group that matches `other_group_glob_str`.
        This function only makes sense on pins that aren't
        """
        filtered_pins = self._get_pins_to_glob(other_group_glob_str)
        assert pin_name in filtered_pins
        other_group_pins = list(filtered_pins[pin_name])
        if len(other_group_pins) > 1:
            print(
                f"Warning: the pins {other_group_pins} on {other_group_glob_str} are connected together. The script only considers the first in get_single_pin_to_glob.",
                file=sys.stderr,
            )
        if len(other_group_pins) == 0:
            return None
        return other_group_pins[0]

    def __repr__(self) -> str:
        return (
            f"Group(path={self.path!r}, type_name={self.type_name!r}, "
            f"fields={list(self.group_map_fields.keys())!r}, pins={len(self.pins)})"
        )


class OtherGroupPinType(Enum):
    NO_OTHER_PINS = "NO_OTHER_PINS"
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_MANY = "MANY_TO_MANY"


class GroupMap:
    map_type: OtherGroupPinType

    sources: Set[Path]
    date: datetime
    tool: str

    """
    None iff this is a many-to-many group map.
    """
    root_group: Group | None
    groups: Set[Group]

    # TODO: better __repr__ functions everywhere.
    def __repr__(self) -> str:
        return (
            f"GroupMap(source={self.sources!r}, date={self.date.isoformat()}, "
            f"tool={self.tool!r}, root_group={None if self.root_group is None else stringify_group_id(self.root_group.get_id())!r}, "
            f"groups={len(self.groups)})"
        )


class GroupNetlist:
    """
    Represent what groups there are and how they are connected.
    """

    sources: Set[Path]
    date: datetime
    tool: str

    """
    All groups have pins with None set as the rootPinName
    """
    groups: Dict[GroupIdentifier, Group]
    nets: Set[GroupNet]


def stringify_group_id(id: GroupIdentifier) -> str:
    """
    The stringified group id resembles a path uniquely identifying this group.
    The stringified group id has no leading slash and no trailing slash.
    It consists of the source schematic, the group path and group type.
    There are no double slashes between the path nodes.
    """
    return f"{id[0]}{id[1]}{id[2]}"


def split_group_path(path: GroupPath) -> List[GroupPathNode]:
    assert len(path) >= 1
    assert path[0] == "/"
    assert path[-1] == "/"
    return [GroupPathNode(node_str) for node_str in path.split("/")]


def get_parent_group_path(path: GroupPath) -> GroupPath:
    nodes = split_group_path(path)
    assert len(nodes) >= 3
    nodes.pop(-2)
    return GroupPath("/".join(nodes))


# TODO: ensure no groups have a comma inside them.
def compile_group_glob(group_glob_str: str) -> GroupGlob:
    """
    A group glob is a list of path globs with *, **, [].
    Each path glob is separated with a , (a single comma without spaces).
    """
    globs = group_glob_str.split(",")
    regexes = {
        re.compile(
            glob.translate(single_group_glob_str, recursive=True, include_hidden=True)
        )
        for single_group_glob_str in globs
    }
    return GroupGlob(frozenset(regexes))


# TODO: maybe make a class out of this.
def does_match_pattern(
    pattern: GroupGlob | None, group_id: GroupIdentifier, when_none: bool = False
) -> bool:
    if pattern is None:
        return when_none
    for single_pattern in pattern:
        if single_pattern.match(stringify_group_id(group_id)) is not None:
            return True
    return False
