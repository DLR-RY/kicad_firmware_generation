import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Set, Tuple

from .intermediate_types import (
    RawSnippet,
    SnippetPinNameLookups,
    SnippetsLookup,
    SnippetsReverseLookup,
)
from .kicad_types import (
    ComponentRef,
    GlobalPinIdentifier,
    Netlist,
    NodePinName,
    SheetPath,
)
from ..snippet_map.snippet_types import (
    GlobalSnippetPinIdentifier,
    MutableSnippetNet,
    Snippet,
    SnippetIdentifier,
    SnippetMap,
    SnippetNet,
    SnippetNetList,
    SnippetPath,
    SnippetPinName,
    SnippetType,
    stringify_snippet_id,
)
from .netlist_xml import parse_netlist
from ..snippet_map.snippet_map_xml import stringify_snippet_map

SNIPPET_TYPE_FIELD_NAME = "SnippetType"
SNIPPET_PIN_FIELD_PREFIX = "SnippetPin"
SNIPPET_MAP_FIELD_PREFIX = "SnippetMapField"
# TODO: set this properly
TOOL_NAME = "kicad_snippet_mapper v0.1.0"


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
        snippet_path = SnippetPath(component.sheetpath.rstrip("/"))
        assert snippet_path[0] == "/"
        snippet_identifier = SnippetIdentifier((snippet_path, snippet_type))

        if snippet_identifier not in snippets:
            snippets[snippet_identifier] = RawSnippet()
            snippets[snippet_identifier].path = snippet_path
            snippets[snippet_identifier].type_name = snippet_type
            snippets[snippet_identifier].components = {component}
        else:
            snippets[snippet_identifier].components.add(component)

        snippets[snippet_identifier].snippet_map_fields = dict()
        for field_name, field_value in component.fields.items():
            if not field_name.startswith(SNIPPET_MAP_FIELD_PREFIX):
                # This is not a SnippetMapField.
                continue
            snippet_map_field_name = field_name[len(SNIPPET_MAP_FIELD_PREFIX) :]
            if len(snippet_map_field_name) == 0:
                print(
                    f"Warning: The snippet {stringify_snippet_id(snippet_identifier)} contains a SnippetMapField with the empty string as key.",
                    file=sys.stderr,
                )
            if (
                snippet_map_field_name
                in snippets[snippet_identifier].snippet_map_fields
            ):
                print(
                    f"Error: The snippet {stringify_snippet_id(snippet_identifier)} contains the SnippetMapField {snippet_map_field_name} twice.\n"
                    f"They have the values {field_value} and {snippets[snippet_identifier].snippet_map_fields[snippet_map_field_name]}.\n"
                    f"One is in component {component.ref}.",
                    file=sys.stderr,
                )
                sys.exit(1)
            snippets[snippet_identifier].snippet_map_fields[snippet_map_field_name] = (
                field_value
            )

        assert component.ref not in reverse_lookup
        reverse_lookup[component.ref] = snippet_identifier

    return (snippets, reverse_lookup)


# Snippets without a explicit naming don't appear in this dict.
def get_explicit_pin_name_lookups(
    snippets_lookup: SnippetsLookup,
) -> SnippetPinNameLookups:
    explicit_pin_namings = SnippetPinNameLookups(dict())
    for snippet_identifier, raw_snippet in snippets_lookup.items():
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
                        f"Error: The SnippetPin {snippet_pin_name} exists at least twice for the snippet {stringify_snippet_id(snippet_identifier)}.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                snippet_pin_names.add(snippet_pin_name)

                # update explicit_pin_namings
                if snippet_identifier in explicit_pin_namings:
                    explicit_pin_namings[snippet_identifier][global_pin_identifier] = (
                        snippet_pin_name
                    )
                else:
                    explicit_pin_namings[snippet_identifier] = {
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
            snippet_identifier = snippets_reverse_lookup[node.ref]
            global_pin_identifier = GlobalPinIdentifier((node.ref, node.pin))

            # Figure out what name this pin has.
            snippet_pin_name: SnippetPinName
            if snippet_identifier in explicit_pin_name_lookups:
                explicit_pin_name_lookup = explicit_pin_name_lookups[snippet_identifier]
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
                snippet_identifier,
                snippet_pin_name,
            ))

            if (
                global_snippet_pin_identifier in global_snippet_pin_to_component
                and global_snippet_pin_to_component[global_snippet_pin_identifier]
                != node.ref
            ):
                print(
                    f"Error: The pin {snippet_pin_name} in the snippet {stringify_snippet_id(snippet_identifier)} occurs in multiple components: {global_snippet_pin_to_component[global_snippet_pin_identifier]} and {node.ref}.",
                    file=sys.stderr,
                )
                sys.exit(1)
            global_snippet_pin_to_component[global_snippet_pin_identifier] = node.ref

            # This might very well be the only pin in the snippet net.
            snippet_net.add(global_snippet_pin_identifier)
        snippet_netlist.add(SnippetNet(frozenset(snippet_net)))
    return snippet_netlist


def gen_snippet_map(
    netlist: Netlist, root_snippet_identifier: SnippetIdentifier
) -> SnippetMap:
    raw_snippets_lookup, snippets_reverse_lookup = group_components_by_snippet(netlist)
    snippet_netlist = convert_netlist(
        netlist, raw_snippets_lookup, snippets_reverse_lookup
    )

    # general metadata
    snippet_map = SnippetMap()
    snippet_map.source = netlist.source
    snippet_map.date = datetime.now()
    snippet_map.tool = TOOL_NAME

    if root_snippet_identifier not in raw_snippets_lookup:
        all_snippet_identifiers = ", ".join([
            f"{stringify_snippet_id(snippet.get_id())}"
            for snippet in raw_snippets_lookup.values()
        ])
        all_snippet_print = (
            f"There are no snippets. Define them by specifying at least one component with the {SNIPPET_TYPE_FIELD_NAME} field."
            if len(all_snippet_identifiers) == 0
            else f"These snippets exist: {all_snippet_identifiers}"
        )
        print(
            f"Error: Didn't find a root snippet with identifier {stringify_snippet_id(root_snippet_identifier)}.\n{all_snippet_print}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Create representations for all snippets without their pins.
    # This includes the root snippet.
    # same as raw_snippets_lookup but this time with the final Snippet class
    snippets_lookup: Dict[SnippetIdentifier, Snippet] = dict()
    for raw_snippet in raw_snippets_lookup.values():
        snippet = Snippet()
        snippet.path = raw_snippet.path
        snippet.type_name = raw_snippet.type_name
        snippet.snippet_map_fields = raw_snippet.snippet_map_fields
        snippet.pins = dict()
        snippets_lookup[SnippetIdentifier((snippet.path, snippet.type_name))] = snippet

    # Figure out what snippets are connected how.
    for net in snippet_netlist:
        # Some nets contain a root snippet pin, other don't.
        root_snippet_pin_name: SnippetPinName | None = None
        skip_net = False
        for snippet_identifier, snippet_pin_name in net:
            # Does this pin belong to the root snippet?
            if snippet_identifier == root_snippet_identifier:
                if root_snippet_pin_name is not None:
                    print(
                        f"Warning: At least two pins of the root snippet {stringify_snippet_id(root_snippet_identifier)}, {snippet_pin_name} and {root_snippet_pin_name} are connected together.\n"
                        "The entire net these pins are connected to will not be part of the snippet map.",
                        file=sys.stderr,
                    )
                    root_snippet_pin_name = None
                    skip_net = True
                    break
                root_snippet_pin_name = snippet_pin_name

        if skip_net:
            continue

        for snippet_identifier, snippet_pin_name in net:
            # Does this pin belong to the root snippet?
            if snippet_identifier == root_snippet_identifier:
                # We've already figured out what root pin this net is connected to.
                # All we have to do is make sure the root snippet has this pin, too.
                snippets_lookup[snippet_identifier].pins[snippet_pin_name] = None
                continue
            assert snippet_pin_name not in snippets_lookup[snippet_identifier].pins
            # Because we only do this when this isn't a root snippet, all pins of the root snippet are connected to None.
            snippets_lookup[snippet_identifier].pins[snippet_pin_name] = (
                root_snippet_pin_name
            )

    for snippet in snippets_lookup.values():
        if len(snippet.pins) == 0:
            print(
                f"Warning: The snippet {stringify_snippet_id(snippet.get_id())} has no pins.",
                file=sys.stderr,
            )

    snippet_map.snippets = {
        snippet
        for snippet in snippets_lookup.values()
        if SnippetIdentifier((snippet.path, snippet.type_name))
        != root_snippet_identifier
    }
    assert root_snippet_identifier not in {
        SnippetIdentifier((snippet.path, snippet.type_name))
        for snippet in snippet_map.snippets
    }
    snippet_map.root_snippet = snippets_lookup[root_snippet_identifier]

    return snippet_map


# There are a few stupid things one can do with a netlist.
# This function ensures the electrical engineer didn't do such things and exits otherwise.
def check_netlist_structure(netlist: Netlist) -> None:
    sheet_paths: Set[SheetPath] = set()
    # The first element is required path and second is the requiring path.
    required_paths: Set[Tuple[SheetPath, SheetPath]] = set()

    for sheet in netlist.sheets:
        # The root sheet has path `/`.
        # Any other sheet has a path like `/asfd/`.
        assert len(sheet.path) >= 1
        assert sheet.path[0] == "/"
        assert sheet.path[-1] == "/"

        if sheet.path in sheet_paths:
            print(
                f"Error: two sheets have the same path {sheet.path}.",
                file=sys.stderr,
            )
            sys.exit(1)
        sheet_paths.add(sheet.path)

        nodes = sheet.path.split("/")
        assert len(nodes) > 0
        if len(nodes) > 0:
            required_paths.add((
                SheetPath("/".join(nodes[0:-2]) + "/"),
                sheet.path,
            ))

    for required_path, requiring_path in required_paths:
        if required_path not in sheet_paths:
            # TODO: read the schematics file directly and figure this out perfectly.
            print(
                f"Warning: The the last node of sheet path {requiring_path} uses the character `/`. "
                "This is not allowed because then separating path nodes isn't possible. "
                f"The script knows this because it didn't find {required_path}. ",
                "You need to fix this as this should be an error! ",
                "Though, this is a warning because there are situations in which the script doesn't notice the user's stupidity. ",
                "You need to watch out for this yourself.",
                file=sys.stderr,
            )
            sys.exit(1)


def get_snippet_identifier(in_str: str) -> SnippetIdentifier:
    idx = in_str.rfind("/")
    if "/" not in in_str:
        print(
            "Error: snippet identifier must contain at least one `/`.",
            file=sys.stderr,
        )
        sys.exit(1)
    return SnippetIdentifier((
        SnippetPath(in_str[0:idx]),
        SnippetType(in_str[idx + 1 :]),
    ))


def main() -> None:
    if len(sys.argv) != 3:
        print(
            "Error: Provide two arguments: the input file path and the root snippet name.",
            file=sys.stderr,
        )
        sys.exit(1)
    netlist_path = Path(sys.argv[1])
    root_snippet_identifier = get_snippet_identifier(sys.argv[2])
    netlist = parse_netlist(netlist_path)
    check_netlist_structure(netlist)
    snippet_map = gen_snippet_map(netlist, root_snippet_identifier)
    sys.stdout.buffer.write(stringify_snippet_map(snippet_map))


if __name__ == "__main__":
    main()
