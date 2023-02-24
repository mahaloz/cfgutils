from typing import List


class GenericBlock:
    def __init__(self, addr, data=None):
        self.addr = addr
        self.data = data

    def __eq__(self, other):
        return type(other) == type(self) and self.addr == other.addr and \
            self.data == other.data

    def __hash__(self):
        return hash(f"{self.addr}{self.data}")

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.addr}>"

    def __str__(self):
        return f"{self.addr}:\n{self.data}"

    def copy(self):
        return GenericBlock(
            self.addr,
            data=self.data.copy() if self.data else None
        )

    @staticmethod
    def merge_blocks(block1: "GenericBlock", block2: "GenericBlock"):
        new_node = block1
        new_node.data += block2.data

    @staticmethod
    def merge_many_blocks(start_addr, nodes: List["GenericBlock"]):
        new_node = nodes[0].copy()
        new_node.addr = start_addr
        for node in nodes[1:]:
            new_node.data += node.data

        return new_node
