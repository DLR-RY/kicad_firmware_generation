from datetime import datetime
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from snippet_map.snippet_types import (
    Snippet,
    SnippetIdentifier,
    SnippetMap,
    SnippetPath,
    SnippetPinName,
    SnippetType,
)

XML_WARNING = "WARNING: This file has been automatically generated. Do not edit!"


def _xmlify_snippet(snippet: Snippet, tag_name: str) -> ET.Element:
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
    for name, root_snippet_pin in pins:
        pin = ET.SubElement(xml_pins, "pin")
        pin.set("name", name)
        if root_snippet_pin is not None:
            pin.set("rootSnippetPin", root_snippet_pin)
    return root


def stringify_snippet_map(snippet_map: SnippetMap) -> bytes:
    root = ET.Element("snippetMap")
    warning_comment = ET.Comment(XML_WARNING)
    root.append(warning_comment)

    netlist = ET.SubElement(root, "netlist")
    source = ET.SubElement(netlist, "source")
    source.text = str(snippet_map.source)
    date = ET.SubElement(netlist, "date")
    date.text = snippet_map.date.isoformat()
    tool = ET.SubElement(netlist, "tool")
    tool.text = snippet_map.tool

    root_snippet = _xmlify_snippet(snippet_map.root_snippet, "rootSnippet")
    root.append(root_snippet)

    xml_snippets = ET.SubElement(root, "snippets")
    # Ensure xml is deterministic.
    snippets = list(snippet_map.snippets)
    snippets.sort(key=lambda s: SnippetIdentifier((s.path, s.type_name)))
    for snippet in snippets:
        xml_snippet = _xmlify_snippet(snippet, "snippet")
        xml_snippets.append(xml_snippet)

    ET.indent(root, space="    ", level=0)
    return bytes(
        ET.tostring(root, encoding="utf-8", method="xml", xml_declaration=True)
    )


def _parse_snippet(snippet_tag: ET.Element) -> Snippet:
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
        root_snippet_pin = snippet_pin_tag.get("rootSnippetPin")
        assert SnippetPinName(name) not in snippet.pins
        snippet.pins[SnippetPinName(name)] = (
            None if root_snippet_pin is None else SnippetPinName(root_snippet_pin)
        )

    return snippet


def parse_snippet_map(snippet_map_path: Path) -> SnippetMap:
    tree = ET.parse(snippet_map_path)
    root = tree.getroot()

    snippet_map = SnippetMap()

    source_tags = root.findall("./netlist/source")
    assert len(source_tags) == 1
    assert source_tags[0].text is not None
    snippet_map.source = Path(source_tags[0].text)

    date_tags = root.findall("./netlist/date")
    assert len(date_tags) == 1
    assert date_tags[0].text is not None
    snippet_map.date = datetime.fromisoformat(date_tags[0].text)

    tool_tags = root.findall("./netlist/tool")
    assert len(tool_tags) == 1
    assert tool_tags[0].text is not None
    snippet_map.tool = tool_tags[0].text

    root_snippet_tags = root.findall("./rootSnippet")
    assert len(root_snippet_tags) == 1
    snippet_map.root_snippet = _parse_snippet(root_snippet_tags[0])

    connected_snippets = root.findall("./snippets/snippet")
    snippet_map.snippets = {_parse_snippet(snippet) for snippet in connected_snippets}

    # Check that stringifying what we parsed gets us back.
    with open(snippet_map_path, "rb") as snippet_map_file:
        check_snippet_map = stringify_snippet_map(snippet_map)
        if check_snippet_map != snippet_map_file.read():
            print(
                "Warning: The snippet map was created with a different stringify algorithm or is buggy.",
                file=sys.stderr,
            )

    return snippet_map
