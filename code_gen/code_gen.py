import sys
from pathlib import Path
from typing import Set

from jinja2 import Environment, FileSystemLoader

from common_types.parse_xml import parse_many_to_many_snippet_map
from common_types.snippet_types import (
    Snippet,
    compile_snippet_glob,
    does_match_pattern,
    get_parent_snippet_path,
    stringify_snippet_id,
)


def _change_case(in_str: str, first_upper: bool) -> str:
    out_str = ""
    next_upper = first_upper
    for c in in_str:
        if c == "/" or c == "_":
            next_upper = True
            continue
        if next_upper:
            out_str += c.upper()
        else:
            out_str += c.lower()
        next_upper = False
    return out_str


def _pascal_case(in_str: str) -> str:
    return _change_case(in_str, True)


def _camel_case(in_str: str) -> str:
    return _change_case(in_str, False)


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

    snippet_map = parse_many_to_many_snippet_map(snippet_map_path)

    # TODO: sort
    def glob_snippets(glob_str: str) -> Set[Snippet]:
        pattern = compile_snippet_glob(glob_str)
        return {
            snippet
            for snippet in snippet_map.snippets
            if does_match_pattern(pattern, snippet.get_id())
        }

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
            glob_snippets=glob_snippets,
            stringify_snippet_id=stringify_snippet_id,
            pascal_case=_pascal_case,
            camel_case=_camel_case,
            get_parent_snippet_path=get_parent_snippet_path,
        )
    )


if __name__ == "__main__":
    main()
