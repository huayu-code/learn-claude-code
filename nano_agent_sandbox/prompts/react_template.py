"""
react_template.py — ReAct 格式模板

用于在需要引导 LLM 按 Thought → Action → Observation 格式输出时使用。
（当前实现中 LLM 通过 function calling 直接结构化输出，此模板作为备用方案。）
"""

REACT_TEMPLATE = """Answer the user's request using the following format:

Thought: <your reasoning about what to do next>
Action: <tool name or "code">
Action Input: <tool arguments or code to execute>

After receiving the result:
Observation: <result from the action>

Repeat Thought/Action/Observation until the task is complete, then:
Final Answer: <your response to the user>
"""

ERROR_FIX_TEMPLATE = """The previous code execution failed with the following error:

Error Type: {error_type}
Error Message: {error_message}
{line_info}

Suggestion: {suggestion}

Please fix the code and try again. Focus on the specific error above.
Do NOT repeat the same mistake.
"""
