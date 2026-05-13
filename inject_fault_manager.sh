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

    mkdir -v reports/${run_idx}

    echo changing a thing
    changed_thing="$(python3 -m inject_fault.inject_fault ${run_idx})"
    echo ${changed_thing}

    successfully_completed=0
    while read -r cmd; do
        pushd "work_dir"
        if bash -c "${cmd}" 2>&1 | tee "../reports/${run_idx}/${successfully_completed}.txt"; then
            popd
        else
            popd
            break
        fi
        successfully_completed=$((successfully_completed + 1))
    done < cmds.txt

    echo "${run_idx};${changed_thing};${successfully_completed};$(cat cmds.txt | wc -l)" >> reports/central.csv
    tail -n 1 reports/central.csv
done
