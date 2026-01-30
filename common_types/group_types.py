import glob
import re
from datetime import datetime
from pathlib import Path
import sys
from typing import Dict, FrozenSet, List, NamedTuple, NewType, Set

Schematic = NewType("Schematic", str)
"""
The path's nodes are separated with `/`.
There must be a leading slash and no trailing slash.
"""
GroupPath = NewType("GroupPath", str)
GroupPathNode = NewType("GroupPathNode", str)
GroupType = NewType("GroupType", str)
GroupPinName = NewType("GroupPinName", str)


class GroupIdentifier(NamedTuple):
    schematic: Schematic
    path: GroupPath
    group_type: GroupType


class GlobalGroupPinIdentifier(NamedTuple):
    group_id: GroupIdentifier
    pin: GroupPinName


"""
These pins are connected.
"""
MutableGroupNet = NewType("MutableGroupNet", Set[GlobalGroupPinIdentifier])
GroupNet = NewType("GroupNet", FrozenSet[GlobalGroupPinIdentifier])

GroupGlob = NewType("GroupGlob", FrozenSet[re.Pattern[str]])


class Group:
    # This is not a single group_id to allow building this object step by step.
    schematic: Schematic
    path: GroupPath
    group_type: GroupType
    """
    Map key to value.
    """
    group_map_fields: Dict[str, str]
    """
    All the pins this group has.
    """
    pins: Set[GroupPinName]

    def get_id(self) -> GroupIdentifier:
        return GroupIdentifier(self.schematic, self.path, self.group_type)


class GroupWithConnection:
    # This is not a single group_id to allow building this object step by step.
    schematic: Schematic
    path: GroupPath
    group_type: GroupType
    """
    Map key to value.
    """
    group_map_fields: Dict[str, str]
    """
    All the pins this group has and what they are connected to.
    """
    pins: Dict[GroupPinName, Set[GlobalGroupPinIdentifier]]

    def get_id(self) -> GroupIdentifier:
        return GroupIdentifier(self.schematic, self.path, self.group_type)

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
                GlobalGroupPinIdentifier(other_group, other_pin)
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
            f"Group(path={self.path!r}, type_name={self.group_type!r}, "
            f"fields={list(self.group_map_fields.keys())!r}, pins={len(self.pins)})"
        )


class GroupNetlist:
    """
    Represent what groups there are and how they are connected.
    This information is represented in a set of nets.
    """

    sources: Set[Path]
    date: datetime
    tool: str

    """
    All groups have pins with None set as the rootPinName
    """
    groups: Dict[GroupIdentifier, Group]
    nets: Set[GroupNet]


class GroupNetlistWithConnections:
    """
    Represent what groups there are and how they are connected.
    The GroupNetlist has a set of nets.
    This class instead has groups that already know what their pins are connected to.
    """

    sources: Set[Path]
    date: datetime
    tool: str

    """
    All groups have pins with None set as the rootPinName
    """
    groups: Dict[GroupIdentifier, GroupWithConnection]


def stringify_group_id(id: GroupIdentifier) -> str:
    """
    The stringified group id resembles a path uniquely identifying this group.
    The stringified group id has no leading slash and no trailing slash.
    It consists of the source schematic, the group path and group type.
    There are no double slashes between the path nodes.
    """
    return f"{id.schematic}{id.path}{id.group_type}"


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


def _dumb_connect_group(group: Group) -> GroupWithConnection:
    connected_group = GroupWithConnection()
    connected_group.schematic = group.schematic
    connected_group.path = group.path
    connected_group.group_type = group.group_type
    connected_group.group_map_fields = group.group_map_fields
    # Simply pretend the group isn't connected to anything.
    connected_group.pins = {pin: set() for pin in group.pins}
    return connected_group


def connect_netlist(netlist: GroupNetlist) -> GroupNetlistWithConnections:
    connected_netlist = GroupNetlistWithConnections()
    connected_netlist.sources = netlist.sources
    connected_netlist.date = datetime.now()
    connected_netlist.tool = netlist.tool
    connected_netlist.groups = {
        group_id: _dumb_connect_group(group)
        for (group_id, group) in netlist.groups.items()
    }

    # Figure out what groups are connected how.
    for net in netlist.nets:
        for group_identifier, group_pin_name in net:
            # No one has touched this before so it must have remained empty.
            assert (
                len(connected_netlist.groups[group_identifier].pins[group_pin_name])
                == 0
            )
            connected_netlist.groups[group_identifier].pins[group_pin_name] = {
                other_pin
                for other_pin in net
                # Skip the own pin.
                if other_pin
                != GlobalGroupPinIdentifier(group_identifier, group_pin_name)
            }
    return connected_netlist


GROUP_PATH_PATTERN = re.compile(r"^/([a-zA-Z0-9_/\-\+ ]+/|)$")
SCHEMATIC_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\+ ]+$")
GROUP_TYPE_PATTERN = SCHEMATIC_PATTERN
PIN_NAME_PATTERN = SCHEMATIC_PATTERN

CHAR_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\+ ]$")
CHAR_WITH_SLASH_PATTERN = re.compile(r"^[a-zA-Z0-9_/\-\+ ]$")


def assert_is_group_path(in_str: str, lenient: bool = False) -> GroupPath:
    if lenient:
        in_str = replace_illegal_characters_wo_slash(in_str)
    if GROUP_PATH_PATTERN.match(in_str) is None:
        print(
            f"Error: {in_str} is no valid GroupPath, consider the --lenient-names flag.",
            file=sys.stderr,
        )
        sys.exit(1)
    return GroupPath(in_str)


def assert_is_schematic(in_str: str, lenient: bool = False) -> Schematic:
    if lenient:
        in_str = replace_illegal_characters(in_str)
    if SCHEMATIC_PATTERN.match(in_str) is None:
        print(
            f"Error: {in_str} is no valid Schematic, consider the --lenient-names flag.",
            file=sys.stderr,
        )
        sys.exit(1)
    return Schematic(in_str)


def assert_is_group_type(in_str: str, lenient: bool = False) -> GroupType:
    if lenient:
        in_str = replace_illegal_characters(in_str)
    if GROUP_TYPE_PATTERN.match(in_str) is None:
        print(
            f"Error: {in_str} is no valid GroupPath, consider the --lenient-names flag.",
            file=sys.stderr,
        )
        sys.exit(1)
    return GroupType(in_str)


def assert_is_pin_name(in_str: str, lenient: bool = False) -> GroupPinName:
    if lenient:
        in_str = replace_illegal_characters(in_str)
    if PIN_NAME_PATTERN.match(in_str) is None:
        print(
            f"Error: {in_str} is no valid GroupPinName, consider the --lenient-names flag.",
            file=sys.stderr,
        )
        sys.exit(1)
    return GroupPinName(in_str)


def replace_illegal_characters(in_str: str) -> str:
    def char_replace(c: str) -> str:
        if CHAR_PATTERN.match(c) is None:
            print(
                f"Warning: replacing {c} in {in_str} with _",
                file=sys.stderr,
            )
            return "_"
        return c

    return "".join(map(char_replace, in_str))


def replace_illegal_characters_wo_slash(in_str: str) -> str:
    def char_replace(c: str) -> str:
        if CHAR_WITH_SLASH_PATTERN.match(c) is None:
            print(
                f"Warning: replacing {c} in {in_str} with _",
                file=sys.stderr,
            )
            return "_"
        return c

    return "".join(map(char_replace, in_str))
