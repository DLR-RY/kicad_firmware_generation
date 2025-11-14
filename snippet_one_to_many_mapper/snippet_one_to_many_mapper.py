import sys
from datetime import datetime
from pathlib import Path

from common_types.parse_xml import parse_snippet_netlist
from common_types.snippet_types import (
    OtherSnippetPinType,
    SnippetIdentifier,
    SnippetMap,
    SnippetNetlist,
    SnippetPath,
    SnippetPinName,
    SnippetType,
    stringify_snippet_id,
)
from common_types.stringify_xml import stringify_snippet_map

SNIPPET_TYPE_FIELD_NAME = "SnippetType"
# TODO: set this properly
TOOL_NAME = "snippet_one_to_many_mapper v0.1.0"


def _gen_one_to_many_snippet_map(
    netlist: SnippetNetlist, root_snippet_identifier: SnippetIdentifier
) -> SnippetMap:
    # general metadata
    snippet_map = SnippetMap()
    snippet_map.map_type = OtherSnippetPinType.ONE_TO_MANY
    snippet_map.source = netlist.source
    snippet_map.date = datetime.now()
    snippet_map.tool = TOOL_NAME

    if root_snippet_identifier not in netlist.snippets:
        all_snippet_identifiers = ", ".join([
            f"{stringify_snippet_id(snippet_id)}"
            for snippet_id in netlist.snippets.keys()
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

    # Figure out what snippets are connected how.
    for net in netlist.nets:
        # Some nets contain a root snippet pin, others don't.
        root_snippet_pin_name: SnippetPinName | None = None
        for snippet_identifier, snippet_pin_name in net:
            # Does this pin belong to the root snippet?
            if snippet_identifier == root_snippet_identifier:
                if root_snippet_pin_name is not None:
                    print(
                        f"Warning: At least two pins of the root snippet {stringify_snippet_id(root_snippet_identifier)}, {snippet_pin_name} and {root_snippet_pin_name} are connected together.\n"
                        "The entire net these pins are connected to will not be part of the snippet map.",
                        file=sys.stderr,
                    )
                    # Remove those pins from the root snippet.
                    for snippet_id_of_in_to_remove, pin_name_to_remove in net:
                        if snippet_id_of_in_to_remove != root_snippet_pin_name:
                            # Skip all snippets that aren't the root snippet.
                            # Those snippets get to keep all their pins.
                            continue
                        print(snippet_identifier, pin_name_to_remove, file=sys.stderr)
                        netlist.snippets[root_snippet_identifier].pins.pop(
                            pin_name_to_remove
                        )
                    root_snippet_pin_name = None
                    break
                root_snippet_pin_name = snippet_pin_name

        if root_snippet_pin_name is None:
            # We didn't find a root snippet's pin in this net.
            continue

        for snippet_identifier, snippet_pin_name in net:
            # Does this pin belong to the root snippet?
            if snippet_identifier == root_snippet_identifier:
                # We've already figured out what root pin this net is connected to.
                # The root snippet's pins are all set to None already, so we don't have to do anything.
                continue
            # No one has touched this before so it must have remained None.
            assert netlist.snippets[snippet_identifier].pins[snippet_pin_name] is None
            # Because we only do this when this isn't a root snippet, all pins of the root snippet are connected to None.
            netlist.snippets[snippet_identifier].pins[snippet_pin_name] = (
                root_snippet_pin_name
            )

    snippet_map.snippets = {
        snippet
        for snippet in netlist.snippets.values()
        if snippet.get_id() != root_snippet_identifier
    }
    assert root_snippet_identifier not in {
        snippet.get_id() for snippet in snippet_map.snippets
    }
    snippet_map.root_snippet = netlist.snippets[root_snippet_identifier]

    return snippet_map


def _get_snippet_identifier(in_str: str) -> SnippetIdentifier:
    idx = in_str.rfind("/")
    if "/" not in in_str:
        print(
            "Error: snippet identifier must contain at least one `/`.",
            file=sys.stderr,
        )
        sys.exit(1)
    return SnippetIdentifier((
        SnippetPath(in_str[0 : idx + 1]),
        SnippetType(in_str[idx + 1 :]),
    ))


def main() -> None:
    if len(sys.argv) != 3:
        print(
            "Error: Provide two arguments: the input snippet netlist file path and the root snippet name.",
            file=sys.stderr,
        )
        sys.exit(1)
    snippet_netlist_path = Path(sys.argv[1])
    root_snippet_identifier = _get_snippet_identifier(sys.argv[2])
    snippet_netlist = parse_snippet_netlist(snippet_netlist_path)
    snippet_map = _gen_one_to_many_snippet_map(snippet_netlist, root_snippet_identifier)
    sys.stdout.buffer.write(stringify_snippet_map(snippet_map))


if __name__ == "__main__":
    main()
