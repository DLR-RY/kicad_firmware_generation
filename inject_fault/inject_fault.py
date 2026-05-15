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
    changed_thing = f"{wire.start.value}-{wire.end.value}"
    wire.delete()
    return changed_thing


def are_same_enough(stra: str, strb: str) -> bool:
    if len(stra) != len(strb):
        return False
    diff_idxs = [i for i, (a, b) in enumerate(zip(stra, strb)) if a != b]
    if len(diff_idxs) > 2:
        return False
    for diff_idx in diff_idxs:
        if not stra[diff_idx].isdigit():
            return False
        if not strb[diff_idx].isdigit():
            return False
    return True


def get_neighbours(first_node, second_group):
    try:
        neighbours = second_group.within_reach_of(first_node, NEIGHBOUR_DISTANCE)
    except:
        return []
    filtered_neighbours = []
    for second_node in neighbours:
        # Don't swap with itself
        if first_node.value == second_node.value:
            continue
        # Swapping labels like ADC8_CH2 and ADC7_CH1 don't actually create an error.
        if are_same_enough(str(first_node.value), str(second_node.value)):
            continue
        filtered_neighbours.append(second_node)

    return filtered_neighbours


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
    # We know that there must always be a first_node with at least one neighbour.
    while True:
        first_node = choice(first_group)
        neighbours = get_neighbours(first_node, second_group)
        if len(neighbours) == 0:
            # don't do anything in this case
            continue
        second_node = choice(neighbours)
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

    return sum([len(get_neighbours(first_node, second_group)) for first_node in first_group])


def count_all():
    if pathlib.Path.exists(pathlib.Path("reports/sch_files.json")):
        with open("reports/sch_files.json", "r") as f:
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

    with open("reports/sch_files.json", "w") as file:
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
