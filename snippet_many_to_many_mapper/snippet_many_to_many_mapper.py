import sys
from datetime import datetime
from pathlib import Path
from typing import NewType

from common_types.parse_xml import parse_snippet_netlist
from common_types.snippet_types import (
    GlobalSnippetPinIdentifier,
    OtherSnippetPinType,
    SnippetIdentifier,
    SnippetMap,
    SnippetNetlist,
)
from common_types.stringify_xml import stringify_snippet_map

# TODO: set this properly
TOOL_NAME = "snippet_many_to_many_mapper v0.1.0"

SnippetPattern = NewType("SnippetPattern", str)


def _does_match_pattern(
    pattern: SnippetPattern | None, snippet_id: SnippetIdentifier, when_none: bool
) -> bool:
    if pattern is None:
        return when_none
    # TODO
    return True


def _gen_many_to_many_snippet_map(
    netlist: SnippetNetlist, root_snippet_pattern: SnippetPattern | None
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
                and not _does_match_pattern(root_snippet_pattern, other_pin[0], False)
            }

    snippet_map.snippets = {
        snippet
        for snippet in netlist.snippets.values()
        if _does_match_pattern(root_snippet_pattern, snippet.get_id(), True)
    }
    return snippet_map


def main() -> None:
    if len(sys.argv) != 2 and len(sys.argv) != 3:
        print(
            "Error: Provide one or two arguments: the input snippet netlist file path and optionally the root snippet pattern.",
            file=sys.stderr,
        )
        sys.exit(1)
    snippet_netlist_path = Path(sys.argv[1])
    root_snippet_pattern = SnippetPattern(sys.argv[2]) if len(sys.argv) == 3 else None
    snippet_netlist = parse_snippet_netlist(snippet_netlist_path)
    snippet_map = _gen_many_to_many_snippet_map(snippet_netlist, root_snippet_pattern)
    sys.stdout.buffer.write(stringify_snippet_map(snippet_map))


if __name__ == "__main__":
    main()
