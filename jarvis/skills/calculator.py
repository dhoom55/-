"""Safe calculator: evaluates arithmetic only (no eval of arbitrary code)."""
import ast
import math
import operator
import re

NAME = "calculator"
PATTERNS = [
    r"^(احسب|حسب|كم يساوي|كم حاصل|calculate|compute|what is|whats)\s+[\d٠-٩\.\s\+\-\*/×÷\^\(\)%,]+$",
    r"^[\d٠-٩\.\s\+\-\*/×÷\^\(\)%,]*\d[\d٠-٩\.\s]*[\+\-\*/×÷\^%][\d٠-٩\.\s\+\-\*/×÷\^\(\)%,]*$",
    r"^(احسب|calculate)\s+(جذر|sqrt)",
]
TESTS = ["احسب 2 + 2", "calculate (3*4)/2", "10 % 3", "احسب جذر 16"]

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
       ast.FloorDiv: operator.floordiv, ast.USub: operator.neg, ast.UAdd: operator.pos}
FUNCS = {"sqrt": math.sqrt}
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError("exponent too large")
        return OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS:
        return FUNCS[node.func.id](*[_eval(a) for a in node.args])
    raise ValueError("unsupported expression")


def calculate(expr: str) -> float:
    expr = expr.translate(AR_DIGITS).replace("×", "*").replace("÷", "/").replace("^", "**").replace(",", "")
    expr = re.sub(r"(جذر|sqrt)\s*\(?\s*([\d\.]+)\s*\)?", r"sqrt(\2)", expr)
    return _eval(ast.parse(expr.strip(), mode="eval").body)


def handle(text, match, jarvis):
    expr = re.sub(r"^\s*(احسب|حسب|كم يساوي|كم حاصل|calculate|compute|what is|what's|whats)\s*", "", text.strip(),
                  flags=re.IGNORECASE).rstrip("؟?=")
    try:
        result = calculate(expr)
    except ZeroDivisionError:
        return jarvis.say("لا يمكن القسمة على صفر.", "Division by zero is undefined.", text)
    except (ValueError, SyntaxError):
        return jarvis.say("ما قدرت أفهم العملية الحسابية.", "I couldn't parse that calculation.", text)
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    elif isinstance(result, float):
        result = round(result, 10)
    return jarvis.say(f"النتيجة: {result}", f"The result is {result}.", text)
