import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Set, Tuple

from common_types.group_types import (
    GlobalGroupPinIdentifier,
    MutableGroupNet,
    Group,
    GroupIdentifier,
    GroupNet,
    GroupNetlist,
    GroupPath,
    GroupPinName,
    GroupType,
    stringify_group_id,
)
from common_types.stringify_xml import stringify_group_netlist
from kicad_group_netlister.kicad_netlist_xml import parse_kicad_netlist
from kicad_group_netlister.kicad_types import (
    GlobalKiCadPinIdentifier,
    KiCadComponentRef,
    KiCadNetlist,
    KiCadNodePinName,
    KiCadSheetPath,
    RawGroup,
    RawGroupLookup,
    GroupPinNameLookups,
    GroupsReverseLookup,
)

GROUP_TYPE_FIELD_NAME = "GroupType"
GROUP_PIN_FIELD_PREFIX = "GroupPin"
GROUP_MAP_FIELD_PREFIX = "GroupMapField"
# TODO: set this properly
TOOL_NAME = "kicad_group_netlister v0.1.0"


def _group_components_by_group(
    netlist: KiCadNetlist,
) -> Tuple[RawGroupLookup, GroupsReverseLookup]:
    groups = RawGroupLookup(dict())
    reverse_lookup = GroupsReverseLookup(dict())
    for component in netlist.components.values():
        if GROUP_TYPE_FIELD_NAME not in component.fields:
            false_friend_fields = [
                field
                for field in component.fields.keys()
                if field.startswith(GROUP_PIN_FIELD_PREFIX)
                or field.startswith(GROUP_MAP_FIELD_PREFIX)
            ]
            if len(false_friend_fields) != 0:
                print(
                    f"Warning: The component {component.ref} defines the {'fields' if len(false_friend_fields) > 1 else 'field'} {', '.join(false_friend_fields)} but not the field {GROUP_TYPE_FIELD_NAME}.\n"
                    "Therefore, it is not part of a group.",
                    file=sys.stderr,
                )

            # This component is not part of any group.
            continue
        group_type = GroupType(component.fields[GROUP_TYPE_FIELD_NAME])
        group_path = GroupPath(component.sheetpath)
        group_identifier = GroupIdentifier((netlist.schematic, group_path, group_type))

        if group_identifier not in groups:
            groups[group_identifier] = RawGroup()
            groups[group_identifier].schematic = netlist.schematic
            groups[group_identifier].path = group_path
            groups[group_identifier].type_name = group_type
            groups[group_identifier].components = {component}
            groups[group_identifier].group_map_fields = dict()
        else:
            groups[group_identifier].components.add(component)

        for field_name, field_value in component.fields.items():
            if not field_name.startswith(GROUP_MAP_FIELD_PREFIX):
                # This is not a GroupMapField.
                continue
            group_map_field_name = field_name[len(GROUP_MAP_FIELD_PREFIX) :]
            if len(group_map_field_name) == 0:
                print(
                    f"Warning: The group {stringify_group_id(group_identifier)} contains a GroupMapField with the empty string as key.",
                    file=sys.stderr,
                )

            if group_map_field_name in groups[group_identifier].group_map_fields:
                print(
                    f"Error: The group {stringify_group_id(group_identifier)} contains the GroupMapField {group_map_field_name} twice.\n"
                    f"They have the values {field_value} and {groups[group_identifier].group_map_fields[group_map_field_name]}.\n"
                    f"One is in component {component.ref}.",
                    file=sys.stderr,
                )
                sys.exit(1)
            groups[group_identifier].group_map_fields[group_map_field_name] = (
                field_value
            )

        assert component.ref not in reverse_lookup
        reverse_lookup[component.ref] = group_identifier

    return (groups, reverse_lookup)


# Groups without a explicit naming don't appear in this dict.
def _get_explicit_pin_name_lookups(
    groups_lookup: RawGroupLookup,
) -> GroupPinNameLookups:
    explicit_pin_namings = GroupPinNameLookups(dict())
    for group_identifier, raw_group in groups_lookup.items():
        # Use this set to verify no GroupPin name is used twice for the same group.
        group_pin_names: Set[GroupPinName] = set()
        for component in raw_group.components:
            for field_name, field_value in component.fields.items():
                # Only consider field names that define explic GroupPin names.
                if not field_name.startswith(GROUP_PIN_FIELD_PREFIX):
                    continue

                # After the GroupPin prefix comes the pin shown in KiCad that belongs to the component.
                node_pin_name = KiCadNodePinName(
                    field_name[len(GROUP_PIN_FIELD_PREFIX) :]
                )
                global_pin_identifier = GlobalKiCadPinIdentifier((
                    component.ref,
                    node_pin_name,
                ))
                # We can't have the same globally unique reference for two pins.
                for other_expicit_in_naming_group in explicit_pin_namings.values():
                    assert global_pin_identifier not in other_expicit_in_naming_group

                # This is the name the user explicitly set for this pin.
                group_pin_name = GroupPinName(field_value)
                if group_pin_name in group_pin_names:
                    print(
                        f"Error: The GroupPin {group_pin_name} exists at least twice for the group {stringify_group_id(group_identifier)}.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                group_pin_names.add(group_pin_name)

                # update explicit_pin_namings
                if group_identifier in explicit_pin_namings:
                    explicit_pin_namings[group_identifier][global_pin_identifier] = (
                        group_pin_name
                    )
                else:
                    explicit_pin_namings[group_identifier] = {
                        global_pin_identifier: group_pin_name
                    }
    return explicit_pin_namings


# The KiCad netlist connects pins on components to other pins on other components.
# This function converts that netlist into a netlist that connects pins on groups to other pins on other groups.
# The names of the pins are the GroupPin names and not the KiCad pin names any longer.
def _gen_group_netlist(
    netlist: KiCadNetlist,
    raw_groups_lookup: RawGroupLookup,
    groups_reverse_lookup: GroupsReverseLookup,
) -> GroupNetlist:
    explicit_pin_name_lookups = _get_explicit_pin_name_lookups(raw_groups_lookup)

    # We only use this to check that no two components have the same global group pin identifier.
    global_group_pin_to_component: Dict[GlobalGroupPinIdentifier, KiCadComponentRef] = (
        dict()
    )

    group_netlist = GroupNetlist()
    group_netlist.source = netlist.source
    group_netlist.date = datetime.now()
    group_netlist.tool = TOOL_NAME

    # Create representations for all groups without their pins.
    # same as raw_groups_lookup but this time with the final Group class
    groups_lookup: Dict[GroupIdentifier, Group] = dict()
    for raw_group in raw_groups_lookup.values():
        group = Group()
        group.schematic = raw_group.schematic
        group.path = raw_group.path
        group.type_name = raw_group.type_name
        group.group_map_fields = raw_group.group_map_fields
        # We populate the pins when we loop over all nets.
        group.pins = dict()
        group_id = raw_group.get_id()
        assert group_id not in groups_lookup
        groups_lookup[group_id] = group

    group_netlist.nets = set()
    for net in netlist.nets:
        group_net = MutableGroupNet(set())
        for node in net:
            if node.ref not in groups_reverse_lookup:
                # The node does not belong to a component that belongs to a group.
                continue
            group_identifier = groups_reverse_lookup[node.ref]
            global_pin_identifier = GlobalKiCadPinIdentifier((node.ref, node.pin))

            # Figure out what name this pin has.
            group_pin_name: GroupPinName
            if group_identifier in explicit_pin_name_lookups:
                explicit_pin_name_lookup = explicit_pin_name_lookups[group_identifier]
                if global_pin_identifier not in explicit_pin_name_lookup:
                    # The pin does belong to components that belong to the group.
                    # Nevertheless, the user chose to explicitly define GroupPin names to some of the group's pins and this pin doesn't have one.
                    # Therefore, we don't consider this pin to belong to the group.
                    continue
                group_pin_name = explicit_pin_name_lookup[global_pin_identifier]
            else:
                # When the user didn't define any GroupPin names for at all we use a fallback:
                # We consider all pins that belong to components that belong to the group as pins of the group.
                group_pin_name = GroupPinName(node.pinfunction)

            # Assign None because we don't have any idea what the root group could be.
            groups_lookup[group_identifier].pins[group_pin_name] = None

            # This uniquely identifies the pin in the entire group map.
            global_group_pin_identifier = GlobalGroupPinIdentifier((
                group_identifier,
                group_pin_name,
            ))

            if (
                global_group_pin_identifier in global_group_pin_to_component
                and global_group_pin_to_component[global_group_pin_identifier]
                != node.ref
            ):
                print(
                    f"Error: The pin {group_pin_name} in the group {stringify_group_id(group_identifier)} occurs in multiple components: {global_group_pin_to_component[global_group_pin_identifier]} and {node.ref}.",
                    file=sys.stderr,
                )
                sys.exit(1)
            global_group_pin_to_component[global_group_pin_identifier] = node.ref

            # This might very well be the only pin in the group net.
            group_net.add(global_group_pin_identifier)
        group_netlist.nets.add(GroupNet(frozenset(group_net)))

    group_netlist.groups = groups_lookup

    for group in group_netlist.groups.values():
        if len(group.pins) == 0:
            print(
                f"Warning: The group {stringify_group_id(group.get_id())} has no pins.",
                file=sys.stderr,
            )

    return group_netlist


# There are a few stupid things one can do with a netlist.
# This function ensures the electrical engineer didn't do such things and exits otherwise.
def _check_kicad_netlist_structure(netlist: KiCadNetlist) -> None:
    sheet_paths: Set[KiCadSheetPath] = set()
    # The first element is required path and second is the requiring path.
    required_paths: Set[Tuple[KiCadSheetPath, KiCadSheetPath]] = set()

    for sheet in netlist.sheets:
        # The root sheet has path `/`.
        # Any other sheet has a path like `/asfd/`.
        assert len(sheet.path) >= 1
        assert sheet.path[0] == "/"
        assert sheet.path[-1] == "/"

        if sheet.path in sheet_paths:
            print(
                f"Error: two sheets have the same path {sheet.path}.",
                file=sys.stderr,
            )
            sys.exit(1)
        sheet_paths.add(sheet.path)

        nodes = sheet.path.split("/")
        assert len(nodes) > 1
        # Don't do this when we're already at the root.
        if len(nodes) > 2:
            required_paths.add((
                KiCadSheetPath("/".join(nodes[:-1]) + "/"),
                sheet.path,
            ))

    for required_path, requiring_path in required_paths:
        if required_path not in sheet_paths:
            # TODO: read the schematics file directly and figure this out perfectly.
            print(
                f"Warning: The the last node of sheet path {requiring_path} uses the character `/`. "
                "This is not allowed because then separating path nodes isn't possible. "
                f"The script knows this because it didn't find {required_path}. ",
                "You need to fix this as this should be an error! ",
                "Though, this is a warning because there are situations in which the script doesn't notice the user's stupidity. ",
                "You need to watch out for this yourself.",
                file=sys.stderr,
            )
            sys.exit(1)


def main() -> None:
    if len(sys.argv) != 2:
        print(
            "Error: Provide one argument: the input KiCad netlist file (in the kicadxml format) path.",
            file=sys.stderr,
        )
        sys.exit(1)
    kicad_netlist_path = Path(sys.argv[1])
    kicad_netlist = parse_kicad_netlist(kicad_netlist_path)
    _check_kicad_netlist_structure(kicad_netlist)

    groups_lookup, groups_reverse_lookup = _group_components_by_group(kicad_netlist)

    group_netlist = _gen_group_netlist(
        kicad_netlist, groups_lookup, groups_reverse_lookup
    )
    sys.stdout.buffer.write(stringify_group_netlist(group_netlist))


if __name__ == "__main__":
    main()
