from typing import Optional, Any

from ailment import BinaryOp, UnaryOp
from ailment.block_walker import AILBlockWalkerBase
from ailment.block import Block
from ailment.statement import Call, ConditionalJump, Statement
from ailment.expression import Const

from .prettyify_ail import string_at_addr


class AILBlockFeatureExtractor(AILBlockWalkerBase):
    """
    Extracts features from AIL blocks based on discoveRE features
    """
    LOGIC_INS_TYPS = {
        "LogicalAnd", "LogicalOr", "CmpF", "CmpEQ", "CmpNE", "CmpLT", "CmpLE", "CmpGT", "CmpGE", "CmpLTs",
        "CmpLEs", "CmpGTs", "CmpGEs"
    }
    ARITH_INS_TYPS = {
        "Add", "AddF", "Sub", "SubF", "Mul", "MulF", "Div", "DivF", "DivMo", "Mod", "Xor", "And",
        "Or", "Shl", "Shr", "Sar", "Ror", "Rol", "Not"
    }

    def __init__(self, project=None, project_cfg=None):
        self._project = project
        self._project_cfg = project_cfg

        # features
        self.arith_ins = []
        self.calls = []
        self.ins = []
        self.logic_ins = []
        self.branch_ins = []
        self.str_consts = []
        self.num_consts = []

        super().__init__()

    def _handle_stmt(self, stmt_idx: int, stmt: Statement, block: Optional[Block]) -> Any:
        self.ins.append(stmt)
        return super()._handle_stmt(stmt_idx, stmt, block)

    def _handle_BinaryOp(self, expr_idx: int, expr: BinaryOp, stmt_idx: int, stmt: Statement, block: Optional[Block]):
        if expr.op in self.ARITH_INS_TYPS:
            self.arith_ins.append(expr)
        elif expr.op in self.LOGIC_INS_TYPS:
            self.logic_ins.append(expr)
        return super()._handle_BinaryOp(expr_idx, expr, stmt_idx, stmt, block)

    def _handle_UnaryOp(self, expr_idx: int, expr: UnaryOp, stmt_idx: int, stmt: Statement, block: Optional[Block]):
        if expr.op in self.ARITH_INS_TYPS:
            self.logic_ins.append(expr)
        return super()._handle_UnaryOp(expr_idx, expr, stmt_idx, stmt, block)

    def _handle_ConditionalJump(self, stmt_idx: int, stmt: ConditionalJump, block: Optional[Block]):
        self.branch_ins.append(stmt)
        return super()._handle_ConditionalJump(stmt_idx, stmt, block)

    def _handle_CallExpr(self, expr_idx: int, expr: "Call", stmt_idx: int, stmt, block: Optional["Block"]):
        self.calls.append(expr)
        super()._handle_CallExpr(expr_idx, expr, stmt_idx, stmt, block)

    def _handle_Call(self, stmt_idx: int, stmt: "Call", block: Optional["Block"]):
        self.calls.append(stmt)
        super()._handle_Call(stmt_idx, stmt, block)

    def _handle_Const(self, expr_idx: int, expr: "Const", stmt_idx: int, stmt: Statement, block: Optional[Block]):
        if self._project is not None and self._project_cfg is not None:
            str_val = string_at_addr(self._project_cfg, expr.value, self._project, max_size=200)
            if str_val is not None:
                self.str_consts.append(str_val)
            else:
                self.num_consts.append(expr.value)
        else:
            self.num_consts.append(expr.value)

        return super()._handle_Const(expr_idx, expr, stmt_idx, stmt, block)

