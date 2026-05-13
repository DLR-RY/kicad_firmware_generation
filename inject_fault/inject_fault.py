import skip
import sys
from random import choice
import shutil


def delete_wire(schem) -> str:
    wire = choice(schem.wire)
    changed_thing = f"delete_wire;{wire.start.value}-{wire.end.value}"
    wire.delete()
    return changed_thing


def swap_labels(schem) -> str:
    first_label = choice(schem.label)
    neighbours = schem.label.within_reach_of(first_label, 20)
    if len(neighbours) == 0:
        # don't do anything in this case
        return "none"
    second_label = choice(neighbours)

    # swap positions
    first_label_at = tuple(first_label.at)
    second_label_at = tuple(second_label.at)
    first_label.move(second_label_at)
    second_label.move(first_label_at)

    return f"swap_labels;{first_label.value}-{second_label.value}"

    # TODO: swap neighbouring labels and neighbouring No Connect Flag (swapping cables is difficult)
    # Watch that some swapping is actually okay and shouldn't lead to an error.
    # E.g., using a different GPIO is fine; using a different ADC / ADC channel is fine; as long as everything is connected


def change_file(file: str) -> str:
    in_file = f"work_dir/{file}"
    report_dir = f"reports/{sys.argv[1]}"
    report_file = f"{report_dir}/{file.replace("/", "_")}"

    schem = skip.Schematic(in_file)

    changed_thing = choice([delete_wire, swap_labels, swap_labels, swap_labels])(schem)

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
