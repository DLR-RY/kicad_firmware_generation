import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Set, Tuple

from common_types.group_types import (
    GlobalGroupPinIdentifier,
    GroupNetlist,
    OtherGroupPinType,
    Group,
    GroupIdentifier,
    GroupMap,
    GroupNet,
    GroupPath,
    GroupPinName,
    GroupType,
    Schematic,
)
from common_types.stringify_xml import stringify_group_map, stringify_group_netlist


def _parse_group(
    group_tag: ET.Element, other_group_pin_type: OtherGroupPinType
) -> Group:
    group = Group()

    schematic = group_tag.get("schematic")
    assert schematic is not None
    group.schematic = Schematic(schematic)

    path = group_tag.get("path")
    assert path is not None
    group.path = GroupPath(path)

    type_name = group_tag.get("type")
    assert type_name is not None
    group.type_name = GroupType(type_name)

    group.group_map_fields = dict()
    group_map_field_tags = group_tag.findall("./groupMapFields/groupMapField")
    for group_map_field_tag in group_map_field_tags:
        name = group_map_field_tag.get("name")
        assert name is not None
        value = group_map_field_tag.text
        assert value is not None
        assert name not in group.group_map_fields
        group.group_map_fields[name] = value

    group.pins = dict()
    group_pin_tags = group_tag.findall("./pins/pin")
    for group_pin_tag in group_pin_tags:
        name = group_pin_tag.get("name")
        assert name is not None
        pin_name = GroupPinName(name)
        root_group_pin = group_pin_tag.get("rootGroupPin")
        assert pin_name not in group.pins
        if other_group_pin_type == OtherGroupPinType.NO_OTHER_PINS:
            # This is a netlist.
            assert len(group_pin_tag) == 0
            assert root_group_pin is None
            group.pins[pin_name] = None
        elif other_group_pin_type == OtherGroupPinType.ONE_TO_MANY:
            # This is a one-to-many map.
            assert len(group_pin_tag) == 0
            group.pins[pin_name] = (
                None if root_group_pin is None else GroupPinName(root_group_pin)
            )
        else:
            # This is a many-to-many map, let's see what other groups this pin is connected to.
            # TODO: create a pretty error message when the user uses a one_to_many instead of many-to-many map.
            assert root_group_pin is None
            assert other_group_pin_type == OtherGroupPinType.MANY_TO_MANY
            other_pins: Set[GlobalGroupPinIdentifier] = set()
            for other_pin_tag in group_pin_tag.findall("./otherPin"):
                other_group_schematic = other_pin_tag.get("schematic")
                assert other_group_schematic is not None

                other_group_path = other_pin_tag.get("path")
                assert other_group_path is not None

                other_group_type = other_pin_tag.get("type")
                assert other_group_type is not None

                other_group_pin = other_pin_tag.get("pin")
                assert other_group_pin is not None

                other_pin_id = GlobalGroupPinIdentifier((
                    GroupIdentifier((
                        Schematic(other_group_schematic),
                        GroupPath(other_group_path),
                        GroupType(other_group_type),
                    )),
                    GroupPinName(other_group_pin),
                ))
                other_pins.add(other_pin_id)
            group.pins[pin_name] = other_pins

    return group


def _parse_xml_root(path: Path) -> Tuple[ET.Element, Set[Path], datetime, str]:
    """
    Return root element, source, date and tool.
    """
    tree = ET.parse(path)
    root = tree.getroot()

    source_tags = root.findall("./netlist/sources/source")
    assert len(source_tags) > 0
    sources: Set[Path] = set()
    for source_tag in source_tags:
        assert source_tag.text is not None
        assert source_tag.text not in sources
        sources.add(Path(source_tag.text))

    date_tags = root.findall("./netlist/date")
    assert len(date_tags) == 1
    assert date_tags[0].text is not None
    date = datetime.fromisoformat(date_tags[0].text)

    tool_tags = root.findall("./netlist/tool")
    assert len(tool_tags) == 1
    assert tool_tags[0].text is not None
    tool = tool_tags[0].text

    return root, sources, date, tool


def _parse_group_node(node_tag: ET.Element) -> GlobalGroupPinIdentifier:
    raw_schematic = node_tag.get("schematic")
    assert raw_schematic is not None
    schematic = Schematic(raw_schematic)

    raw_path = node_tag.get("path")
    assert raw_path is not None
    path = GroupPath(raw_path)

    raw_type_name = node_tag.get("type")
    assert raw_type_name is not None
    type_name = GroupType(raw_type_name)

    raw_pin = node_tag.get("pin")
    assert raw_pin is not None
    pin = GroupPinName(raw_pin)

    return GlobalGroupPinIdentifier((
        GroupIdentifier((schematic, path, type_name)),
        pin,
    ))


def _parse_group_net(net_tag: ET.Element) -> GroupNet:
    node_tags = net_tag.findall("./node")
    return GroupNet(frozenset({_parse_group_node(node_tag) for node_tag in node_tags}))


def parse_group_netlist(group_netlist_path: Path) -> GroupNetlist:
    group_netlist = GroupNetlist()
    root, group_netlist.sources, group_netlist.date, group_netlist.tool = (
        _parse_xml_root(group_netlist_path)
    )

    group_tags = root.findall("./groups/group")
    group_netlist.groups = dict()
    for group_tag in group_tags:
        group = _parse_group(group_tag, OtherGroupPinType.NO_OTHER_PINS)
        group_id = group.get_id()
        assert group_id not in group_netlist.groups
        group_netlist.groups[group_id] = group

    nets = root.findall("./nets/net")
    group_netlist.nets = {_parse_group_net(net) for net in nets}

    # Check that stringifying what we parsed gets us back.
    with open(group_netlist_path, "rb") as group_netlist_file:
        check_group_netlist = stringify_group_netlist(group_netlist)
        if check_group_netlist != group_netlist_file.read():
            print(
                "Warning: The group netlist was created with a different stringify algorithm or is buggy.",
                file=sys.stderr,
            )

    return group_netlist


def parse_one_to_many_group_map(group_map_path: Path) -> GroupMap:
    group_map = GroupMap()
    group_map.map_type = OtherGroupPinType.ONE_TO_MANY
    root, group_map.sources, group_map.date, group_map.tool = _parse_xml_root(
        group_map_path
    )

    root_group_tags = root.findall("./rootGroup")
    assert len(root_group_tags) == 1
    group_map.root_group = _parse_group(
        root_group_tags[0], OtherGroupPinType.ONE_TO_MANY
    )

    connected_groups = root.findall("./groups/group")
    group_map.groups = {
        _parse_group(group, OtherGroupPinType.ONE_TO_MANY) for group in connected_groups
    }

    # Check that stringifying what we parsed gets us back.
    with open(group_map_path, "rb") as group_map_file:
        check_group_map = stringify_group_map(group_map)
        if check_group_map != group_map_file.read():
            print(
                "Warning: The one-to-many group map was created with a different stringify algorithm or is buggy.",
                file=sys.stderr,
            )

    return group_map


def parse_many_to_many_group_map(group_map_path: Path) -> GroupMap:
    group_map = GroupMap()
    group_map.map_type = OtherGroupPinType.MANY_TO_MANY
    root, group_map.sources, group_map.date, group_map.tool = _parse_xml_root(
        group_map_path
    )
    group_map.root_group = None

    root_group_tags = root.findall("./rootGroup")
    assert len(root_group_tags) == 0

    groups = root.findall("./groups/group")
    group_map.groups = {
        _parse_group(group, OtherGroupPinType.MANY_TO_MANY) for group in groups
    }

    # Check that stringifying what we parsed gets us back.
    with open(group_map_path, "rb") as group_map_file:
        check_group_map = stringify_group_map(group_map)
        if check_group_map != group_map_file.read():
            print(
                "Warning: The many-to-many group map was created with a different stringify algorithm or is buggy.",
                file=sys.stderr,
            )

    return group_map
