import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import List, Set, Tuple

from common_types.snippet_types import (
    GlobalSnippetPinIdentifier,
    Snippet,
    SnippetIdentifier,
    SnippetMap,
    OtherSnippetPinType,
    SnippetNet,
    SnippetNetlist,
    SnippetPath,
    SnippetPinName,
    SnippetType,
)

XML_WARNING = "WARNING: This file has been automatically generated. Do not edit!"


def _xmlify_snippet(
    snippet: Snippet,
    other_snippet_pin_type: OtherSnippetPinType,
    tag_name: str,
) -> ET.Element:
    root = ET.Element(tag_name)
    root.set("path", snippet.path)
    root.set("type", snippet.type_name)

    snippet_map_fields = ET.SubElement(root, "snippetMapFields")
    for key, value in snippet.snippet_map_fields.items():
        snippet_map_field = ET.SubElement(snippet_map_fields, "snippetMapField")
        snippet_map_field.set("name", key)
        snippet_map_field.text = value

    xml_pins = ET.SubElement(root, "pins")
    # Ensure xml is deterministic.
    pins = list(snippet.pins.items())
    pins.sort(key=lambda item: item[0])
    for name, pin_connection in pins:
        pin = ET.SubElement(xml_pins, "pin")
        pin.set("name", name)

        if other_snippet_pin_type == OtherSnippetPinType.MANY_TO_MANY:
            # This should be a Set[GlobalSnippetPinIdentifier] but that typing isn't present at runtime
            assert type(pin_connection) is set
            other_pins = list(pin_connection)
            other_pins.sort()
            for other_pin in other_pins:
                xml_other_pin = ET.SubElement(pin, "otherPin")
                xml_other_pin.set("path", other_pin[0][0])
                xml_other_pin.set("type", other_pin[0][1])
                xml_other_pin.set("pin", other_pin[1])
        elif other_snippet_pin_type == OtherSnippetPinType.ONE_TO_MANY:
            root_snippet_pin = pin_connection
            if root_snippet_pin is not None:
                # This should be a SnippetPinName but is actually a str at runtime...
                assert type(root_snippet_pin) is str
                pin.set("rootSnippetPin", root_snippet_pin)
        else:
            assert other_snippet_pin_type == OtherSnippetPinType.NO_OTHER_PINS
            assert pin_connection is None
            # is None: don't add anything
    return root


def _xmlify_snippets(
    snippets: List[Snippet],
    other_snippet_pin_type: OtherSnippetPinType,
    tag_name: str,
) -> ET.Element:
    xml_snippets = ET.Element(tag_name)
    # Ensure xml is deterministic.
    snippets.sort(key=lambda s: s.get_id())
    for snippet in snippets:
        xml_snippet = _xmlify_snippet(snippet, other_snippet_pin_type, "snippet")
        xml_snippets.append(xml_snippet)
    return xml_snippets


def _xmlify_net(net: SnippetNet, tag_name: str) -> ET.Element:
    xml_net = ET.Element(tag_name)
    # Ensure xml is deterministic.
    nodes = list(net)
    nodes.sort()
    for node in nodes:
        xml_node = ET.SubElement(xml_net, "node")
        xml_node.set("path", node[0][0])
        xml_node.set("type", node[0][1])
        xml_node.set("pin", node[1])
    return xml_net


def _xmlify_nets(nets: List[SnippetNet], tag_name: str) -> ET.Element:
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


def stringify_snippet_netlist(snippet_netlist: SnippetNetlist) -> bytes:
    root = _create_xml_root(
        snippet_netlist.source,
        snippet_netlist.date,
        snippet_netlist.tool,
        "snippetNetlist",
    )
    root.append(
        _xmlify_snippets(
            list(snippet_netlist.snippets.values()),
            OtherSnippetPinType.NO_OTHER_PINS,
            "snippets",
        )
    )
    root.append(_xmlify_nets(list(snippet_netlist.nets), "nets"))
    return _stringify_xml(root)


def stringify_snippet_map(snippet_map: SnippetMap) -> bytes:
    root = _create_xml_root(
        snippet_map.source, snippet_map.date, snippet_map.tool, "snippetMap"
    )
    if snippet_map.map_type == OtherSnippetPinType.ONE_TO_MANY:
        assert snippet_map.root_snippet is not None
        assert snippet_map.map_type == OtherSnippetPinType.ONE_TO_MANY
        root.append(
            _xmlify_snippet(
                snippet_map.root_snippet,
                OtherSnippetPinType.NO_OTHER_PINS,
                "rootSnippet",
            )
        )
    else:
        # NO_OTHER_PINS is not possible for a snippet map.
        assert snippet_map.map_type == OtherSnippetPinType.MANY_TO_MANY
        assert snippet_map.root_snippet is None
    root.append(
        _xmlify_snippets(list(snippet_map.snippets), snippet_map.map_type, "snippets")
    )
    return _stringify_xml(root)


def _parse_snippet(snippet_tag: ET.Element, map_type: OtherSnippetPinType) -> Snippet:
    snippet = Snippet()

    path = snippet_tag.get("path")
    assert path is not None
    snippet.path = SnippetPath(path)

    type_name = snippet_tag.get("type")
    assert type_name is not None
    snippet.type_name = SnippetType(type_name)

    snippet.snippet_map_fields = dict()
    snippet_map_field_tags = snippet_tag.findall("./snippetMapFields/snippetMapField")
    for snippet_map_field_tag in snippet_map_field_tags:
        name = snippet_map_field_tag.get("name")
        assert name is not None
        value = snippet_map_field_tag.text
        assert value is not None
        assert name not in snippet.snippet_map_fields
        snippet.snippet_map_fields[name] = value

    snippet.pins = dict()
    snippet_pin_tags = snippet_tag.findall("./pins/pin")
    for snippet_pin_tag in snippet_pin_tags:
        name = snippet_pin_tag.get("name")
        assert name is not None
        pin_name = SnippetPinName(name)
        root_snippet_pin = snippet_pin_tag.get("rootSnippetPin")
        assert pin_name not in snippet.pins
        if map_type == OtherSnippetPinType.NO_OTHER_PINS:
            # This is a netlist.
            assert len(snippet_pin_tag) == 0
            assert root_snippet_pin is None
            snippet.pins[pin_name] = None
        elif map_type == OtherSnippetPinType.ONE_TO_MANY:
            # This is a one-to-many map.
            assert len(snippet_pin_tag) == 0
            snippet.pins[pin_name] = (
                None if root_snippet_pin is None else SnippetPinName(root_snippet_pin)
            )
        else:
            # This is a many-to-many map, let's see what other snippets this pin is connected to.
            assert map_type == OtherSnippetPinType.MANY_TO_MANY
            other_pins: Set[GlobalSnippetPinIdentifier] = set()
            for other_pin_tag in snippet_pin_tag.findall("./otherPin"):
                other_snippet_path = other_pin_tag.get("path")
                assert other_snippet_path is not None

                other_snippet_type = other_pin_tag.get("type")
                assert other_snippet_type is not None

                other_snippet_pin = other_pin_tag.get("pin")
                assert other_snippet_pin is not None

                other_pin_id = GlobalSnippetPinIdentifier((
                    SnippetIdentifier((
                        SnippetPath(other_snippet_pin),
                        SnippetType(other_snippet_type),
                    )),
                    SnippetPinName(other_snippet_pin),
                ))
                other_pins.add(other_pin_id)
            snippet.pins[pin_name] = other_pins

    return snippet


def _parse_xml_root(path: Path) -> Tuple[ET.Element, Path, datetime, str]:
    """
    Return root element, source, date and tool.
    """
    tree = ET.parse(path)
    root = tree.getroot()

    source_tags = root.findall("./netlist/source")
    assert len(source_tags) == 1
    assert source_tags[0].text is not None
    source = Path(source_tags[0].text)

    date_tags = root.findall("./netlist/date")
    assert len(date_tags) == 1
    assert date_tags[0].text is not None
    date = datetime.fromisoformat(date_tags[0].text)

    tool_tags = root.findall("./netlist/tool")
    assert len(tool_tags) == 1
    assert tool_tags[0].text is not None
    tool = tool_tags[0].text

    return root, source, date, tool


def _parse_snippet_node(node_tag: ET.Element) -> GlobalSnippetPinIdentifier:
    raw_path = node_tag.get("path")
    assert raw_path is not None
    path = SnippetPath(raw_path)

    raw_type_name = node_tag.get("type")
    assert raw_type_name is not None
    type_name = SnippetType(raw_type_name)

    raw_pin = node_tag.get("pin")
    assert raw_pin is not None
    pin = SnippetPinName(raw_pin)

    return GlobalSnippetPinIdentifier((
        SnippetIdentifier((path, type_name)),
        pin,
    ))


def _parse_snippet_net(net_tag: ET.Element) -> SnippetNet:
    node_tags = net_tag.findall("./node")
    return SnippetNet(
        frozenset({_parse_snippet_node(node_tag) for node_tag in node_tags})
    )


def parse_snippet_netlist(snippet_netlist_path: Path) -> SnippetNetlist:
    snippet_netlist = SnippetNetlist()
    root, snippet_netlist.source, snippet_netlist.date, snippet_netlist.tool = (
        _parse_xml_root(snippet_netlist_path)
    )

    snippet_tags = root.findall("./snippets/snippet")
    snippet_netlist.snippets = dict()
    for snippet_tag in snippet_tags:
        snippet = _parse_snippet(snippet_tag, OtherSnippetPinType.NO_OTHER_PINS)
        snippet_id = snippet.get_id()
        assert snippet_id not in snippet_netlist.snippets
        snippet_netlist.snippets[snippet_id] = snippet

    nets = root.findall("./nets/net")
    snippet_netlist.nets = {_parse_snippet_net(net) for net in nets}

    # Check that stringifying what we parsed gets us back.
    with open(snippet_netlist_path, "rb") as snippet_netlist_file:
        check_snippet_netlist = stringify_snippet_netlist(snippet_netlist)
        if check_snippet_netlist != snippet_netlist_file.read():
            print(
                "Warning: The snippet netlist was created with a different stringify algorithm or is buggy.",
                file=sys.stderr,
            )

    return snippet_netlist


def parse_one_to_many_snippet_map(snippet_map_path: Path) -> SnippetMap:
    snippet_map = SnippetMap()
    snippet_map.map_type = OtherSnippetPinType.ONE_TO_MANY
    root, snippet_map.source, snippet_map.date, snippet_map.tool = _parse_xml_root(
        snippet_map_path
    )

    root_snippet_tags = root.findall("./rootSnippet")
    assert len(root_snippet_tags) == 1
    snippet_map.root_snippet = _parse_snippet(
        root_snippet_tags[0], OtherSnippetPinType.ONE_TO_MANY
    )

    connected_snippets = root.findall("./snippets/snippet")
    snippet_map.snippets = {
        _parse_snippet(snippet, OtherSnippetPinType.ONE_TO_MANY)
        for snippet in connected_snippets
    }

    # Check that stringifying what we parsed gets us back.
    with open(snippet_map_path, "rb") as snippet_map_file:
        check_snippet_map = stringify_snippet_map(snippet_map)
        if check_snippet_map != snippet_map_file.read():
            print(
                "Warning: The one-to-many snippet map was created with a different stringify algorithm or is buggy.",
                file=sys.stderr,
            )

    return snippet_map


def parse_many_to_many_snippet_map(snippet_map_path: Path) -> SnippetMap:
    snippet_map = SnippetMap()
    snippet_map.map_type = OtherSnippetPinType.MANY_TO_MANY
    root, snippet_map.source, snippet_map.date, snippet_map.tool = _parse_xml_root(
        snippet_map_path
    )

    snippets = root.findall("./snippets/snippet")
    snippet_map.snippets = {
        _parse_snippet(snippet, OtherSnippetPinType.MANY_TO_MANY)
        for snippet in snippets
    }

    # Check that stringifying what we parsed gets us back.
    with open(snippet_map_path, "rb") as snippet_map_file:
        check_snippet_map = stringify_snippet_map(snippet_map)
        if check_snippet_map != snippet_map_file.read():
            print(
                "Warning: The many-to-many snippet map was created with a different stringify algorithm or is buggy.",
                file=sys.stderr,
            )

    return snippet_map
