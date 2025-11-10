from typing import Dict, NewType, Set

from .kicad_types import Component, ComponentRef, GlobalPinIdentifier
from ..snippet_map.snippet_types import (
    SnippetIdentifier,
    SnippetPath,
    SnippetPinName,
    SnippetType,
)


class RawSnippet:
    path: SnippetPath
    type_name: SnippetType
    # Map key to value.
    snippet_map_fields: Dict[str, str]

    components: Set[Component]

    def get_id(self) -> SnippetIdentifier:
        return SnippetIdentifier((self.path, self.type_name))

    def __repr__(self) -> str:
        return (
            f"RawSnippet(path={self.path!r}, type_name={self.type_name!r}, "
            f"fields={list(self.snippet_map_fields.keys())!r}, components={len(self.components)})"
        )


# mapping from snippet name to the info we can directly pull from the KiCad netlist
SnippetsLookup = NewType("SnippetsLookup", Dict[SnippetIdentifier, RawSnippet])
# mapping from component ref to snippet name
SnippetsReverseLookup = NewType(
    "SnippetsReverseLookup", Dict[ComponentRef, SnippetIdentifier]
)
# For each snippet this resolves the pins global identifier to the explicitly chosen pin name.
SnippetPinNameLookups = NewType(
    "SnippetPinNameLookups",
    Dict[SnippetIdentifier, Dict[GlobalPinIdentifier, SnippetPinName]],
)
