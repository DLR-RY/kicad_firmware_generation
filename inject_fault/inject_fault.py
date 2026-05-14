import skip
import pathlib
import json
import sys
from random import choice, choices
import shutil

NEIGHBOUR_DISTANCE = 20


def delete_wire(schem) -> str:
    if not hasattr(schem, "wire"):
        assert False
    if len(schem.wire) == 0:
        assert False
    wire = choice(schem.wire)
    changed_thing = f"delete_wire;{wire.start.value}-{wire.end.value}"
    wire.delete()
    return changed_thing


# Watch that some swapping is actually okay and shouldn't lead to an error.
# E.g., using a different GPIO is fine; using a different ADC / ADC channel is fine; as long as everything is connected
# Results could be greatly improved by adding simple checks to the Jinja2 template.
# Right now, e.g., the snippet template only looks for the MISO pin and just assumes that the other ones are correct.
def swap(schem, first_group_name, second_group_name) -> str:
    if not hasattr(schem, first_group_name):
        assert False
    if not hasattr(schem, second_group_name):
        assert False
    first_group = getattr(schem, first_group_name)
    second_group = getattr(schem, second_group_name)

    if len(first_group) == 0:
        assert False
    while True:
        first_node = choice(first_group)
        neighbours = second_group.within_reach_of(first_node, NEIGHBOUR_DISTANCE)
        if len(neighbours) == 0:
            # don't do anything in this case
            continue
        second_node = choice(neighbours)

        # Don't swap with itself
        if first_node.value == second_node.value:
            continue
        break

    # swap positions
    first_node_at = tuple(first_node.at)
    second_node_at = tuple(second_node.at)
    first_node.move(second_node_at)
    second_node.move(first_node_at)

    return f"{first_node.value}-{second_node.value}"


def count_matches(schem, first_group_name, second_group_name) -> int:
    if not hasattr(schem, first_group_name):
        return 0
    if not hasattr(schem, second_group_name):
        return 0
    first_group = getattr(schem, first_group_name)
    second_group = getattr(schem, second_group_name)

    def count_matches_for(first_node) -> int:
        try:
            return len(second_group.within_reach_of(first_node, NEIGHBOUR_DISTANCE))
        except:
            return 0
    return sum([count_matches_for(first_node) for first_node in first_group])


def count_all():
    if pathlib.Path.exists(pathlib.Path("sch_files.json")):
        with open("sch_files.json", "r") as f:
            return json.load(f)

    sch_files_json = {
            "files": [],
            "possible_faults": {
                "delete-wire": [],
                "swap-label-label": [],
                "swap-label-hierarchical_label": [],
                # there are no global labels in this schematic
                # "swap-label-global_label": [],
                "swap-label-no_connect": [],
                "swap-hierarchical_label-hierarchical_label": [],
                # "swap-hierarchical_label-global_label": [],
                "swap-hierarchical_label-no_connect": [],
                # "swap-global_label-global_label": [],
                # "swap-global_label-no_connect": [],
                # swap-no_connect-no_connect makes no sense
            },
        }

    # ignore snippets (we're not doing unit tests, after all); mechanical components; unused connectors in firmware/schematics; sheets without any digital/analog data line
    with open("sch_files.txt", "r") as in_file:
        sch_files = [line.strip() for line in in_file.readlines()]

    for file in sch_files:
        in_file = f"work_dir/{file}"
        schem = skip.Schematic(in_file)
        sch_files_json["files"].append(file)
        sch_files_json["possible_faults"]["delete-wire"].append(len(schem.wire) if hasattr(schem, "wire") else 0)
        for key in sch_files_json["possible_faults"].keys():
            keys = key.split("-")
            if keys[0] != "swap":
                continue
            sch_files_json["possible_faults"][key].append(count_matches(schem, keys[1], keys[2]))

    with open("sch_files.json", "w") as file:
        json.dump(sch_files_json, file, indent=4)
    return sch_files_json


def main():
    sch_files_json = count_all()
    fault_weights = [sum(possible_fault) for possible_fault in sch_files_json["possible_faults"].values()]
    chosen_fault, counts = choices(list(sch_files_json["possible_faults"].items()), weights=fault_weights, k=1)[0]
    changed_file = choices(sch_files_json["files"], weights=counts, k=1)[0]

    in_file = f"work_dir/{changed_file}"
    report_dir = f"reports/{sys.argv[1]}"
    report_file = f"{report_dir}/{changed_file.replace("/", "_")}"

    schem = skip.Schematic(in_file)

    chosen_faults = chosen_fault.split("-")
    if chosen_faults[0] == "swap":
        changed_thing = swap(schem, chosen_faults[1], chosen_faults[2])
    elif chosen_fault == "delete-wire":
        changed_thing = delete_wire(schem)
    else:
        assert False

    schem.write(in_file)
    shutil.copyfile(in_file, report_file)

    print(f"{changed_file};{chosen_fault};{changed_thing}")

if __name__ == "__main__":
    main()
