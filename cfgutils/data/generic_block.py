from typing import List, Optional


class GenericBlock:
    def __init__(
        self, addr: int, statements: List = None, idx: Optional[int] = None, is_entrypoint: bool = False,
        is_exitpoint: bool = False, is_merged_node=False
    ):
        self.addr = addr
        self.statements = statements or []
        self.idx = idx
        self.is_entrypoint = is_entrypoint
        self.is_exitpoint = is_exitpoint
        self.is_merged_node = is_merged_node

        self._idx_str = "" if self.idx is None else f".{self.idx}"

    def __eq__(self, other):
        return type(other) is self.__class__ and self.addr == other.addr and self.statements == other.statements

    def __hash__(self):
        return hash(f"{self.addr}{self.idx}{[d for d in self.statements]}")

    def __repr__(self):
        type_str = " (exit)" if self.is_exitpoint else " (entry)" if self.is_entrypoint else ""
        return f"<Block: {self.addr}{self._idx_str}{type_str}>"

    def __str__(self):
        type_str = " (exit)" if self.is_exitpoint else " (entry)" if self.is_entrypoint else ""
        output = f"{self.addr}{self._idx_str}{type_str}:\n"
        for stmt in self.statements:
            str_stmt = str(stmt)
            if len(str_stmt) > 80:
                str_stmt = str_stmt[:80] + "..."
            output += f"{str_stmt}\n"
        return output

    def copy(self):
        return self.__class__(
            self.addr,
            statements=self.statements.copy() if self.statements is not None else None,
            idx=self.idx,
        )

    def contains_addr(self, addr):
        if self.addr == addr:
            return True

    @classmethod
    def merge_blocks(cls, block1: "GenericBlock", block2: "GenericBlock"):
        new_node = block1.copy()
        new_node.statements += block2.statements
        new_node.is_entrypoint |= block2.is_entrypoint
        new_node.is_exitpoint |= block2.is_exitpoint
        new_node.is_merged_node = True
        return new_node

    @classmethod
    def merge_many_blocks(cls, start_addr, nodes: List["GenericBlock"]):
        new_node = nodes[0].copy()
        new_node.addr = start_addr
        for node in nodes[1:]:
            new_node = cls.merge_blocks(new_node, node)

        return new_node
