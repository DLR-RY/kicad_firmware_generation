import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Set

from common_types.parse_xml import parse_snippet_netlist
from common_types.snippet_types import (
    GlobalSnippetPinIdentifier,
    OtherSnippetPinType,
    SnippetIdentifier,
    SnippetMap,
    SnippetNetlist,
    SnippetPath,
    SnippetPinName,
    SnippetType,
    SnippetGlob,
    does_match_pattern,
    compile_snippet_glob,
)
from common_types.stringify_xml import stringify_snippet_map

# TODO: set this properly
TOOL_NAME = "snippet_many_to_many_mapper v0.1.0"


def _gen_many_to_many_snippet_map(
    netlist: SnippetNetlist,
    root_snippet_pattern: SnippetGlob | None,
    simplify_pins: Set[SnippetPinName],
) -> SnippetMap:
    # general metadata
    snippet_map = SnippetMap()
    snippet_map.map_type = OtherSnippetPinType.MANY_TO_MANY
    snippet_map.source = netlist.source
    snippet_map.date = datetime.now()
    snippet_map.tool = TOOL_NAME
    snippet_map.root_snippet = None

    # Figure out what snippets are connected how.
    for net in netlist.nets:
        for snippet_identifier, snippet_pin_name in net:
            # No one has touched this before so it must have remained None.
            assert netlist.snippets[snippet_identifier].pins[snippet_pin_name] is None
            netlist.snippets[snippet_identifier].pins[snippet_pin_name] = {
                other_pin
                for other_pin in net
                # Skip the own pin.
                if other_pin
                != GlobalSnippetPinIdentifier((snippet_identifier, snippet_pin_name))
                # Skip other
                and not does_match_pattern(root_snippet_pattern, other_pin[0], False)
            }

    # Simplify some nets.
    for snippet in netlist.snippets.values():
        for pin in snippet.pins.values():
            # Check if this net can be simplified.

            # Should be Set[GlobalSnippetPinIdentifier] but that isn't konwn at runtime.
            assert type(pin) is set
            # Not None iff we found a simplification.
            found_simplify_pin: SnippetPinName | None = None
            for _, other_pin in pin:
                for simplify_pin in simplify_pins:
                    if simplify_pin in other_pin:
                        found_simplify_pin = simplify_pin
                        print(
                            f"Warning: Simplifying {other_pin} to {found_simplify_pin}",
                            file=sys.stderr,
                        )
                        break
                if found_simplify_pin is not None:
                    break
            if found_simplify_pin is not None:
                pin.clear()
                pin.add(
                    GlobalSnippetPinIdentifier((
                        SnippetIdentifier((
                            # TODO: do this better
                            SnippetPath("/Simplified/"),
                            SnippetType("Away"),
                        )),
                        found_simplify_pin,
                    ))
                )

    snippet_map.snippets = {
        snippet
        for snippet in netlist.snippets.values()
        if does_match_pattern(root_snippet_pattern, snippet.get_id(), True)
    }
    return snippet_map


def main() -> None:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Generate an overview over every snippet consisting of what all the snippet's pins are connected to.",
    )
    parser.add_argument(
        "snippet_netlist_input", help="The path to the snippet_netlist."
    )
    parser.add_argument(
        "--root-snippet-glob",
        help="From what snippets' perspective should the output be? "
        "This field is a glob. Use ** to match multiple path nodes. "
        "If this field is provided, only snippets that don't match are considered as other snippets. "
        "I.e., connections from matched snippets to other matched snippets are ignored. "
        "If this isn't provided, all snippets will be included.",
    )
    parser.add_argument(
        "--simplify-pins",
        help="If a snippet connects to a pin that has this field as a substring, reduce all pins that belong to this net to a single pin with the provided name. "
        "Separate multiple values with a comma (,). "
        "When more than on simplification matches, an arbitraty one will be chosen."
        "This is, for example, useful to replace all GND connections with a single GND pin.",
    )
    args = parser.parse_args()

    snippet_netlist_path = Path(args.snippet_netlist_input)
    root_snippet_glob = (
        None
        if args.root_snippet_glob is None
        else compile_snippet_glob(args.root_snippet_glob)
    )
    simplify_pins: Set[SnippetPinName] = {
        SnippetPinName(pin)
        for pin in ([] if args.simplify_pins is None else args.simplify_pins.split(","))
    }

    snippet_netlist = parse_snippet_netlist(snippet_netlist_path)
    snippet_map = _gen_many_to_many_snippet_map(
        snippet_netlist, root_snippet_glob, simplify_pins
    )
    sys.stdout.buffer.write(stringify_snippet_map(snippet_map))


if __name__ == "__main__":
    main()
