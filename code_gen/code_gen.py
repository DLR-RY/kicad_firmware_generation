import sys
from pathlib import Path
from typing import List, Set

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from common_types.parse_xml import parse_many_to_many_group_map
from common_types.group_types import (
    Group,
    compile_group_glob,
    does_match_pattern,
    get_parent_group_path,
    stringify_group_id,
)


def _change_case(in_str: str, first_upper: bool) -> str:
    out_str = ""
    next_upper = first_upper
    for c in in_str.lower():
        if c not in "abcdefghijklmnopqrstuvwxyz0123456789":
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
    group_map_path = Path(sys.argv[1])
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

    group_map = parse_many_to_many_group_map(group_map_path)

    def glob_groups(glob_str: str) -> List[Group]:
        pattern = compile_group_glob(glob_str)
        groups = list({
            group
            for group in group_map.groups
            if does_match_pattern(pattern, group.get_id())
        })
        groups.sort(key=lambda g: g.get_id())
        return groups

    env = Environment(
        loader=FileSystemLoader(
            template_env_path,
            followlinks=True,
        ),
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
    )
    template = env.get_template(template_name)
    print(
        template.render(
            group_map=group_map,
            glob_groups=glob_groups,
            stringify_group_id=stringify_group_id,
            pascal_case=_pascal_case,
            camel_case=_camel_case,
            get_parent_group_path=get_parent_group_path,
        )
    )


if __name__ == "__main__":
    main()
