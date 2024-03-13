from typing import Optional

from ailment.block_walker import AILBlockWalkerBase
from ailment.block import Block
from ailment.statement import Call, ConditionalJump


class AILBlockCallCounter(AILBlockWalkerBase):
    """
    Helper class to count AIL calls and call-expressions in a block
    """

    calls = []

    def _handle_CallExpr(self, expr_idx: int, expr: "Call", stmt_idx: int, stmt, block: Optional["Block"]):
        self.calls.append(expr)
        super()._handle_CallExpr(expr_idx, expr, stmt_idx, stmt, block)

    def _handle_Call(self, stmt_idx: int, stmt: "Call", block: Optional["Block"]):
        self.calls.append(stmt)
        super()._handle_Call(stmt_idx, stmt, block)

