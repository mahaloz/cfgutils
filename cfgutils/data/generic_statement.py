from typing import List


class GenericStatement:
    def __init__(self, addr: int, operation: object, operands: List[object] = None):
        self.addr = addr
        self.op = operation
        self.operands = operands or []

    def __eq__(self, other):
        return isinstance(other, GenericStatement) and self.op == other.op and self.operands == self.operands

    def __hash__(self):
        _target = hash(self.addr) + hash(self.op)
        for operand in self.operands:
            _target += hash(operand)

        return _target

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"<Statement {hex(self.addr)}: {self.op}({self.operands})"

