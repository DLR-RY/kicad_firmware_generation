from pathlib import Path
import xml.etree.ElementTree as ET

from .kicad_types import (
    Component,
    ComponentRef,
    Net,
    Netlist,
    Node,
    NodePinFunction,
    NodePinName,
    Sheet,
    SheetPath,
)


def parse_netlist(netlist_path: Path) -> Netlist:
    netlist = Netlist()

    tree = ET.parse(netlist_path)
    root = tree.getroot()

    source_tags = root.findall("./design/source")
    assert len(source_tags) == 1
    assert source_tags[0].text is not None
    netlist.source = Path(source_tags[0].text)

    netlist.sheets = set()
    sheet_tags = root.findall("./design/sheet")
    for sheet_tag in sheet_tags:
        path = sheet_tag.get("name")
        assert path is not None
        sheet = Sheet()
        sheet.path = SheetPath(path)
        netlist.sheets.add(sheet)

    comp_tags = root.findall("./components/comp")
    netlist.components = dict()
    for comp_tag in comp_tags:
        component = Component()

        component_ref = comp_tag.get("ref")
        assert component_ref is not None
        component.ref = ComponentRef(component_ref)

        sheetpath_tags = comp_tag.findall("./sheetpath")
        assert len(sheetpath_tags) == 1
        sheetpath = sheetpath_tags[0].get("names")
        assert sheetpath is not None
        component.sheetpath = SheetPath(sheetpath)

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
        net = Net()

        node_tags = net_tag.findall("./node")
        net.nodes = set()
        for node_tag in node_tags:
            node = Node()

            ref = node_tag.get("ref")
            assert ref is not None
            node.ref = ComponentRef(ref)

            pin = node_tag.get("pin")
            assert pin is not None
            node.pin = NodePinName(pin)

            pinfunction = node_tag.get("pinfunction")
            node.pinfunction = NodePinFunction(
                "" if pinfunction is None else pinfunction
            )

            # TODO: this assert doesn't actually do anything
            assert node not in net.nodes
            net.nodes.add(node)

        # TODO: this assert doesn't actually do anything
        assert net not in netlist.nets
        netlist.nets.add(net)

    return netlist
