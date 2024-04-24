from typing import Optional, Any

from ailment import BinaryOp, UnaryOp, Assignment
from ailment.block_walker import AILBlockWalkerBase
from ailment.block import Block
from ailment.statement import Call, ConditionalJump, Statement, Store
from ailment.expression import Const, StackBaseOffset, BasePointerOffset, Load

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

    def __init__(self, project=None, project_cfg=None, call_name_fallback=None):
        self._project = project
        self._project_cfg = project_cfg
        self._call_name_fallback_addrs = call_name_fallback or {}

        # features
        self.arith_ins = []
        self.calls = []
        self.ins = []
        self.logic_ins = []
        self.branch_ins = []
        self.str_consts = []
        self.num_consts = []
        self.stack_addrs = []
        self.var_names = []
        self.call_names = []

        super().__init__()
        self.expr_handlers[StackBaseOffset] = self._handle_StackBaseOffset

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
        func_name = self._resolve_call_name(expr)
        if func_name is not None:
            self.call_names.append(func_name)
        super()._handle_CallExpr(expr_idx, expr, stmt_idx, stmt, block)

    def _handle_Call(self, stmt_idx: int, stmt: "Call", block: Optional["Block"]):
        self.calls.append(stmt)
        func_name = self._resolve_call_name(stmt)
        if func_name is not None:
            self.call_names.append(func_name)
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

    def _handle_StackBaseOffset(self, expr_idx: int, expr: "StackBaseOffset", stmt_idx: int, stmt: Statement, block: Optional[Block]):
        self.stack_addrs.append(expr.offset)
        return None

    def _handle_Store(self, stmt_idx: int, stmt: Store, block: Optional[Block]):
        if stmt.variable is not None and stmt.variable.name is not None:
            self.var_names.append(stmt.variable.name)

        return super()._handle_Store(stmt_idx, stmt, block)

    def _handle_Load(self, expr_idx: int, expr: Load, stmt_idx: int, stmt: Statement, block: Optional[Block]):
        if hasattr(expr, "variable") and expr.variable is not None and expr.variable.name is not None:
            self.var_names.append(expr.variable.name)

        return super()._handle_Load(expr_idx, expr, stmt_idx, stmt, block)

    def _handle_Assignment(self, stmt_idx: int, stmt: Assignment, block: Optional[Block]):
        if hasattr(stmt.dst, "variable") and stmt.dst.variable is not None and stmt.dst.variable.name is not None:
            self.var_names.append(stmt.dst.variable.name)

        if hasattr(stmt.src, "variable") and stmt.src.variable is not None and stmt.src.variable.name is not None:
            self.var_names.append(stmt.src.variable.name)

        return super()._handle_Assignment(stmt_idx, stmt, block)

    #
    # utils
    #

    def _resolve_call_name(self, call_expr):
        func_name = None
        if isinstance(call_expr.target, Const):
            func_addr = call_expr.target.value
            if self._project is not None and func_addr in self._project.kb.functions and not self._project.kb.functions[func_addr].name.startswith("sub_"):
                func_name = self._project.kb.functions[func_addr].name
            elif func_addr in self._call_name_fallback_addrs:
                func_name = self._call_name_fallback_addrs[func_addr]
        if isinstance(call_expr.target, Load) and isinstance(call_expr.target.addr, StackBaseOffset):
            # convert to lookup format
            k = f"s_{hex(call_expr.target.addr.offset)}"
            func_name = self._call_name_fallback_addrs.get(k, None)

        return func_name
