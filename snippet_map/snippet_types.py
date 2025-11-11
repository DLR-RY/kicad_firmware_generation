from datetime import datetime
from pathlib import Path
from typing import Dict, FrozenSet, List, NewType, Set, Tuple

"""
The path's nodes are separated with `/`.
There must be a leading slash and no trailing slash.
"""
SnippetPath = NewType("SnippetPath", str)
SnippetPathNode = NewType("SnippetPathNode", str)
SnippetType = NewType("SnippetType", str)
SnippetIdentifier = NewType("SnippetIdentifier", Tuple[SnippetPath, SnippetType])
SnippetPinName = NewType("SnippetPinName", str)

GlobalSnippetPinIdentifier = NewType(
    "GlobalSnippetPinIdentifier", Tuple[SnippetIdentifier, SnippetPinName]
)
"""
These pins are connected.
"""
MutableSnippetNet = NewType("MutableSnippetNet", Set[GlobalSnippetPinIdentifier])
SnippetNet = NewType("SnippetNet", FrozenSet[GlobalSnippetPinIdentifier])
SnippetNetList = NewType("SnippetNetList", Set[SnippetNet])


class Snippet:
    path: SnippetPath
    type_name: SnippetType
    """
    Map key to value.
    """
    snippet_map_fields: Dict[str, str]
    """
    Map snippet pin name to connected root snippet pin name.
    If this is the root snippet the value is always None.
    """
    pins: Dict[SnippetPinName, SnippetPinName | None]

    def get_id(self) -> SnippetIdentifier:
        return SnippetIdentifier((self.path, self.type_name))

    def __repr__(self) -> str:
        return (
            f"Snippet(path={self.path!r}, type_name={self.type_name!r}, "
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
            f"tool={self.tool!r}, root_snippet={stringify_snippet_id(self.root_snippet.get_id())!r}, "
            f"snippets={len(self.snippets)})"
        )


def stringify_snippet_id(id: SnippetIdentifier) -> str:
    return f"{id[0]}{id[1]}"


def split_snippet_path(path: SnippetPath) -> List[SnippetPathNode]:
    assert len(path) >= 1
    assert path[0] == "/"
    assert path[-1] == "/"
    return [SnippetPathNode(node_str) for node_str in path.split("/")]
