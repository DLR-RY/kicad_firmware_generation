import skip
import sys
from random import choice, choices
import shutil


def delete_wire(schem) -> str:
    if len(schem.wire) == 0:
        return "none"
    wire = choice(schem.wire)
    changed_thing = f"delete_wire;{wire.start.value}-{wire.end.value}"
    wire.delete()
    return changed_thing


# Watch that some swapping is actually okay and shouldn't lead to an error.
# E.g., using a different GPIO is fine; using a different ADC / ADC channel is fine; as long as everything is connected
def swap_labels(schem) -> str:
    return f"swap_labels;{swap(schem.label, schem.label)}"


def swap_label_no_connect(schem) -> str:
    return f"swap_label_no_connect;{swap(schem.no_connect, schem.label)}"


def swap(first_group, second_group) -> str:
    if len(first_group) == 0:
        return "none"
    first_node = choice(first_group)
    neighbours = second_group.within_reach_of(first_node, 20)
    if len(neighbours) == 0:
        # don't do anything in this case
        return "none"
    second_node = choice(neighbours)

    # swap positions
    first_node_at = tuple(first_node.at)
    second_node_at = tuple(second_node.at)
    first_node.move(second_node_at)
    second_node.move(first_node_at)

    return f"{first_node.value}-{second_node.value}"

def change_file(file: str) -> str:
    in_file = f"work_dir/{file}"
    report_dir = f"reports/{sys.argv[1]}"
    report_file = f"{report_dir}/{file.replace("/", "_")}"

    schem = skip.Schematic(in_file)

    changed_thing = choices((delete_wire, swap_labels, swap_label_no_connect), weights=(20, 50, 30), k=1)[0](schem)

    schem.write(in_file)
    shutil.copyfile(in_file, report_file)

    return changed_thing


def main():
    # ignore snippets (we're not doing unit tests, after all); mechanical components; unused connectors in firmware/schematics; sheets without any digital/analog data line
    with open("sch_files.txt", "r") as file:
        sch_files = [line.strip() for line in file.readlines()]
    changed_file = choice(sch_files)
    changed_thing = change_file(changed_file)

    print(f"{changed_file};{changed_thing}")

if __name__ == "__main__":
    main()
