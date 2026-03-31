# nano_agent_sandbox 系统设计文档（面试视角）

> 本文档从"面试官最关心什么"的角度组织，聚焦于 **设计决策的 Why**、**工程权衡的 Trade-off**、以及 **对真实问题的解法**。

---

## 一、一句话介绍 & 项目定位

**nano_agent_sandbox** 是一个从零手写的、带安全沙箱和自愈能力的 Code Agent。它实现了类似 Claude Code / OpenAI Code Interpreter 的核心架构——LLM 驱动的 ReAct 循环 + 安全代码执行 + 错误自修复，整体仅依赖 `openai` + `python-dotenv` 两个外部包。

**面试官关心的定位问题**：为什么手写而不用 LangChain/CrewAI？
- 答：目的是**深入理解 Agent 运行时的每一个环节**，而非套框架。每一层（LLM 调用、工具路由、沙箱隔离、自愈策略）都有自己的设计选择和工程权衡，这是框架封装后看不到的。

---

## 二、整体架构（必问题：画一下你的系统架构）

```
┌─────────────────────────────────────────────────────────────┐
│                   main.py — Composition Root                 │
│            （依赖注入 / 组件组装 / CLI 交互循环）                │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Agent Loop（ReAct 主循环）                          │
│    Observe → Think → Act → Reflect → 循环/终止               │
│    ┌──────────────────────────────────────────────┐         │
│    │ ContextManager（上下文窗口管理 + 自动压缩）     │         │
│    └──────────────────────────────────────────────┘         │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: LLM Client（流式调用 + Action 解析）                │
│    流式文本输出 / tool_calls 增量拼接 / CodeAct 降级           │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Tool System（注册 + 路由 + 执行）                   │
│    Registry(Dispatch Map) → 5 个内置工具                      │
│    run_code | read_file | write_file | bash | todo           │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: Sandbox（安全隔离层）                               │
│    CodeExecutor(Facade) → SubprocessSandbox                  │
│    FileManager（路径沙箱化 + 产物收集）                        │
├─────────────────────────────────────────────────────────────┤
│  Layer 5: Self-Heal（自愈机制）                               │
│    ErrorAnalyzer（6大类错误分类） + RetryStrategy（防死循环）    │
└─────────────────────────────────────────────────────────────┘
```

**面试官追问：为什么分 5 层？**
- 每层职责单一、可独立测试、可独立替换。比如 Sandbox 层可以从 subprocess 换成 Docker，不影响上层。Self-Heal 层可以换成更复杂的策略，不影响 Agent Loop。

---

## 三、核心设计决策 & 面试高频问题

### 3.1 ReAct 循环：Agent 如何"思考-行动-反思"？

```
用户输入 → [Observe] 追加上下文
         → [Think]   流式调 LLM，返回 Action
         → [Act]     路由工具执行 or CodeAct 降级执行
         → [Reflect] 检查结果，错误则触发自愈
         → 循环，直到 Action.is_final=True 或达到 25 轮上限
```

**关键代码路径**（`core/agent_loop.py`）：
- `run()` 是主循环入口，每轮调用 `_think_stream()` → `_act()` → `_reflect()`
- `_think_stream()` 流式调 LLM，实时打印文本，返回结构化 `Action`
- `_act()` 有**双路径**：标准 function calling 优先，CodeAct 降级兜底
- `_reflect()` 检测错误后注入 `<self_heal>` 结构化提示

**面试官关心**：为什么要有 25 轮上限？
- **资源保护**：防止 LLM 陷入无限循环消耗 token/API 调用
- **用户体验**：长时间无结果不如提前终止告知用户
- 到达上限时注入终止提示（而非直接 kill），让 LLM 有机会做总结性回复

### 3.2 CodeAct 降级机制：如何应对 LLM 行为的不确定性？

**问题**：LLM 不总是乖乖用 function calling，有时会直接在文本里写 ```python 代码块。

**解法**（`core/llm_client.py` 的 `parse_action()`）：
1. 优先检查 `message.tool_calls`（标准路径）
2. 如果没有 tool_calls，用正则 `r"```python\n(.*?)```"` 从文本中提取代码块
3. 提取到的代码块填入 `Action.code_blocks`，`_act()` 中自动执行

**面试官关心**：这个降级有什么风险？
- 正则可能误匹配（比如 LLM 在解释代码而非要求执行）
- **权衡**：宁可多执行一次（结果可 observe），不可漏执行（用户以为 Agent 不干活）
- 生产系统可加确认步骤或置信度判断

### 3.3 上下文窗口管理：长对话如何不爆 token？

**问题**：多轮工具调用后，上下文迅速膨胀（一次 code 执行结果可能几千字符）。

**解法**（`core/context_manager.py`）：
1. **触发条件**：`_estimate_tokens()` > 60000 字符
2. **保留策略**：保留最近 6 条消息（保证 LLM 能看到最近的执行结果）
3. **压缩方式**：
   - **有 LLM 可用**：调 LLM 生成 3-5 条摘要替代旧消息
   - **无 LLM / 降级**：提取每条消息前 200 字符拼接
4. 旧消息替换为一条 `<context_summary>` 消息

**面试官追问**：为什么保留 6 条而不是 3 条或 10 条？
- 6 条覆盖了「用户问题 + 最近 2-3 轮工具调用与结果」，是 ReAct 循环的最小完整上下文
- 太少会丢失关键执行结果导致 LLM 重复操作，太多则压缩效果差

**面试官追问**：`_estimate_tokens()` 用字符数而非真实 token 计数，准确吗？
- 不完全准确，但**足够好**。真实 tokenizer 调用有开销，字符数作为启发式在中英文混合场景下误差约 20-30%，但上限设为 60000 字符（远低于模型真实窗口），留足安全余量。

### 3.4 沙箱安全：如何防止恶意代码？

这是面试重点。安全沙箱有 **4 层防护**：

| 层级 | 机制 | 防御目标 |
|------|------|----------|
| **路径沙箱化** | `FileManager.safe_path()` 使用 `resolve()` + `is_relative_to()` | 防止 `../../etc/passwd` 路径穿越 |
| **环境变量隔离** | `_build_safe_env()` 只传递 PATH/HOME/TMPDIR/LANG，清空 PYTHONPATH | 防止 API Key 等敏感信息泄露 |
| **超时保护** | `subprocess.run(timeout=30)` + `TimeoutExpired` 捕获 | 防止死循环/恶意占用 CPU |
| **输出截断** | `_truncate()` 限制 50000 字符 | 防止内存爆炸（如 `print("x"*10**9)`） |

**Bash 工具的额外防护**（`tools/builtin/bash_tool.py`）：
- **危险命令黑名单**：`rm -rf /`、`sudo`、`shutdown`、`reboot`、`mkfs`、`dd if=`、`:(){`（Fork Bomb）
- 命中即拒绝，不执行

**面试官追问**：subprocess 沙箱的局限性是什么？
- **没有 namespace 隔离**：子进程仍共享主机网络、PID 空间
- **内存限制未强制执行**：`config.SANDBOX_MAX_MEMORY_MB` 声明但未用 `resource.setrlimit()` 实现
- **生产级方案**：应使用 Docker/gVisor/nsjail，项目中 `CodeExecutor` 的 Facade 模式预留了替换入口

**面试官追问**：`safe_path()` 的实现能防所有路径攻击吗？
```python
def safe_path(self, path_str: str) -> Path:
    target = (self.workdir / path_str).resolve()
    if not target.is_relative_to(self.workdir):
        raise PermissionError(f"Access denied: {path_str}")
    return target
```
- `resolve()` 消除 `..` 和符号链接 → 防路径穿越和 symlink 攻击
- `is_relative_to()` 确保最终路径在沙箱目录内
- **已知局限**：TOCTOU（检查和使用之间的竞争条件），但在单线程 Agent 场景下不是问题

### 3.5 自愈机制：Agent 出错后如何自动修复？

**三步闭环**：

```
错误发生 → ErrorAnalyzer.classify_error() → 分类 + 修复建议
         → RetryStrategy.should_retry()   → 判断是否可重试
         → 注入 <self_heal> 上下文         → 引导 LLM 下一轮修复
```

**错误分类体系（6 大类）**：
| 类别 | 示例 | 严重性 | 修复建议 |
|------|------|--------|----------|
| syntax | SyntaxError, IndentationError | high | 检查语法、缩进 |
| import | ModuleNotFoundError | medium | `pip install` 或换标准库 |
| runtime | TypeError, ValueError, KeyError 等 | medium | 检查类型/变量 |
| io | FileNotFoundError, PermissionError | medium | 检查路径/权限 |
| resource | MemoryError, RecursionError | high | **不可重试** |
| timeout | TimeoutError | high | **不可重试** |

**防死循环的三重保护**（`retry_strategy.py`）：
1. **全局次数上限**：总重试 ≥ 3 次 → 放弃
2. **同类错误限制**：相同错误指纹（`error_name:message[:100]`）连续出现 ≥ 2 次 → 放弃（LLM 没学到教训）
3. **不可恢复错误**：resource/timeout 类 → 立即放弃（重试无意义）

**面试官关心**：自愈提示是怎么注入的？
```python
# agent_loop.py → _reflect()
hint = f"""<self_heal>
错误类型: {error_info['type']}
错误信息: {error_info['message']}
修复建议: {suggestion}
剩余重试: {remaining}
</self_heal>"""
self.context.inject_observation(hint)
```
- 用结构化 XML 标签，让 LLM 能清晰区分「系统错误反馈」和「用户对话」
- `inject_observation()` 以 user 角色注入，确保 LLM 下一轮能看到

---

## 四、组件交互 & 依赖注入（面试考点：如何组装？）

### 4.1 Composition Root 模式（`main.py:build_agent()`）

```python
def build_agent():
    # Step 1: 创建沙箱基础设施
    sandbox = SubprocessSandbox(workdir, timeout)
    executor = CodeExecutor(sandbox)
    file_mgr = FileManager(workdir)

    # Step 2: 依赖注入到工具模块（模块级单例）
    run_code_tool.init(executor)
    read_file_tool.init(file_mgr)
    write_file_tool.init(file_mgr)

    # Step 3: 工具注册
    registry = ToolRegistry()
    registry.register("run_code", run_code_tool.run_code, RUN_CODE_SCHEMA)
    # ... 注册其他 4 个工具

    # Step 4: LLM + 上下文
    llm = LLMClient(api_key, base_url, model)
    context = ContextManager(system_prompt)

    # Step 5: 自愈
    analyzer = ErrorAnalyzer()
    retry = RetryStrategy(max_retries=3)

    # Step 6: 组装
    return AgentLoop(llm, context, registry, analyzer, retry), file_mgr
```

**面试官关心**：为什么用模块级单例而不是类成员？
- **简洁性**：工具函数签名要匹配 OpenAI function calling 的 `handler(arguments)` 模式
- **权衡**：牺牲了可测试性（全局状态），但保持了工具注册的统一接口
- 生产系统可用闭包或依赖注入容器替代

### 4.2 工具系统的 Dispatch Map 模式

```python
class ToolRegistry:
    def __init__(self):
        self._tools = {}     # name → handler
        self._schemas = {}   # name → OpenAI schema

    def dispatch(self, name, arguments):
        handler = self._tools.get(name)
        if not handler:
            return f"Unknown tool: {name}. Available: {self.tool_names}"
        return handler(arguments)  # O(1) 查找 + 直接调用
```

**面试官追问**：为什么不用 if-elif 或 match-case？
- **O(1) vs O(n)**：字典查找 vs 线性匹配
- **开放封闭原则**：新增工具只需 `register()`，不改路由代码
- **运行时动态性**：可以热插拔工具

---

## 五、流式处理：一个容易被忽视的工程难点

### 5.1 问题：OpenAI 流式 API 中 tool_calls 如何拼接？

流式响应中，tool_calls 不是一次性返回的，而是**分块到达**：
- 第一个 chunk 携带 `index=0, id="call_xxx", name="run_code"`
- 后续 chunk 携带 `index=0, arguments='{"co'`、`arguments='de": "pri'`、...

### 5.2 解法（`core/llm_client.py`）

```python
tc_map = {}  # index → {id, name, arguments_str}
for chunk in stream:
    for tc in chunk.choices[0].delta.tool_calls or []:
        idx = tc.index
        if idx not in tc_map:
            tc_map[idx] = {"id": "", "name": "", "args": ""}
        if tc.id:
            tc_map[idx]["id"] = tc.id
        if tc.function.name:
            tc_map[idx]["name"] = tc.function.name
        if tc.function.arguments:
            tc_map[idx]["args"] += tc.function.arguments  # 累积拼接
```

**面试官关心**：arguments 的 JSON 解析失败怎么办？
- 降级为 `{"raw": arguments_str}`，不崩溃，让 Agent 循环继续

---

## 六、设计模式总结（面试背诵版）

| 模式 | 位置 | 解决什么问题 |
|------|------|-------------|
| **ReAct Loop** | agent_loop.py | Agent 自主决策循环 |
| **Facade** | executor.py | 隐藏沙箱实现，预留替换入口 |
| **Dispatch Map** | registry.py | O(1) 工具路由，开放封闭 |
| **依赖注入** | main.py build_agent() | 组件解耦，可测试 |
| **Strategy** | retry_strategy.py | 可替换的重试策略 |
| **DataClass** | Action, ToolCall, ExecutionResult | 类型安全的数据传递 |
| **Module Singleton** | 各 builtin 工具 | 简化工具函数签名 |
| **Composition Root** | main.py | 集中管理依赖图 |

---

## 七、测试策略（面试考点：你怎么保证质量？）

项目包含 **20 个单元测试**，覆盖三大核心模块：

### 7.1 沙箱安全测试（7 项）
- 基本执行、数学计算正确性
- 语法错误 / 导入错误的捕获
- **超时保护测试**：临时改 3s 超时，执行 `time.sleep(10)` 验证
- **环境变量隔离**：主进程设 `SECRET_KEY`，断言沙箱内 `os.environ.get()` 返回 None
- 多行输出完整性

### 7.2 自愈机制测试（7 项）
- 各类错误的正确分类
- 修复建议内容验证
- 重试次数限制生效
- resource 错误立即拒绝
- reset 后状态重置

### 7.3 Agent 核心测试（6 项）
- 上下文消息追加/获取
- observation 注入格式
- 工具注册 + dispatch
- 未知工具优雅降级
- Todo 管理 + 单任务聚焦约束

---

## 八、已知局限 & 改进方向（面试加分项：自我反思）

| 局限 | 现状 | 改进方向 |
|------|------|----------|
| 沙箱隔离不足 | subprocess，无 namespace | Docker / gVisor / nsjail |
| 内存限制未实现 | config 中声明，未 enforce | `resource.setrlimit()` 或 cgroup |
| bash 工具安全性低 | 黑名单 + 在主目录执行 | 也放进沙箱 / 白名单模式 |
| token 估算不精确 | 字符数启发式 | 接入 tiktoken 精确计数 |
| 无并发工具执行 | 串行 dispatch | 支持 parallel tool calls |
| 无持久化记忆 | 每次会话重置 | 向量数据库 / 文件系统记忆 |
| CodeAct 降级有误匹配风险 | 正则提取所有 python 块 | 置信度判断 / 用户确认 |

---

## 九、核心数据流（面试白板题）

```
用户: "用 Python 画一个正弦曲线并保存为 PNG"
  │
  ├─[Observe] context.append_user(query)
  │
  ├─[Think] llm.chat_stream(messages, tools)
  │   ├── 实时打印: "我来帮你画正弦曲线..."
  │   └── Action: tool_calls=[ToolCall("run_code", {code: "import matplotlib..."})]
  │
  ├─[Act] registry.dispatch("run_code", {code: ...})
  │   ├── run_code.py → executor.execute(code)
  │   ├── SubprocessSandbox:
  │   │   ├── 写临时 .py 文件
  │   │   ├── subprocess.run(timeout=30, env=safe_env)
  │   │   ├── 捕获 stdout/stderr
  │   │   └── 清理临时文件
  │   └── context.append_tool_result(result)
  │
  ├─[Reflect] _is_error(result)?
  │   ├── No → 继续循环
  │   └── Yes → classify_error() → should_retry()?
  │       ├── Yes → 注入 <self_heal> 提示 → 继续循环
  │       └── No  → 让 LLM 自行决定下一步
  │
  ├─[Think] LLM 看到成功结果 → 生成最终回复（is_final=True）
  │
  └── 返回文本 + file_mgr.collect_artifacts() 展示 sine_curve.png
```

---

## 十、面试常见追问 & 参考回答

**Q: 如果 LLM 返回了错误的 JSON 参数怎么办？**
A: `llm_client.py` 中 JSON 解析失败会降级为 `{"raw": ...}`，工具层再做参数校验，不会崩溃。

**Q: 如何防止 Agent 陷入无限循环？**
A: 三重保护——25 轮硬上限 + 自愈重试 3 次上限 + 同类错误连续 2 次检测。

**Q: 上下文压缩会丢失关键信息吗？**
A: 保留最近 6 条消息确保当前任务上下文完整。用 LLM 摘要旧对话的关键要点，比简单丢弃好。但确实存在信息损失，这是 token 限制下的必要权衡。

**Q: 为什么不用 LangChain？**
A: 项目目标是理解 Agent 运行时的每个环节。手写代码量约 1500 行，每个组件的设计决策都是可解释的。框架封装后这些权衡就不可见了。

**Q: 这个项目的技术亮点是什么？**
A: 三个亮点——(1) CodeAct 降级机制优雅处理 LLM 行为不确定性；(2) 自愈闭环（分类→建议→注入→引导修复）；(3) 五层架构每层可独立替换测试。
