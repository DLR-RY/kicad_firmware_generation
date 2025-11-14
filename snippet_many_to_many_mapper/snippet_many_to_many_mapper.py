import sys
from datetime import datetime
from pathlib import Path

from common_types.snippet_xml import stringify_snippet_map, parse_snippet_netlist
from common_types.snippet_types import (
    GlobalSnippetPinIdentifier,
    SnippetMap,
    SnippetNetlist,
    OtherSnippetPinType,
)

# TODO: set this properly
TOOL_NAME = "snippet_many_to_many_mapper v0.1.0"


def _gen_many_to_many_snippet_map(netlist: SnippetNetlist) -> SnippetMap:
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
            }

    snippet_map.snippets = {snippet for snippet in netlist.snippets.values()}
    return snippet_map


def main() -> None:
    if len(sys.argv) != 2:
        print(
            "Error: Provide one arguments: the input snippet netlist file path.",
            file=sys.stderr,
        )
        sys.exit(1)
    snippet_netlist_path = Path(sys.argv[1])
    snippet_netlist = parse_snippet_netlist(snippet_netlist_path)
    snippet_map = _gen_many_to_many_snippet_map(snippet_netlist)
    sys.stdout.buffer.write(stringify_snippet_map(snippet_map))


if __name__ == "__main__":
    main()
