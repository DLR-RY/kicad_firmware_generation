import skip
import sys
from random import choice
import shutil


def delete_wire(schem) -> str:
    wire = choice(schem.wire)
    changed_thing = f"delete_wire;{wire.start.value}-{wire.end.value}"
    wire.delete()
    return changed_thing


def change_file(file: str) -> str:
    in_file = f"work_dir/{file}"
    report_dir = f"reports/{sys.argv[1]}"
    report_file = f"{report_dir}/{file.replace("/", "_")}"

    schem = skip.Schematic(in_file)

    changed_thing = delete_wire(schem)

    schem.write(in_file)
    shutil.copyfile(in_file, report_file)

    return changed_thing


# TODO: swap neighbouring labels and neighbouring No Connect Flag (swapping cables is difficult)
# Watch that some swapping is actually okay and shouldn't lead to an error.
# E.g., using a different GPIO is fine; using a different ADC / ADC channel is fine; as long as everything is connected


def main():
    # ignore snippets (we're not doing unit tests, after all); mechanical components; unused connectors in firmware/schematics; sheets without any digital/analog data line
    with open("sch_files.txt", "r") as file:
        sch_files = [line.strip() for line in file.readlines()]
    changed_file = choice(sch_files)
    changed_thing = change_file(changed_file)

    print(f"{changed_file};{changed_thing}")

if __name__ == "__main__":
    main()
