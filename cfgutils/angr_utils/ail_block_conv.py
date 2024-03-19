from collections import defaultdict
from typing import Optional

from ailment import BinaryOp, UnaryOp, Assignment
from ailment.block_walker import AILBlockWalkerBase
from ailment.block import Block
from ailment.statement import Call, ConditionalJump, Statement, Store, Return
from ailment.expression import Const, Load, ITE, Convert

from cfgutils.angr_utils.prettyify_ail import string_at_addr
from cfgutils.data.generic_statement import GenericStatement


class AILBlockConverter(AILBlockWalkerBase):
    def __init__(self, project=None, project_cfg=None):
        self.stmt_by_idx = defaultdict(list)
        self._project = project
        self._project_cfg = project_cfg
        super().__init__()

    @property
    def statements(self):
        ordered = []
        for idx, stmts in self.stmt_by_idx.items():
            ordered.append(reversed(stmts))

        return ordered

    def _fix_string_and_imms(self, const):
        if not isinstance(const, Const):
            return str(const)

        str_val = None
        if self._project is not None and self._project_cfg is not None:
            str_val = string_at_addr(self._project_cfg, const.value, self._project, max_size=200)

        return str_val if str_val is not None else const.value

    def _fix_list(self, _list):
        if not _list:
            return []

        out = []
        for _l in _list:
            out.append(self._fix_string_and_imms(_l))

        return out

    #
    # Statements
    #

    def _handle_Call(self, stmt_idx: int, stmt: "Call", block: Optional["Block"]):
        self.stmt_by_idx[stmt_idx].append(
            GenericStatement(stmt.tags['ins_addr'], "call", self._fix_list(stmt.args))
        )
        return super()._handle_Call(stmt_idx, stmt, block)

    def _handle_Return(self, stmt_idx: int, stmt: Return, block: Optional[Block]):
        self.stmt_by_idx[stmt_idx].append(
            GenericStatement(stmt.tags['ins_addr'], "ret", self._fix_list(stmt.ret_exprs))
        )
        return super()._handle_Return(stmt_idx, stmt, block)

    def _handle_Store(self, stmt_idx: int, stmt: Store, block: Optional[Block]):
        self.stmt_by_idx[stmt_idx].append(
            GenericStatement(stmt.tags['ins_addr'], "store", [
                self._fix_string_and_imms(stmt.addr), self._fix_string_and_imms(stmt.data)
            ])
        )
        return super()._handle_Store(stmt_idx, stmt, block)

    def _handle_Assignment(self, stmt_idx: int, stmt: Assignment, block: Optional[Block]):
        self.stmt_by_idx[stmt_idx].append(
            GenericStatement(stmt.tags['ins_addr'], "assign", [
                self._fix_string_and_imms(stmt.dst), self._fix_string_and_imms(stmt.src)
            ])
        )
        return super()._handle_Assignment(stmt_idx, stmt, block)

    def _handle_ConditionalJump(self, stmt_idx: int, stmt: ConditionalJump, block: Optional[Block]):
        self.stmt_by_idx[stmt_idx].append(
            GenericStatement(stmt.tags['ins_addr'], "cond_jmp", [
                self._fix_string_and_imms(stmt.condition), self._fix_string_and_imms(stmt.true_target),
                self._fix_string_and_imms(stmt.false_target)
            ])
        )
        return super()._handle_ConditionalJump(stmt_idx, stmt, block)

    #
    # Expr
    #

    def _handle_Load(self, expr_idx: int, expr: Load, stmt_idx: int, stmt: Statement, block: Optional[Block]):
        self.stmt_by_idx[stmt_idx].append(
            GenericStatement(stmt.tags['ins_addr'], "load", [
                self._fix_string_and_imms(expr.addr), self._fix_string_and_imms(expr.size)
            ])
        )
        return super()._handle_Load(expr_idx, expr, stmt_idx, stmt, block)

    def _handle_ITE(self, expr_idx: int, expr: ITE, stmt_idx: int, stmt: Statement, block: Optional[Block]):
        self.stmt_by_idx[stmt_idx].append(
            GenericStatement(stmt.tags['ins_addr'], "ITE", [
                self._fix_string_and_imms(expr.cond), self._fix_string_and_imms(expr.iftrue),
                self._fix_string_and_imms(expr.iffalse)
            ])
        )
        return super()._handle_ITE(expr_idx, expr, stmt_idx, stmt, block)

    def _handle_BinaryOp(self, expr_idx: int, expr: BinaryOp, stmt_idx: int, stmt: Statement, block: Optional[Block]):
        self.stmt_by_idx[stmt_idx].append(
            GenericStatement(stmt.tags['ins_addr'], expr.op, self._fix_list(expr.operands))
        )
        return super()._handle_BinaryOp(expr_idx, expr, stmt_idx, stmt, block)

    def _handle_UnaryOp(self, expr_idx: int, expr: UnaryOp, stmt_idx: int, stmt: Statement, block: Optional[Block]):
        self.stmt_by_idx[stmt_idx].append(
            GenericStatement(stmt.tags['ins_addr'], expr.op, self._fix_string_and_imms(expr.operand))
        )
        return super()._handle_UnaryOp(expr_idx, expr, stmt_idx, stmt, block)

    def _handle_CallExpr(self, expr_idx: int, expr: "Call", stmt_idx: int, stmt, block: Optional["Block"]):
        self.stmt_by_idx[stmt_idx].append(
            GenericStatement(stmt.tags['ins_addr'], "call", self._fix_list(expr.args))
        )
        return super()._handle_CallExpr(expr_idx, expr, stmt_idx, stmt, block)

