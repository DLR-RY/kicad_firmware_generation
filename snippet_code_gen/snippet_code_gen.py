import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


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

    env = Environment(loader=FileSystemLoader(template_env_path, followlinks=True))
    template = env.get_template(template_name)
    print(template.render(test="Hello World!"))


if __name__ == "__main__":
    main()
