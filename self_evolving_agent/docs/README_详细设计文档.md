# 🧬 Self-Evolving Agent 详细设计文档

> 一个能够自动创建、测试、注册新工具的自进化 AI Agent

---

## 目录

1. [项目概述](#1-项目概述)
2. [核心创新点](#2-核心创新点)
3. [系统架构](#3-系统架构)
4. [模块详解](#4-模块详解)
5. [核心流程](#5-核心流程)
6. [安全设计](#6-安全设计)
7. [设计决策与权衡](#7-设计决策与权衡)
8. [与业界方案对比](#8-与业界方案对比)
9. [可扩展性](#9-可扩展性)
10. [使用示例](#10-使用示例)

---

## 1. 项目概述

### 1.1 背景与动机

传统的 AI Agent 依赖预定义的工具集，存在以下局限：

| 问题 | 传统方案 | 本项目方案 |
|------|----------|------------|
| 工具不足 | 开发者手动添加 | Agent 自动创建 |
| 上下文限制 | 每次重复编写代码 | 复用已注册工具 |
| 灵活性 | 固定工具集 | 动态扩展 |
| 知识积累 | 无状态 | 持久化工具库 |

### 1.2 核心理念

```
"授人以鱼不如授人以渔" → "授 Agent 以工具不如授 Agent 以造工具的能力"
```

本项目受两篇重要论文启发：
- **LATM (Large Language Models as Tool Makers)**：LLM 既是工具使用者也是工具制造者
- **Voyager**：Minecraft AI Agent 通过技能库实现持续学习

### 1.3 技术栈

- **语言**: Python 3.10+
- **LLM**: OpenAI API（兼容 DeepSeek/本地模型）
- **测试**: pytest
- **安全**: AST 静态分析 + 进程隔离沙箱

---

## 2. 核心创新点

### 2.1 工具自进化能力

```
用户需求 → Agent 分析 → 发现工具缺失 → 自动生成代码 → 安全校验 → 沙箱测试 → 注册为新工具
```

这是本项目最核心的创新：**Agent 不仅能使用工具，还能创造工具**。

### 2.2 三层安全防护

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: AST 静态分析                               │
│  - 在代码执行前检测危险模式                          │
│  - 阻止 os/subprocess/eval/exec 等危险操作          │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│  Layer 2: 进程级沙箱隔离                             │
│  - subprocess 执行，独立进程空间                     │
│  - 清洗环境变量，防止 API Key 泄露                   │
│  - 工作目录限制在 /tmp/self-evolving-sandbox/       │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│  Layer 3: 测试驱动验证                               │
│  - 工具必须通过所有测试用例才能注册                  │
│  - 异常输入的边界测试                                │
└─────────────────────────────────────────────────────┘
```

### 2.3 自修复机制

当生成的代码有问题时，Agent 会：
1. 收集错误信息
2. 构建修复提示
3. 让 LLM 修正代码
4. 最多尝试 3 轮

这模拟了人类程序员 "写代码 → 测试 → 发现 bug → 修复" 的迭代过程。

### 2.4 热加载工具注册

```python
# 新工具注册后立即可用，无需重启
registry.register(tool_record)  # 注册
agent.run("用刚创建的工具做 xxx")  # 立即使用
```

---

## 3. 系统架构

### 3.1 整体架构图

```
                           ┌───────────────────────────────────────┐
                           │           Self-Evolving Agent         │
                           └───────────────────────────────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
                    ▼                         ▼                         ▼
        ┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
        │    Agent Loop     │     │   Tool Registry   │     │   Tool Forge      │
        │   (ReAct 循环)    │     │   (工具注册表)    │     │   (工具锻造)      │
        └───────────────────┘     └───────────────────┘     └───────────────────┘
                │                         │                         │
        ┌───────┴───────┐         ┌───────┴───────┐         ┌───────┴───────┐
        │               │         │               │         │               │
        ▼               ▼         ▼               ▼         ▼               ▼
   ┌─────────┐   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
   │   LLM   │   │ Context │  │ Builtin │  │  Tool   │  │  Code   │  │ Sandbox │
   │ Client  │   │ Manager │  │  Tools  │  │  Store  │  │Validator│  │ Tester  │
   └─────────┘   └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘
                                                │               │           │
                                                │               │           │
                                         ┌──────┴───────────────┴───────────┴──────┐
                                         │              Sandbox Executor           │
                                         │        (进程隔离 Python 执行器)         │
                                         └─────────────────────────────────────────┘
```

### 3.2 目录结构

```
self_evolving_agent/
├── main.py                     # CLI 入口 + Composition Root
├── config.py                   # 全局配置 (API Key、超时、黑名单等)
│
├── core/                       # 核心模块
│   ├── agent_loop.py           # ReAct 循环 + 工具锻造决策
│   ├── llm_client.py           # LLM 客户端 (流式响应 + Tool Calling 解析)
│   └── context.py              # 上下文管理 (消息历史 + 压缩)
│
├── forge/                      # 工具锻造系统
│   ├── tool_maker.py           # 解析 LLM 生成的代码/Schema/测试
│   ├── code_validator.py       # AST 安全校验入口
│   ├── sandbox_tester.py       # 在沙箱中运行测试
│   └── tool_evolver.py         # 失败自修复提示构建
│
├── sandbox/                    # 沙箱执行
│   ├── executor.py             # 进程隔离执行器
│   └── security.py             # AST 黑名单检测
│
├── registry/                   # 工具注册
│   ├── tool_registry.py        # 热加载 + 调度
│   ├── tool_store.py           # JSON 持久化
│   └── builtin_tools.py        # 5 个内置工具
│
├── prompts/
│   └── system_prompt.py        # 系统提示词
│
└── tests/                      # 31 个测试用例
```

### 3.3 数据流图

```
┌──────────┐    user_input     ┌─────────────┐
│   User   │ ─────────────────▶│  AgentLoop  │
└──────────┘                   └──────┬──────┘
                                      │
                         ┌────────────┴────────────┐
                         │                         │
                   existing tool?            need new tool?
                         │                         │
                         ▼                         ▼
                ┌────────────────┐       ┌────────────────┐
                │ ToolRegistry   │       │   ToolForge    │
                │   dispatch()   │       │  _forge_tool() │
                └───────┬────────┘       └───────┬────────┘
                        │                        │
                        │               ┌────────┴────────┐
                        │               │                 │
                        │               ▼                 ▼
                        │      ┌──────────────┐  ┌──────────────┐
                        │      │ Validator    │  │ SandboxTest  │
                        │      │ AST Check    │  │ Execute+Test │
                        │      └──────┬───────┘  └──────┬───────┘
                        │             │ pass             │ pass
                        │             └────────┬─────────┘
                        │                      ▼
                        │             ┌──────────────┐
                        │             │   Register   │
                        │             │  + Persist   │
                        │             └──────┬───────┘
                        │                    │
                        └────────────────────┘
                                      │
                                      ▼
                              ┌──────────────┐
                              │    Result    │
                              └──────────────┘
```

---

## 4. 模块详解

### 4.1 Agent Loop (`core/agent_loop.py`)

这是整个系统的大脑，实现了 ReAct 循环 + 工具锻造决策。

#### 核心算法

```python
def run(self, user_input: str) -> str:
    for turn in range(MAX_TURNS):
        # 1. Think: 调用 LLM 思考
        action = self.llm.chat(messages, tools=all_tools)
        
        # 2. 检查是否结束
        if action.is_final:
            return action.text
        
        # 3. Act: 处理工具调用
        for tool_call in action.tool_calls:
            if tool_call.name == "create_tool":
                # 进入工具锻造流程
                result = self._forge_tool(description)
            else:
                # 调用已有工具
                result = self.registry.dispatch(tool_call.name, args)
        
        # 4. Observe: 上下文压缩
        if self.context.check_compress():
            self.context.compress()
```

#### Meta-Tool 设计

Agent Loop 暴露两个"元工具"给 LLM：

| 工具名 | 用途 |
|--------|------|
| `create_tool` | 告诉 Agent 需要创建什么样的工具 |
| `list_all_tools` | 列出所有可用工具 |

这些元工具不在 Registry 中，而是由 Agent Loop 直接处理。

### 4.2 Tool Forge (`forge/`)

工具锻造系统是本项目的核心创新模块。

#### 4.2.1 Tool Maker (`tool_maker.py`)

负责解析 LLM 生成的工具代码。期望格式：

```markdown
```python
def tool_name(param: str) -> str:
    """Description"""
    return result
```

```json
{"name": "tool_name", "description": "...", "parameters": {...}}
```

```test
{"param": "test_value_1"}
{"param": "test_value_2"}
```
```

解析逻辑：
1. 用正则提取 Python 代码块
2. 用正则提取 JSON Schema
3. 用正则提取测试用例
4. 如果没有 Schema，自动从 AST 推断

#### 4.2.2 Code Validator (`security.py`)

基于 AST 的静态安全分析：

```python
class _SecurityVisitor(ast.NodeVisitor):
    def visit_Import(self, node):
        # 检查是否导入了危险模块
        if module in BLOCKED_MODULES:
            self.violations.append(f"Blocked import: {module}")
    
    def visit_Call(self, node):
        # 检查是否调用了危险函数
        if func_name in BLOCKED_BUILTINS:
            self.violations.append(f"Blocked builtin: {func_name}()")
```

黑名单配置：

```python
BLOCKED_MODULES = {"os", "subprocess", "shutil", "sys", "socket", ...}
BLOCKED_BUILTINS = {"eval", "exec", "__import__", "compile", "open"}
```

#### 4.2.3 Sandbox Tester (`sandbox_tester.py`)

在沙箱中执行测试用例：

```python
def run_tool_tests(record: ToolRecord) -> Tuple[bool, List[str]]:
    messages = []
    for test_case in record.test_cases:
        result = execute_function(
            func_code=record.code,
            func_name=record.name,
            args=test_case,
        )
        if result.success:
            messages.append(f"✅ Test passed: {test_case}")
        else:
            messages.append(f"❌ Test failed: {result.stderr}")
            return False, messages
    return True, messages
```

#### 4.2.4 Tool Evolver (`tool_evolver.py`)

当工具生成失败时，构建修复提示：

```python
def build_fix_prompt(code, errors, attempt) -> str:
    return f"""
The tool code you generated has errors. Please fix them.

## Current Code (Attempt {attempt}/3)
{code}

## Errors
{errors}

## Instructions
Fix the issues and return the COMPLETE corrected function.
"""
```

### 4.3 Sandbox (`sandbox/`)

#### 4.3.1 Executor (`executor.py`)

进程隔离执行器的核心设计：

```python
def execute_code(code: str, timeout: int = 30) -> ExecutionResult:
    # 1. 确保沙箱目录存在
    sandbox_dir = ensure_sandbox_dir()
    
    # 2. 写入临时文件
    code_file = sandbox_dir / "_exec_code.py"
    code_file.write_text(wrapped_code)
    
    # 3. subprocess 执行
    proc = subprocess.run(
        [sys.executable, str(code_file)],
        capture_output=True,
        timeout=timeout,
        cwd=str(sandbox_dir),
        env=_safe_env(),  # 清洗后的环境变量
    )
    
    # 4. 返回结果
    return ExecutionResult(
        success=proc.returncode == 0,
        stdout=proc.stdout[:MAX_OUTPUT],
        stderr=proc.stderr[:MAX_OUTPUT],
    )
```

环境变量清洗策略：

```python
def _safe_env() -> dict:
    """只保留必要的环境变量，防止 API Key 泄露"""
    env = {}
    for key in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL"):
        if val := os.environ.get(key):
            env[key] = val
    env["PYTHONPATH"] = ""  # 防止导入项目代码
    return env
```

### 4.4 Registry (`registry/`)

#### 4.4.1 Tool Registry (`tool_registry.py`)

热加载工具注册表：

```python
class ToolRegistry:
    def __init__(self, store: ToolStore):
        self._handlers: Dict[str, Callable] = dict(BUILTIN_HANDLERS)
        self._schemas: Dict[str, dict] = {...}
        self._agent_tools: Dict[str, ToolRecord] = {}
        self._load_persisted()  # 启动时加载持久化工具
    
    def register(self, record: ToolRecord, persist: bool = True):
        """注册新工具，立即生效"""
        # 创建在沙箱中执行的 handler
        def handler(args, _code=record.code, _name=record.name):
            result = execute_function(_code, _name, args)
            return result.return_value or result.stdout
        
        self._handlers[record.name] = handler
        self._schemas[record.name] = record.schema
        if persist:
            self.store.save(record)
    
    def dispatch(self, tool_name: str, args: dict) -> str:
        """调用工具"""
        handler = self._handlers.get(tool_name)
        return handler(args) if handler else f"Unknown tool: {tool_name}"
```

#### 4.4.2 Tool Store (`tool_store.py`)

JSON 文件持久化：

```python
class ToolStore:
    def __init__(self, base_dir: Path = TOOL_STORE_DIR):
        self.base_dir = base_dir
    
    def save(self, record: ToolRecord):
        path = self.base_dir / f"{record.name}.json"
        path.write_text(json.dumps(asdict(record), indent=2))
    
    def load_all(self) -> List[ToolRecord]:
        return [
            ToolRecord(**json.loads(p.read_text()))
            for p in self.base_dir.glob("*.json")
        ]
```

### 4.5 Built-in Tools (`builtin_tools.py`)

5 个内置工具：

| 工具 | 功能 |
|------|------|
| `run_python` | 在沙箱执行 Python 代码 |
| `read_file` | 读取沙箱内文件 |
| `write_file` | 写入沙箱内文件 |
| `list_files` | 列出沙箱目录 |
| `install_package` | pip 安装包 |

---

## 5. 核心流程

### 5.1 工具创建完整流程

```
[用户请求] "帮我分析这个 CSV 文件"
      │
      ▼
[Agent 思考] "没有 CSV 分析工具，需要创建一个"
      │
      ▼
[调用 create_tool] description="分析 CSV 文件..."
      │
      ▼
[Tool Forge 启动]
      │
      ├─► [LLM 生成代码]
      │         │
      │         ▼
      │   ```python
      │   def analyze_csv(path: str, column: str) -> str:
      │       import pandas as pd
      │       df = pd.read_csv(path)
      │       return df[column].describe().to_string()
      │   ```
      │
      ├─► [AST 安全检查]
      │         │ ✅ 没有危险调用
      │         ▼
      ├─► [沙箱测试]
      │         │ ✅ 测试通过
      │         ▼
      ├─► [注册工具]
      │         │ 写入 tool_store/analyze_csv.json
      │         ▼
      └─► [返回结果] "✅ 新工具 'analyze_csv' 已创建"
      │
      ▼
[Agent 继续] "现在我来使用这个工具..."
      │
      ▼
[调用 analyze_csv] {"path": "data.csv", "column": "sales"}
      │
      ▼
[沙箱执行]
      │
      ▼
[返回结果]
```

### 5.2 自修复流程

```
[第 1 轮] LLM 生成代码
      │
      ├─► [安全检查] ❌ 使用了 os.system
      │
      ▼
[构建修复提示] "代码使用了被禁止的 os.system..."
      │
      ▼
[第 2 轮] LLM 修复代码
      │
      ├─► [安全检查] ✅ 通过
      ├─► [沙箱测试] ❌ 测试失败: KeyError
      │
      ▼
[构建修复提示] "测试失败: KeyError..."
      │
      ▼
[第 3 轮] LLM 再次修复
      │
      ├─► [安全检查] ✅ 通过
      ├─► [沙箱测试] ✅ 通过
      │
      ▼
[注册成功]
```

---

## 6. 安全设计

### 6.1 威胁模型

| 威胁 | 攻击路径 | 防护措施 |
|------|----------|----------|
| 任意命令执行 | `os.system("rm -rf /")` | AST 拦截 `os` 模块 |
| 敏感信息泄露 | `print(os.environ)` | 环境变量清洗 |
| 文件系统破坏 | 写入系统文件 | 沙箱目录限制 |
| 资源耗尽 | 死循环/大内存 | timeout + 输出截断 |
| 代码注入 | `eval(user_input)` | AST 拦截 `eval/exec` |

### 6.2 AST 安全检查详解

```python
# 完整黑名单
BLOCKED_MODULES = {
    "os", "subprocess", "shutil", "sys", "socket",
    "multiprocessing", "threading", "ctypes", "pickle",
    "builtins", "importlib", "code", "codeop",
}

BLOCKED_BUILTINS = {
    "eval", "exec", "__import__", "compile",
    "open",  # 特殊处理：只允许沙箱内路径
}
```

AST 访问器检查点：
1. `visit_Import` — 检查 `import xxx`
2. `visit_ImportFrom` — 检查 `from xxx import yyy`
3. `visit_Call` — 检查 `eval()`, `exec()` 等调用
4. `visit_Attribute` — 检查 `os.system` 等属性访问

### 6.3 沙箱隔离机制

```
┌─────────────────────────────────────────────────────────────┐
│  主进程 (Agent)                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  环境变量: OPENAI_API_KEY=sk-xxx, PATH=..., ...     │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                    subprocess.run()
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  子进程 (沙箱)                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  环境变量: PATH=..., HOME=..., LANG=...             │    │
│  │  (无 API Key，无敏感信息)                            │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  工作目录: /tmp/self-evolving-sandbox/              │    │
│  │  (只能在此目录读写文件)                              │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. 设计决策与权衡

### 7.1 为什么用 subprocess 而不是 exec()？

| 方案 | 优点 | 缺点 |
|------|------|------|
| `exec()` | 快，无进程开销 | 无隔离，可污染主进程 |
| `subprocess` | 进程隔离，环境可控 | 启动开销 ~100ms |
| Docker | 最强隔离 | 部署复杂，开销大 |
| WebAssembly | 轻量沙箱 | Python 支持有限 |

**选择 subprocess 的理由**：
- 平衡了安全性和性能
- 无需额外依赖
- 面试 Demo 易于运行

### 7.2 为什么用 JSON 持久化而不是数据库？

**选择理由**：
- 面试 Demo 需要零依赖
- 工具数量通常 < 100，无性能瓶颈
- JSON 文件可直接查看/编辑

**生产环境建议**：
- 使用 SQLite（单机）或 PostgreSQL（分布式）
- 添加版本管理和回滚机制

### 7.3 为什么 AST 分析在沙箱执行之前？

```
错误顺序: 先执行，再检查（太晚了！）
正确顺序: 先检查，再执行（防患于未然）
```

AST 是静态分析，可以在代码运行前发现危险模式。

### 7.4 测试用例为什么由 LLM 生成？

**传统方案**：开发者手写测试
**本项目方案**：LLM 生成测试 + 人工补充

优点：
- LLM 了解工具的预期行为
- 可以生成边界测试
- 减少人工工作量

风险与对策：
- LLM 可能生成无效测试 → 增加格式校验
- 测试覆盖不全 → 允许人工补充

---

## 8. 与业界方案对比

### 8.1 对比表

| 特性 | Self-Evolving Agent | LangChain | AutoGPT | Claude Tool Use |
|------|---------------------|-----------|---------|-----------------|
| 工具动态创建 | ✅ | ❌ | ❌ | ❌ |
| 工具持久化 | ✅ | ❌ | ❌ | ❌ |
| 沙箱执行 | ✅ | 部分 | 部分 | ❌ |
| 安全校验 | AST+沙箱 | 依赖用户 | 依赖用户 | 云端隔离 |
| 自修复 | ✅ | ❌ | ❌ | ❌ |

### 8.2 与 LATM 论文对比

本项目是 LATM 思想的实践实现，增加了：
- 完整的安全机制
- 可运行的 Demo
- 持久化和热加载

### 8.3 与 Voyager 对比

| Voyager (Minecraft) | Self-Evolving Agent |
|---------------------|---------------------|
| 游戏技能库 | 通用工具库 |
| JavaScript 技能 | Python 工具 |
| 无安全限制（游戏） | 严格安全校验 |
| 向量检索技能 | 名称/描述匹配 |

---

## 9. 可扩展性

### 9.1 添加新的安全检查

```python
# 在 security.py 中添加
def visit_Subscript(self, node):
    """检查危险的下标访问，如 __builtins__['eval']"""
    if isinstance(node.value, ast.Name) and node.value.id == "__builtins__":
        self.violations.append("Blocked access to __builtins__")
```

### 9.2 支持更多语言

```python
# 添加 executor_js.py
def execute_javascript(code: str, timeout: int = 30) -> ExecutionResult:
    proc = subprocess.run(
        ["node", "-e", code],
        capture_output=True,
        timeout=timeout,
        ...
    )
```

### 9.3 添加工具版本管理

```python
@dataclass
class ToolRecord:
    name: str
    version: int  # 已有
    history: List[str]  # 新增：历史代码
    created_at: datetime
    updated_at: datetime
```

### 9.4 添加工具依赖关系

```python
@dataclass
class ToolRecord:
    ...
    dependencies: List[str]  # 依赖的其他工具名
```

---

## 10. 使用示例

### 10.1 启动 Agent

```bash
# 设置 API Key
export OPENAI_API_KEY=your_key
# 或使用 .env 文件

# 交互模式
python -m self_evolving_agent.main

# 单任务模式
python -m self_evolving_agent.main --task "分析 data.csv 的销售趋势"
```

### 10.2 交互示例

```
You > 帮我创建一个计算斐波那契数列的工具

🧠 Turn 1/10
🔧 Tool: create_tool
   Args: {"tool_description": "计算第 n 个斐波那契数..."}

🔨 FORGE: Creating new tool...
   📝 Generation attempt 1/3
   🔒 Security check... ✅ passed
   🧪 Running tests in sandbox...
   ✅ Test passed: {"n": 10}
   ✅ Test passed: {"n": 1}
   ✅ All tests passed — registering 'fibonacci'

════════════════════════════════════════════════════════════
📋 Final Answer:
我已经创建了 `fibonacci` 工具。让我用它计算一下：

斐波那契(10) = 55
斐波那契(20) = 6765

这个工具现在已经注册，以后可以直接使用。
════════════════════════════════════════════════════════════

You > tools
📦 Available Tools:

── Built-in ──
  🔧 run_python: Execute Python code in a secure sandbox...
  🔧 read_file: Read a file from the sandbox...
  ...

── Agent-Created ──
  🛠️  fibonacci (v1): 计算第 n 个斐波那契数
```

---

## 附录

### A. 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `LLM_MODEL` | gpt-4o-mini | 使用的模型 |
| `SANDBOX_TIMEOUT` | 30s | 沙箱执行超时 |
| `MAX_FIX_ATTEMPTS` | 3 | 最大自修复轮次 |
| `MAX_AGENT_TURNS` | 10 | Agent 最大推理轮次 |
| `SANDBOX_DIR` | /tmp/self-evolving-sandbox | 沙箱目录 |

### B. 参考资料

- [LATM: Large Language Models as Tool Makers](https://arxiv.org/abs/2305.17126)
- [Voyager: An Open-Ended Embodied Agent](https://arxiv.org/abs/2305.16291)
- [ReAct: Synergizing Reasoning and Acting](https://arxiv.org/abs/2210.03629)
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
