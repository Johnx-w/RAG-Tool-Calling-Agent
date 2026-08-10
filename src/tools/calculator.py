"""Safe arithmetic calculator (no arbitrary eval)."""

from __future__ import annotations

import ast
import operator
from typing import Any

_BIN_OPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS: dict[type, Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BIN_OPS:
            raise ValueError(f"不支持的运算符: {op_type.__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        return float(_BIN_OPS[op_type](left, right))
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise ValueError(f"不支持的一元运算: {op_type.__name__}")
        return float(_UNARY_OPS[op_type](_eval_node(node.operand)))
    if isinstance(node, ast.Call):
        raise ValueError("不允许函数调用")
    if isinstance(node, ast.Name):
        raise ValueError("不允许变量名")
    raise ValueError(f"不支持的表达式节点: {type(node).__name__}")


def calculate(expression: str) -> str:
    """Evaluate a basic arithmetic expression and return a string result."""
    expr = (expression or "").strip()
    if not expr:
        raise ValueError("表达式为空")
    # normalize common unicode operators
    expr = (
        expr.replace("×", "*")
        .replace("÷", "/")
        .replace("（", "(")
        .replace("）", ")")
    )
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"表达式语法错误: {e}") from e
    value = _eval_node(tree)
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return str(value)
