"""Validation engine and rule registry.

Importing this package registers the built-in rule set, so `run_rules()` is
always meaningful — callers never need a side-effect import to enable rules.
"""

from __future__ import annotations

import idl2icd.validation.rules.builtin as builtin
from idl2icd.validation.engine import (
    SEVERITY_RANK,
    register_rule,
    run_rules,
    worst_severity,
)

__all__ = ["SEVERITY_RANK", "builtin", "register_rule", "run_rules", "worst_severity"]
