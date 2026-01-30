import argparse
import sys
from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from common_types.group_types import (
    GroupWithConnection,
    compile_group_glob,
    connect_netlist,
    does_match_pattern,
    get_parent_group_path,
    stringify_group_id,
)
from common_types.parse_xml import parse_group_netlist

TOOL_NAME = "code_gen v0.1.0"
TOOL_NAME_WITH_VERSION = f"{TOOL_NAME} v0.1.0"


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


def generate_code(
    netlist_path: Path,
    template_path: Path,
    template_dir_env: Path | None,
    output_path: Path | None,
) -> None:
    """
    This function does the same and has the same parameters as the code_gen CLI interface.
    """
    template_env_path = (
        template_dir_env if template_dir_env is not None else template_path.parent
    )
    if not template_path.is_relative_to(template_env_path):
        print(
            "Error: The template path is not a subpath of the template environment path.",
            file=sys.stderr,
        )
        sys.exit(1)
    template_name = str(template_path.relative_to(template_env_path))

    netlist = connect_netlist(parse_group_netlist(netlist_path))

    def glob_groups(glob_str: str) -> List[GroupWithConnection]:
        pattern = compile_group_glob(glob_str)
        groups = [
            group
            for group in netlist.groups.values()
            if does_match_pattern(pattern, group.get_id())
        ]
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
    output = template.render(
        netlist=netlist,
        glob_groups=glob_groups,
        stringify_group_id=stringify_group_id,
        pascal_case=_pascal_case,
        camel_case=_camel_case,
        get_parent_group_path=get_parent_group_path,
    )
    if output_path is not None:
        print(f"Printing output to: {output_path}")
        with open(output_path, "w") as file:
            file.write(output)
    else:
        print(output)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Generate a file from a Jinja2 template based on the information from a Group Netlist. "
        "The output is printed to stdout, errors and warnings to stderr.",
    )
    parser.add_argument(
        "group_netlist_file",
        help="The path to a Group Netlist file.",
    )
    parser.add_argument(
        "template_file_path",
        help="The path to a Jinja2 template. "
        "This file may include other template files. "
        "You may specify the template directory environment these included template files are relative to. "
        "See the --template-dir-env argument. "
        "Alternatively, code_gen uses the parent directory of the template_file_path.",
    )
    parser.add_argument(
        "--template-dir-env",
        help="The path to the Jinja2 template directory environment.",
    )
    parser.add_argument(
        "--output",
        help="The output path. Print to stdout if not provided.",
    )
    args = parser.parse_args()

    generate_code(
        Path(args.group_netlist_file),
        Path(args.template_file_path),
        None if args.template_dir_env is None else Path(args.template_dir_env),
        None if args.output is None else Path(args.output),
    )


if __name__ == "__main__":
    main()
