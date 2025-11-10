import xml.etree.ElementTree as ET

from .snippet_types import Snippet, SnippetIdentifier, SnippetMap

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

    xml_snippets = ET.SubElement(root, "snippet")
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


def parse_snippet_map(snippet_map_path: Path) -> SnippetMap:
    pass
