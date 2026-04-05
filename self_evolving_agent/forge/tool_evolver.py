"""Tool Evolver — self-repair loop for failed tool generation.

When a generated tool fails testing, this module feeds the error back
to the LLM and asks it to fix the code. Up to MAX_FIX_ATTEMPTS rounds.
"""

from typing import List

from .. import config


def build_fix_prompt(
    original_code: str,
    error_messages: List[str],
    attempt: int,
) -> str:
    """Build a prompt asking LLM to fix the broken tool code."""
    errors_text = "\n".join(error_messages)
    return f"""\
The tool code you generated has errors. Please fix them.

## Current Code (Attempt {attempt}/{config.MAX_FIX_ATTEMPTS})
```python
{original_code}
```

## Errors
{errors_text}

## Instructions
1. Fix the issues described above
2. Return the COMPLETE corrected function (not just the changed parts)
3. Use the same output format:

```python
def function_name(...) -> ...:
    \"\"\"...\"\"\"
    ...
```

```json
{{schema unchanged or updated}}
```

```test
{{test cases as JSON, one per line}}
```
"""
