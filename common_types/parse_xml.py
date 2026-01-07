import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Set, Tuple

from common_types.group_types import (
    GlobalGroupPinIdentifier,
    GroupNetlist,
    Group,
    GroupIdentifier,
    GroupNet,
    assert_is_group_path,
    assert_is_group_type,
    assert_is_pin_name,
    assert_is_schematic,
)
from common_types.stringify_xml import stringify_group_netlist


def _parse_group(group_tag: ET.Element) -> Group:
    group = Group()

    schematic = group_tag.get("schematic")
    assert schematic is not None
    group.schematic = assert_is_schematic(schematic)

    path = group_tag.get("path")
    assert path is not None
    group.path = assert_is_group_path(path)

    type_name = group_tag.get("type")
    assert type_name is not None
    group.group_type = assert_is_group_type(type_name)

    group.group_map_fields = dict()
    group_map_field_tags = group_tag.findall("./groupMapFields/groupMapField")
    for group_map_field_tag in group_map_field_tags:
        name = group_map_field_tag.get("name")
        assert name is not None
        value = group_map_field_tag.text
        assert value is not None
        assert name not in group.group_map_fields
        group.group_map_fields[name] = value

    group.pins = set()
    group_pin_tags = group_tag.findall("./pins/pin")
    for group_pin_tag in group_pin_tags:
        name = group_pin_tag.get("name")
        assert name is not None
        pin_name = assert_is_pin_name(name)
        assert pin_name not in group.pins
        group.pins.add(pin_name)

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
    schematic = assert_is_schematic(raw_schematic)

    raw_path = node_tag.get("path")
    assert raw_path is not None
    path = assert_is_group_path(raw_path)

    raw_type_name = node_tag.get("type")
    assert raw_type_name is not None
    type_name = assert_is_group_type(raw_type_name)

    raw_pin = node_tag.get("pin")
    assert raw_pin is not None
    pin = assert_is_pin_name(raw_pin)

    return GlobalGroupPinIdentifier(
        GroupIdentifier(schematic, path, type_name),
        pin,
    )


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
        group = _parse_group(group_tag)
        group_id = group.get_id()
        assert group_id not in group_netlist.groups
        group_netlist.groups[group_id] = group

    nets = root.findall("./nets/net")
    group_netlist.nets = {_parse_group_net(net) for net in nets}

    # Check that stringifying what we parsed gets us back.
    with open(group_netlist_path, "rb") as group_netlist_file:
        check_group_netlist = stringify_group_netlist(group_netlist)
        if check_group_netlist != group_netlist_file.read():
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(check_group_netlist)
                print(
                    "Warning: The group netlist was created with a different stringify algorithm or is buggy. "
                    f"The parsed and then stringified file is in: {tmp.name}",
                    file=sys.stderr,
                )

    return group_netlist
