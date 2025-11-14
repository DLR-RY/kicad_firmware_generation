import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from common_types.snippet_xml import parse_one_to_many_snippet_map
from common_types.snippet_types import (
    SnippetMap,
    SnippetPath,
    split_snippet_path,
)
from code_gen.snippet_sheet import SnippetSheet


def _ensure_snippet_sheet_exists(path: SnippetPath, root: SnippetSheet) -> SnippetSheet:
    assert len(path) >= 1
    assert path[0] == "/"
    assert path[-1] == "/"

    snippet_sheet = root
    # skip the root node and the last slash
    for node in split_snippet_path(path)[1:-1]:
        if node not in snippet_sheet.children:
            child_snippet_sheet = SnippetSheet()
            child_snippet_sheet.children = dict()
            child_snippet_sheet.parent = snippet_sheet
            child_snippet_sheet.snippets = dict()
            snippet_sheet.children[node] = child_snippet_sheet
        snippet_sheet = snippet_sheet.children[node]
        assert snippet_sheet is not None
    return snippet_sheet


def _get_snippet_sheets(snippet_map: SnippetMap) -> SnippetSheet:
    root = SnippetSheet()
    root.children = dict()
    root.parent = None
    root.snippets = dict()

    for snippet in snippet_map.snippets:
        snippet_sheet = _ensure_snippet_sheet_exists(snippet.path, root)
        assert snippet.type_name not in snippet_sheet.snippets
        snippet_sheet.snippets[snippet.type_name] = snippet
    return root


# TODO: remove
# def _get_pin_lookup(
#     snippet_map: SnippetMap,
# ) -> Dict[SnippetPinName, Set[SnippetPinName]]:
#     """
#     The snippet lookup only includes pins that are connected to the root snippet.
#     """
#     pins_lookup: Dict[SnippetPinName, Set[SnippetPinName]] = dict()
#     for snippet in snippet_map.snippets:
#         for pin_name, root_pin_name in snippet.pins.items():
#             if root_pin_name is None:
#                 continue
#             if pin_name not in pins_lookup:
#                 pins_lookup[pin_name] = {root_pin_name}
#             else:
#                 pins_lookup[pin_name].add(root_pin_name)
#     return pins_lookup


def main() -> None:
    if len(sys.argv) != 3 and len(sys.argv) != 4:
        print(
            "Error: Provide two arguments: the input file path, the path to the template and optionally the path to the template directory environment.",
            file=sys.stderr,
        )
        sys.exit(1)
    snippet_map_path = Path(sys.argv[1])
    template_path = Path(sys.argv[2])
    template_env_path = (
        Path(sys.argv[3]) if len(sys.argv) == 4 else template_path.parent
    )
    if not template_path.is_relative_to(template_env_path):
        print(
            "Error: The template path is not a subpath of the template environment path.",
            file=sys.stderr,
        )
        sys.exit(1)
    template_name = str(template_path.relative_to(template_env_path))

    snippet_map = parse_one_to_many_snippet_map(snippet_map_path)
    root_snippet_sheet = _get_snippet_sheets(snippet_map)

    env = Environment(
        loader=FileSystemLoader(
            template_env_path,
            followlinks=True,
        ),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(template_name)
    print(
        template.render(
            snippet_map=snippet_map,
            root_snippet_sheet=root_snippet_sheet,
        )
    )


if __name__ == "__main__":
    main()
