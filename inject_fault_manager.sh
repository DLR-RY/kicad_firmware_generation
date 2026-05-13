#!/bin/bash
set -euo pipefail
IFS=" \t\n"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

mkdir -p reports

while true; do
    touch reports/central.csv
    run_idx=$(cat reports/central.csv | wc -l)

    echo deleting work_dir
    rm -rf work_dir
    echo copying work_dir
    cp -r source_dir work_dir

    echo changing a thing
    changed_thing="$(python3 -m inject_fault.inject_fault ${run_idx})"

    mkdir -v reports/${run_idx}

    while read -r cmd; do
        cmd_idx=$(ls -1 reports/${run_idx} | wc -l)
        pushd "work_dir"
        if bash -c "${cmd}" 2>&1 | tee "../reports/${run_idx}/${cmd_idx}.txt"; then
            popd
        else
            popd
            break
        fi
    done < cmds.txt

    echo "${run_idx},${changed_thing},$(ls -1 reports/${run_idx} | wc -l),$(cat cmds.txt | wc -l)" >> reports/central.csv
    tail -n 1 reports/central.csv
done
