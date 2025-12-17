import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import List

from common_types.group_types import (
    OtherGroupPinType,
    Group,
    GroupMap,
    GroupNet,
    GroupNetlist,
)

XML_WARNING = "WARNING: This file has been automatically generated. Do not edit!"


def _xmlify_group(
    group: Group,
    other_group_pin_type: OtherGroupPinType,
    tag_name: str,
) -> ET.Element:
    root = ET.Element(tag_name)
    root.set("schematic", group.schematic)
    root.set("path", group.path)
    root.set("type", group.type_name)

    group_map_fields = ET.SubElement(root, "groupMapFields")
    for key, value in group.group_map_fields.items():
        group_map_field = ET.SubElement(group_map_fields, "groupMapField")
        group_map_field.set("name", key)
        group_map_field.text = value

    xml_pins = ET.SubElement(root, "pins")
    # Ensure xml is deterministic.
    pins = list(group.pins.items())
    pins.sort(key=lambda item: item[0])
    for name, pin_connection in pins:
        pin = ET.SubElement(xml_pins, "pin")
        pin.set("name", name)

        if other_group_pin_type == OtherGroupPinType.MANY_TO_MANY:
            # This should be a Set[GlobalGroupPinIdentifier] but that typing isn't present at runtime
            assert type(pin_connection) is set
            other_pins = list(pin_connection)
            other_pins.sort()
            for other_pin in other_pins:
                xml_other_pin = ET.SubElement(pin, "otherPin")
                xml_other_pin.set("schematic", other_pin[0][0])
                xml_other_pin.set("path", other_pin[0][1])
                xml_other_pin.set("type", other_pin[0][2])
                xml_other_pin.set("pin", other_pin[1])
        elif other_group_pin_type == OtherGroupPinType.ONE_TO_MANY:
            root_group_pin = pin_connection
            if root_group_pin is not None:
                # This should be a GroupPinName but is actually a str at runtime...
                assert type(root_group_pin) is str
                pin.set("rootGroupPin", root_group_pin)
        else:
            assert other_group_pin_type == OtherGroupPinType.NO_OTHER_PINS
            assert pin_connection is None
            # is None: don't add anything
    return root


def _xmlify_groups(
    groups: List[Group],
    other_group_pin_type: OtherGroupPinType,
    tag_name: str,
) -> ET.Element:
    xml_groups = ET.Element(tag_name)
    # Ensure xml is deterministic.
    groups.sort(key=lambda s: s.get_id())
    for group in groups:
        xml_group = _xmlify_group(group, other_group_pin_type, "group")
        xml_groups.append(xml_group)
    return xml_groups


def _xmlify_net(net: GroupNet, tag_name: str) -> ET.Element:
    xml_net = ET.Element(tag_name)
    # Ensure xml is deterministic.
    nodes = list(net)
    nodes.sort()
    for node in nodes:
        xml_node = ET.SubElement(xml_net, "node")
        xml_node.set("schematic", node[0][0])
        xml_node.set("path", node[0][1])
        xml_node.set("type", node[0][2])
        xml_node.set("pin", node[1])
    return xml_net


def _xmlify_nets(nets: List[GroupNet], tag_name: str) -> ET.Element:
    xml_nets = ET.Element(tag_name)
    # Ensure xml is deterministic.
    nets.sort(key=lambda n: bytes(ET.tostring(_xmlify_net(n, "net"), encoding="utf-8")))
    for net in nets:
        xml_net = _xmlify_net(net, "net")
        xml_nets.append(xml_net)
    return xml_nets


def _create_xml_root(
    source: Path, date: datetime, tool: str, tag_name: str
) -> ET.Element:
    root = ET.Element(tag_name)
    warning_comment = ET.Comment(XML_WARNING)
    root.append(warning_comment)

    netlist = ET.SubElement(root, "netlist")
    source_tag = ET.SubElement(netlist, "source")
    source_tag.text = str(source)
    date_tag = ET.SubElement(netlist, "date")
    date_tag.text = date.isoformat()
    tool_tag = ET.SubElement(netlist, "tool")
    tool_tag.text = tool

    return root


def _stringify_xml(element: ET.Element) -> bytes:
    ET.indent(element, space="    ", level=0)
    return bytes(
        ET.tostring(element, encoding="utf-8", method="xml", xml_declaration=True)
    )


def stringify_group_netlist(group_netlist: GroupNetlist) -> bytes:
    root = _create_xml_root(
        group_netlist.source,
        group_netlist.date,
        group_netlist.tool,
        "groupNetlist",
    )
    root.append(
        _xmlify_groups(
            list(group_netlist.groups.values()),
            OtherGroupPinType.NO_OTHER_PINS,
            "groups",
        )
    )
    root.append(_xmlify_nets(list(group_netlist.nets), "nets"))
    return _stringify_xml(root)


def stringify_group_map(group_map: GroupMap) -> bytes:
    root = _create_xml_root(
        group_map.source, group_map.date, group_map.tool, "groupMap"
    )
    if group_map.map_type == OtherGroupPinType.ONE_TO_MANY:
        assert group_map.root_group is not None
        assert group_map.map_type == OtherGroupPinType.ONE_TO_MANY
        root.append(
            _xmlify_group(
                group_map.root_group,
                OtherGroupPinType.NO_OTHER_PINS,
                "rootGroup",
            )
        )
    else:
        # NO_OTHER_PINS is not possible for a group map.
        assert group_map.map_type == OtherGroupPinType.MANY_TO_MANY
        assert group_map.root_group is None
    root.append(_xmlify_groups(list(group_map.groups), group_map.map_type, "groups"))
    return _stringify_xml(root)
