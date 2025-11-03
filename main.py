import sys
from pathlib import Path
from typing import FrozenSet, Set, Dict, Tuple, NewType
from datetime import datetime
import xml.etree.ElementTree as ET


SNIPPET_TYPE_FIELD_NAME = "SnippetType"
SNIPPET_PIN_FIELD_PREFIX = "SnippetPin"
SNIPPET_MAP_FIELD_PREFIX = "SnippetMapField"
TOOL_NAME = "kicad_snippet_mapper v0.1.0"

ComponentRef = NewType("ComponentRef", str)
SheetPath = NewType("SheetPath", str)
NodePinName = NewType("NodePinName", str)
# globally unique descriptor for a pin
GlobalPinIdentifier = NewType("GlobalPinIdentifier", Tuple[ComponentRef, NodePinName])
NodePinFunction = NewType("NodePinFunction", str)

SnippetName = NewType("SnippetName", str)
SnippetType = NewType("SnippetType", str)
SnippetPinName = NewType("SnippetPinName", str)
GlobalSnippetPinIdentifier = NewType(
    "GlobalSnippetPinIdentifier", Tuple[SnippetName, SnippetPinName]
)
# These pins are connected.
MutableSnippetNet = NewType("MutableSnippetNet", Set[GlobalSnippetPinIdentifier])
SnippetNet = NewType("SnippetNet", FrozenSet[GlobalSnippetPinIdentifier])
SnippetNetList = NewType("SnippetNetList", Set[SnippetNet])


class Component:
    ref: ComponentRef
    sheetpath: SheetPath
    fields: Dict[str, str]

    def __repr__(self) -> str:
        return f"Component(ref={self.ref!r}, sheetpath={self.sheetpath!r}, fields={list(self.fields.keys())!r})"


# a pin on a component that is connected to some net(s)
class Node:
    ref: ComponentRef
    pin: NodePinName
    pinfunction: NodePinFunction

    def __repr__(self) -> str:
        return f"Node(ref={self.ref!r}, pin={self.pin!r}, pinfunction={self.pinfunction!r})"


class Net:
    nodes: Set[Node]

    def __repr__(self) -> str:
        return f"Net(nodes={len(self.nodes)} nodes)"


class Netlist:
    source: Path
    # Map component's ref to component.
    components: Dict[ComponentRef, Component]
    nets: Set[Net]

    def __repr__(self) -> str:
        return (
            f"Netlist(source={self.source!r}, "
            f"components={len(self.components)} components, "
            f"nets={len(self.nets)} nets)"
        )


class Snippet:
    name: SnippetName
    type_name: SnippetType
    # Map key to value.
    snippet_map_fields: Dict[str, str]
    # Map snippet pin name to connected root snippet pin name.
    # If this is the root snippet the value is always None.
    pins: Dict[SnippetPinName, SnippetPinName | None]

    def __repr__(self) -> str:
        return (
            f"Snippet(name={self.name!r}, type_name={self.type_name!r}, "
            f"fields={list(self.snippet_map_fields.keys())!r}, pins={len(self.pins)})"
        )


class SnippetMap:
    source: Path
    date: datetime
    tool: str

    root_snippet: Snippet
    snippets: Set[Snippet]

    def __repr__(self) -> str:
        return (
            f"SnippetMap(source={self.source!r}, date={self.date.isoformat()}, "
            f"tool={self.tool!r}, root_snippet={self.root_snippet.name!r}, "
            f"snippets={len(self.snippets)})"
        )


class RawSnippet:
    name: SnippetName
    type_name: SnippetType
    # Map key to value.
    snippet_map_fields: Dict[str, str]

    components: Set[Component]

    def __repr__(self) -> str:
        return (
            f"RawSnippet(name={self.name!r}, type_name={self.type_name!r}, "
            f"fields={list(self.snippet_map_fields.keys())!r}, components={len(self.components)})"
        )


# mapping from snippet name to the info we can directly pull from the KiCad netlist
SnippetsLookup = NewType("SnippetsLookup", Dict[SnippetName, RawSnippet])
# mapping from component ref to snippet name
SnippetsReverseLookup = NewType(
    "SnippetsReverseLookup", Dict[ComponentRef, SnippetName]
)
# For each snippet this resolves the pins global identifier to the explicitly chosen pin name.
SnippetPinNameLookups = NewType(
    "SnippetPinNameLookups",
    Dict[SnippetName, Dict[GlobalPinIdentifier, SnippetPinName]],
)


def group_components_by_snippet(
    netlist: Netlist,
) -> Tuple[SnippetsLookup, SnippetsReverseLookup]:
    snippets = SnippetsLookup(dict())
    reverse_lookup = SnippetsReverseLookup(dict())
    for component in netlist.components.values():
        if SNIPPET_TYPE_FIELD_NAME not in component.fields:
            false_friend_fields = [
                field
                for field in component.fields.keys()
                if field.startswith(SNIPPET_PIN_FIELD_PREFIX)
                or field.startswith(SNIPPET_MAP_FIELD_PREFIX)
            ]
            if len(false_friend_fields) != 0:
                print(
                    f"Warning: The component {component.ref} defines the {'fields' if len(false_friend_fields) > 1 else 'field'} {', '.join(false_friend_fields)} but not the field {SNIPPET_TYPE_FIELD_NAME}.\n"
                    "Therefore, it is not part of a snippet.",
                    file=sys.stderr,
                )

            # This component is not part of any snippet.
            continue
        snippet_type = SnippetType(component.fields[SNIPPET_TYPE_FIELD_NAME])
        snippet_name = SnippetName(f"{component.sheetpath}{snippet_type}")

        if snippet_name not in snippets:
            snippets[snippet_name] = RawSnippet()
            snippets[snippet_name].name = snippet_name
            snippets[snippet_name].type_name = snippet_type
            snippets[snippet_name].components = {component}
        else:
            snippets[snippet_name].components.add(component)

        snippets[snippet_name].snippet_map_fields = dict()
        for field_name, field_value in component.fields.items():
            if not field_name.startswith(SNIPPET_MAP_FIELD_PREFIX):
                # This is not a SnippetMapField.
                continue
            snippet_map_field_name = field_name[len(SNIPPET_MAP_FIELD_PREFIX) :]
            if snippet_map_field_name in snippets[snippet_name].snippet_map_fields:
                print(
                    f"Error: The snippet {snippet_name} contains the SnippetMapField {snippet_map_field_name} twice.\n"
                    f"They have the values {field_value} and {snippets[snippet_name].snippet_map_fields[snippet_map_field_name]}.\n"
                    f"One is in component {component.ref}.",
                    file=sys.stderr,
                )
                sys.exit(1)
            snippets[snippet_name].snippet_map_fields[snippet_map_field_name] = (
                field_value
            )

        assert component.ref not in reverse_lookup
        reverse_lookup[component.ref] = snippet_name

    return (snippets, reverse_lookup)


# Snippets without a explicit naming don't appear in this dict.
def get_explicit_pin_name_lookups(
    snippets_lookup: SnippetsLookup,
) -> SnippetPinNameLookups:
    explicit_pin_namings = SnippetPinNameLookups(dict())
    for snippet_name, raw_snippet in snippets_lookup.items():
        # Use this set to verify no SnippetPin name is used twice for the same snippet.
        snippet_pin_names: Set[SnippetPinName] = set()
        for component in raw_snippet.components:
            for field_name, field_value in component.fields.items():
                # Only consider field names that define explic SnippetPin names.
                if not field_name.startswith(SNIPPET_PIN_FIELD_PREFIX):
                    continue

                # After the SnippetPin prefix comes the pin shown in KiCad that belongs to the component.
                node_pin_name = NodePinName(field_name[len(SNIPPET_PIN_FIELD_PREFIX) :])
                global_pin_identifier = GlobalPinIdentifier((
                    component.ref,
                    node_pin_name,
                ))
                # We can't have the same globally unique reference for two pins.
                for other_expicit_in_naming_snippet in explicit_pin_namings.values():
                    assert global_pin_identifier not in other_expicit_in_naming_snippet

                # This is the name the user explicitly set for this pin.
                snippet_pin_name = SnippetPinName(field_value)
                if snippet_pin_name in snippet_pin_names:
                    print(
                        f"Error: The SnippetPin {snippet_pin_name} exists twice for the snippet {snippet_name}.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                snippet_pin_names.add(snippet_pin_name)

                # update explicit_pin_namings
                if snippet_name in explicit_pin_namings:
                    explicit_pin_namings[snippet_name][global_pin_identifier] = (
                        snippet_pin_name
                    )
                else:
                    explicit_pin_namings[snippet_name] = {
                        global_pin_identifier: snippet_pin_name
                    }
    return explicit_pin_namings


# The KiCad netlist connects pins on components to other pins on other components.
# This function converts that netlist into a netlist that connects pins on snippets to other pins on other snippets.
# The names of the pins are the SnippetPin names and not the KiCad pin names any longer.
def convert_netlist(
    netlist: Netlist,
    snippets_lookup: SnippetsLookup,
    snippets_reverse_lookup: SnippetsReverseLookup,
) -> SnippetNetList:
    explicit_pin_name_lookups = get_explicit_pin_name_lookups(snippets_lookup)

    # We only use this to check that no two components have the same global snippet pin identifier.
    global_snippet_pin_to_component: Dict[GlobalSnippetPinIdentifier, ComponentRef] = (
        dict()
    )

    snippet_netlist = SnippetNetList(set())
    for net in netlist.nets:
        snippet_net = MutableSnippetNet(set())
        for node in net.nodes:
            if node.ref not in snippets_reverse_lookup:
                # The node does not belong to a component that belongs to a snippet.
                continue
            snippet_name = snippets_reverse_lookup[node.ref]
            global_pin_identifier = GlobalPinIdentifier((node.ref, node.pin))

            # Figure out what name this pin has.
            snippet_pin_name: SnippetPinName
            if snippet_name in explicit_pin_name_lookups:
                explicit_pin_name_lookup = explicit_pin_name_lookups[snippet_name]
                if global_pin_identifier not in explicit_pin_name_lookup:
                    # The pin does belong to components that belong to the snippet.
                    # Nevertheless, the user chose to explicitly define SnippetPin names to some of the snippet's pins and this pin doesn't have one.
                    # Therefore, we don't consider this pin to belong to the snippet.
                    continue
                snippet_pin_name = explicit_pin_name_lookup[global_pin_identifier]
            else:
                # When the user didn't define any SnippetPin names for at all we use a fallback:
                # We consider all pins that belong to components that belong to the snippet as pins of the snippet.
                snippet_pin_name = SnippetPinName(node.pinfunction)
            # This uniquely identifies the pin in the entire snippet map.
            global_snippet_pin_identifier = GlobalSnippetPinIdentifier((
                snippet_name,
                snippet_pin_name,
            ))

            if (
                global_snippet_pin_identifier in global_snippet_pin_to_component
                and global_snippet_pin_to_component[global_snippet_pin_identifier]
                != node.ref
            ):
                print(
                    f"Error: The pin {snippet_pin_name} in the snippet {snippet_name} occurs in multiple components: {global_snippet_pin_to_component[global_snippet_pin_identifier]} and {node.ref}.",
                    file=sys.stderr,
                )
                sys.exit(1)
            global_snippet_pin_to_component[global_snippet_pin_identifier] = node.ref

            # This might very well be the only pin in the snippet net.
            snippet_net.add(global_snippet_pin_identifier)
        snippet_netlist.add(SnippetNet(frozenset(snippet_net)))
    return snippet_netlist


def gen_snippet_map(netlist: Netlist, root_snippet_name: SnippetName) -> SnippetMap:
    raw_snippets_lookup, snippets_reverse_lookup = group_components_by_snippet(netlist)
    snippet_netlist = convert_netlist(
        netlist, raw_snippets_lookup, snippets_reverse_lookup
    )

    # general metadata
    snippet_map = SnippetMap()
    snippet_map.source = netlist.source
    snippet_map.date = datetime.now()
    snippet_map.tool = TOOL_NAME

    if root_snippet_name not in raw_snippets_lookup:
        all_snippet_names = ", ".join([
            snippet.name for snippet in raw_snippets_lookup.values()
        ])
        all_snippet_print = (
            f"There are no snippets. Define them by specifying at least one component with the {SNIPPET_TYPE_FIELD_NAME} field."
            if len(all_snippet_names) == 0
            else f"These snippets exist: {all_snippet_names}"
        )
        print(
            f"Error: Didn't find a root snippet with name {root_snippet_name}.\n{all_snippet_print}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Create representations for all snippets without their pins.
    # This includes the root snippet.
    # same as raw_snippets_lookup but this time with the final Snippet class
    snippets_lookup: Dict[SnippetName, Snippet] = dict()
    for raw_snippet in raw_snippets_lookup.values():
        snippet = Snippet()
        snippet.name = raw_snippet.name
        snippet.type_name = raw_snippet.type_name
        snippet.snippet_map_fields = raw_snippet.snippet_map_fields
        snippet.pins = dict()
        snippets_lookup[snippet.name] = snippet

    # Figure out what snippets are connected how.
    for net in snippet_netlist:
        # Some nets contain a root snippet pin, other don't.
        root_snippet_pin_name: SnippetPinName | None = None
        for snippet_name, snippet_pin_name in net:
            # Does this pin belong to the root snippet?
            if snippet_name == root_snippet_name:
                if root_snippet_pin_name is not None:
                    print(
                        f"Warning: At least two pins of the root snippet {root_snippet_name}, {snippet_pin_name} and {root_snippet_pin_name} are connected together.\n"
                        "The entire net these pins are connected to will not be part of the snippet map.",
                        file=sys.stderr,
                    )
                    root_snippet_pin_name = None
                    break
                root_snippet_pin_name = snippet_pin_name

        for snippet_name, snippet_pin_name in net:
            # Does this pin belong to the root snippet?
            if snippet_name == root_snippet_name:
                # We've already figured out what root pin this net is connected to.
                # All we have to do is make sure the root snippet has this pin, too.
                snippets_lookup[snippet_name].pins[snippet_pin_name] = None
                continue
            assert snippet_pin_name not in snippets_lookup[snippet_name].pins
            # Because we only do this when this isn't a root snippet, all pins of the root snippet are connected to None.
            snippets_lookup[snippet_name].pins[snippet_pin_name] = root_snippet_pin_name

    snippet_map.snippets = {
        snippet
        for snippet in snippets_lookup.values()
        if snippet.name != root_snippet_name
    }
    assert root_snippet_name not in {snippet.name for snippet in snippet_map.snippets}
    snippet_map.root_snippet = snippets_lookup[root_snippet_name]

    return snippet_map


def parse_netlist(netlist_path: Path) -> Netlist:
    netlist = Netlist()

    tree = ET.parse(netlist_path)
    root = tree.getroot()

    source_tags = root.findall("./design/source")
    assert len(source_tags) == 1
    assert source_tags[0].text is not None
    netlist.source = Path(source_tags[0].text)

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


def stringify_snippet(snippet: Snippet, tag_name: str) -> ET.Element:
    root = ET.Element(tag_name)
    root.set("name", snippet.name)
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


def stringify_snippet_map(snippet_map: SnippetMap) -> ET.Element:
    root = ET.Element("snippetMap")

    netlist = ET.SubElement(root, "netlist")
    source = ET.SubElement(netlist, "source")
    source.text = str(snippet_map.source)
    date = ET.SubElement(netlist, "date")
    date.text = snippet_map.date.isoformat()
    tool = ET.SubElement(netlist, "tool")
    tool.text = snippet_map.tool

    root_snippet = stringify_snippet(snippet_map.root_snippet, "rootSnippet")
    root.append(root_snippet)

    xml_snippets = ET.SubElement(root, "snippet")
    # Ensure xml is deterministic.
    snippets = list(snippet_map.snippets)
    snippets.sort(key=lambda s: s.name)
    for snippet in snippets:
        xml_snippet = stringify_snippet(snippet, "snippet")
        xml_snippets.append(xml_snippet)

    ET.indent(root, space="    ", level=0)
    return root


def main() -> None:
    if len(sys.argv) != 3:
        print(
            "Error: Provide two arguments: the input file path and the root snippet name",
            file=sys.stderr,
        )
        sys.exit(1)
    netlist_path = Path(sys.argv[1])
    root_snippet_name = SnippetName(sys.argv[2])
    netlist = parse_netlist(netlist_path)
    snippet_map = gen_snippet_map(netlist, root_snippet_name)
    ET.dump(stringify_snippet_map(snippet_map))


if __name__ == "__main__":
    main()
