import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Set

from common_types.group_types import Schematic
from kicad_group_netlister.kicad_types import (
    KiCadComponent,
    KiCadComponentRef,
    KiCadNet,
    KiCadNetlist,
    KiCadNode,
    KiCadNodePinFunction,
    KiCadNodePinName,
    KiCadSheet,
    KiCadSheetPath,
)


def parse_kicad_netlist(netlist_path: Path) -> KiCadNetlist:
    netlist = KiCadNetlist()

    tree = ET.parse(netlist_path)
    root = tree.getroot()

    source_tags = root.findall("./design/source")
    assert len(source_tags) == 1
    assert source_tags[0].text is not None
    netlist.source = Path(source_tags[0].text)

    netlist.schematic = Schematic(netlist.source.name.rstrip(".kicad_sch"))
    assert "." not in netlist.schematic
    assert "/" not in netlist.schematic

    netlist.sheets = set()
    sheet_tags = root.findall("./design/sheet")
    for sheet_tag in sheet_tags:
        path = sheet_tag.get("name")
        assert path is not None
        sheet = KiCadSheet()
        sheet.path = KiCadSheetPath(path)
        netlist.sheets.add(sheet)

    comp_tags = root.findall("./components/comp")
    netlist.components = dict()
    for comp_tag in comp_tags:
        component = KiCadComponent()

        component_ref = comp_tag.get("ref")
        assert component_ref is not None
        component.ref = KiCadComponentRef(component_ref)

        sheetpath_tags = comp_tag.findall("./sheetpath")
        assert len(sheetpath_tags) == 1
        sheetpath = sheetpath_tags[0].get("names")
        assert sheetpath is not None
        component.sheetpath = KiCadSheetPath(sheetpath)

        field_tags = comp_tag.findall("./fields/field")
        component.fields = dict()
        for field_tag in field_tags:
            field_name = field_tag.get("name")
            assert field_name is not None
            field_value = field_tag.text

            assert field_name not in component.fields
            # Default to empty string.
            component.fields[field_name] = "" if field_value is None else field_value

        assert component.ref not in netlist.components
        netlist.components[component.ref] = component

    net_tags = root.findall("./nets/net")
    netlist.nets = set()
    for net_tag in net_tags:
        node_tags = net_tag.findall("./node")
        nodes: Set[KiCadNode] = set()
        for node_tag in node_tags:
            node = KiCadNode()

            ref = node_tag.get("ref")
            assert ref is not None
            node.ref = KiCadComponentRef(ref)

            pin = node_tag.get("pin")
            assert pin is not None
            node.pin = KiCadNodePinName(pin)

            pinfunction = node_tag.get("pinfunction")
            node.pinfunction = KiCadNodePinFunction(
                "" if pinfunction is None else pinfunction
            )

            # TODO: this assert doesn't actually do anything
            assert node not in nodes
            nodes.add(node)

        net = KiCadNet(frozenset(nodes))
        # TODO: this assert doesn't actually do anything
        assert net not in netlist.nets
        netlist.nets.add(net)

    return netlist
