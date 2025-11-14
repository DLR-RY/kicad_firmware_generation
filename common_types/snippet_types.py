from datetime import datetime
from enum import Enum
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


class Snippet:
    path: SnippetPath
    type_name: SnippetType
    """
    Map key to value.
    """
    snippet_map_fields: Dict[str, str]
    """
    If we are generating a one-to-many map (OtherSnippetPinType.ONE_TO_MANY), map snippet pin name to connected root snippet pin name.
    If this is the root snippet the value is always None.
    If we are generating a snippet netlist (OtherSnippetPinType.NO_PINS), the value is also always None.
    If we are generating a many-to-many map (OtherSnippetPinType.MANY_TO_MANY), the value is a set of all connected pins.
    """
    pins: Dict[SnippetPinName, SnippetPinName | None | Set[GlobalSnippetPinIdentifier]]

    def get_id(self) -> SnippetIdentifier:
        return SnippetIdentifier((self.path, self.type_name))

    def __repr__(self) -> str:
        return (
            f"Snippet(path={self.path!r}, type_name={self.type_name!r}, "
            f"fields={list(self.snippet_map_fields.keys())!r}, pins={len(self.pins)})"
        )


class OtherSnippetPinType(Enum):
    NO_OTHER_PINS = "NO_OTHER_PINS"
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_MANY = "MANY_TO_MANY"


class SnippetMap:
    map_type: OtherSnippetPinType

    source: Path
    date: datetime
    tool: str

    """
    None iff this is a many-to-many snippet map.
    """
    root_snippet: Snippet | None
    snippets: Set[Snippet]

    def __repr__(self) -> str:
        return (
            f"SnippetMap(source={self.source!r}, date={self.date.isoformat()}, "
            f"tool={self.tool!r}, root_snippet={None if self.root_snippet is None else stringify_snippet_id(self.root_snippet.get_id())!r}, "
            f"snippets={len(self.snippets)})"
        )


class SnippetNetlist:
    """
    Represent what snippets there are and how they are connected.
    """

    source: Path
    date: datetime
    tool: str

    """
    All snippets have pins with None set as the rootPinName
    """
    snippets: Dict[SnippetIdentifier, Snippet]
    nets: Set[SnippetNet]


def stringify_snippet_id(id: SnippetIdentifier) -> str:
    return f"{id[0]}{id[1]}"


def split_snippet_path(path: SnippetPath) -> List[SnippetPathNode]:
    assert len(path) >= 1
    assert path[0] == "/"
    assert path[-1] == "/"
    return [SnippetPathNode(node_str) for node_str in path.split("/")]
