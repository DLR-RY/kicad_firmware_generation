import argparse
import sys
from pathlib import Path
from typing import FrozenSet, Set

from common_types.group_types import (
    GroupGlob,
    GroupIdentifier,
    GroupNet,
    GroupNetlist,
    compile_group_glob,
    does_match_pattern,
    stringify_group_id,
)
from common_types.parse_xml import parse_group_netlist
from common_types.stringify_xml import stringify_group_netlist

TOOL_NAME = "group_netlist_merger v0.1.0"


def _merge_group_netlists(netlists: Set[GroupNetlist]) -> GroupNetlist:
    netlists_list = list(netlists)
    assert len(netlists_list) > 0
    netlist = netlists_list[0]
    for new_netlist in netlists_list[1:]:
        for source in netlist.sources:
            assert source not in new_netlist.sources
        netlist.sources |= new_netlist.sources
        for group_id in netlist.groups.keys():
            assert group_id not in new_netlist.groups
        netlist.groups |= new_netlist.groups
        print(netlist.nets, file=sys.stderr)
        print(new_netlist.nets, file=sys.stderr)
        assert len(netlist.nets & new_netlist.nets) == 0
        netlist.nets |= new_netlist.nets
    return netlist


def _connect_netlist(
    netlist: GroupNetlist, connect_group_globs: Set[GroupGlob]
) -> GroupNetlist:
    # For each group glob figure out what groups it matches.
    to_connect_group_sets: Set[FrozenSet[GroupIdentifier]] = set()
    for connect_group_glob in connect_group_globs:
        to_connect_group_set: Set[GroupIdentifier] = set()
        for group_id in netlist.groups:
            if not does_match_pattern(connect_group_glob, group_id):
                continue
            # Ensure we only connect groups that can be connected.
            if len(to_connect_group_set) != 0:
                group = netlist.groups[group_id]
                other_group = netlist.groups[list(to_connect_group_set)[0]]
                if set(other_group.pins.keys()) != set(group.pins.keys()):
                    print(
                        f"Error: The connect group glob pattern {connect_group_glob} matches both {stringify_group_id(group.get_id())} and {stringify_group_id(other_group.get_id())} but they don't have the same pins.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
            to_connect_group_set.add(group_id)

        print(f"Merging groups: {to_connect_group_set}", file=sys.stderr)
        if len(to_connect_group_set) < 2:
            print(
                f"Warning: The connect group glob pattern {connect_group_glob} matches fewer than two groups: {to_connect_group_set}.",
                file=sys.stderr,
            )
        to_connect_group_sets.add(frozenset(to_connect_group_set))

    # This relation should be transitive but isn't.
    # We implement the transitive nature further down.
    # This could be implemented a lot faster but this is a lot simpler and easier to manually verify.
    def should_nets_be_merged(net_a: GroupNet, net_b: GroupNet) -> bool:
        if net_a == net_b:
            return True
        # We need a group_set that connects the two nets.
        # Loop through all to find one.
        for group_set in to_connect_group_sets:
            # We need a node in the net_a that should be connected to a node in net_b.
            for node_a in net_a:
                if node_a[0] not in group_set:
                    # The node is not of a group that should be connected.
                    continue
                for node_b in net_b:
                    if node_b[1] != node_a[1]:
                        # The pins of node_a and node_b aren't the same -> don't connect.
                        continue
                    if node_b[0] not in group_set:
                        # The node is not of a group that should be connected.
                        continue
                    return True
        return False

    out_nets: Set[GroupNet] = set()
    # We go through all nets and check if any other nets should be merged with it.
    # This works great with the non-transitive predicate from above.
    # An alternative would be a breadth-first search but that is more complicated.
    for net in netlist.nets:
        unioned = False
        # Should this net be unioned instead of appended?
        for out_net in out_nets:
            assert should_nets_be_merged(net, out_net) == should_nets_be_merged(
                out_net, net
            )
            if should_nets_be_merged(net, out_net):
                if "AO_CURRENT_NONE" in {node[1] for node in net}:
                    print(f"FOUND: {net}", file=sys.stderr)
                print(f"Merging nets: {net} {out_net}", file=sys.stderr)
                # Update the old net with the new nodes.
                out_nets.remove(out_net)
                out_nets.add(GroupNet(out_net | net))
                unioned = True
                break
        if not unioned:
            out_nets.add(net)

    netlist.nets = out_nets
    return netlist


def main() -> None:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Merge multiple Group Netlists from different schematics into a single one. "
        "The output is printed to stdout, errors and warnings to stderr.",
    )
    parser.add_argument(
        "group_netlist_file",
        help="The path to a Group Netlist files. You may provide multiple.",
        nargs="+",
    )
    parser.add_argument(
        "--connect-group-glob",
        help="All groups that match this glob are merged into a single one. "
        "All groups that match must have exactly the same pins. "
        "All matching groups are connected together. "
        "This reflects the use of a physical connector, connecting multiple schematics together. "
        "You may provide multiple.",
        action="append",
    )
    args = parser.parse_args()
    netlist_paths = {Path(path) for path in args.group_netlist_file}

    netlists: Set[GroupNetlist] = set()
    for netlist_path in netlist_paths:
        netlists.add(parse_group_netlist(netlist_path))

    merged_group_netlist = _merge_group_netlists(
        netlists,
    )
    connected_merged_group_netlist = _connect_netlist(
        merged_group_netlist,
        set()
        if args.connect_group_glob is None
        else {compile_group_glob(group_glob) for group_glob in args.connect_group_glob},
    )
    sys.stdout.buffer.write(stringify_group_netlist(connected_merged_group_netlist))


if __name__ == "__main__":
    main()
