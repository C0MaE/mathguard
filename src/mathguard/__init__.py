"""mathguard — verify mathematical claims made by people or language models.

>>> import mathguard as mg
>>> mg.check_equal("(a+b)^2", "a^2 + 2a b + b^2").status.value
'verified'
"""

__version__ = "0.4.0"

from .answer import AnswerReport, Grade, check_answer, grade, load_task
from .api import LLM_INSTRUCTIONS, verify, verify_json
from .checks import (
    check_antiderivative,
    check_chain,
    check_definite_integral,
    check_derivative,
    check_equal,
    check_limit,
    check_solutions,
    check_value,
)
from .document import DocumentReport, check_document
from .latex import latex_to_expr, parse_latex
from .parsing import ParseError, parse
from .units import check_dimensions, dimension_of
from .verdict import Report, Status, Verdict

__all__ = [
    "AnswerReport",
    "DocumentReport",
    "Grade",
    "LLM_INSTRUCTIONS",
    "ParseError",
    "Report",
    "Status",
    "Verdict",
    "check_answer",
    "check_antiderivative",
    "check_chain",
    "check_definite_integral",
    "check_derivative",
    "check_dimensions",
    "check_document",
    "check_equal",
    "check_limit",
    "check_solutions",
    "check_value",
    "dimension_of",
    "grade",
    "latex_to_expr",
    "load_task",
    "parse",
    "parse_latex",
    "verify",
    "verify_json",
]
