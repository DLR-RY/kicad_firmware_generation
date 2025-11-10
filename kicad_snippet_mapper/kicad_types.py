from pathlib import Path
from typing import Dict, NewType, Set, Tuple

ComponentRef = NewType("ComponentRef", str)
SheetPath = NewType("SheetPath", str)
NodePinName = NewType("NodePinName", str)
# globally unique descriptor for a pin
GlobalPinIdentifier = NewType("GlobalPinIdentifier", Tuple[ComponentRef, NodePinName])
NodePinFunction = NewType("NodePinFunction", str)


class Sheet:
    path: SheetPath


class Component:
    ref: ComponentRef
    sheetpath: SheetPath
    fields: Dict[str, str]

    def __repr__(self) -> str:
        return f"Component(ref={self.ref!r}, sheetpath={self.sheetpath!r}, fields={list(self.fields.keys())!r})"


# a pin on a component that is connected to some net(s)
class Node:
    ref: ComponentRef
    pin: NodePinName
    pinfunction: NodePinFunction

    def __repr__(self) -> str:
        return f"Node(ref={self.ref!r}, pin={self.pin!r}, pinfunction={self.pinfunction!r})"


class Net:
    nodes: Set[Node]

    def __repr__(self) -> str:
        return f"Net(nodes={len(self.nodes)} nodes)"


class Netlist:
    source: Path
    sheets: Set[Sheet]
    # Map component's ref to component.
    components: Dict[ComponentRef, Component]
    nets: Set[Net]

    def __repr__(self) -> str:
        return (
            f"Netlist(source={self.source!r}, "
            f"components={len(self.components)} components, "
            f"nets={len(self.nets)} nets)"
        )
