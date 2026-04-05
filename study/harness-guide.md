# Harness 思想完全指南

> 让你从"写 Agent 代码"转变为"为 Agent 构建世界"

---

## 第一章：什么是 Harness？

### 1.1 一句话定义

```
模型是 Agent，代码是 Harness。
```

**Harness** 的字面意思是"马具"或"驾驭装置"。在 Agent 工程中：

| 概念 | 类比 | 职责 |
|------|------|------|
| **Model（模型）** | 驾驶员 | 负责思考、决策、规划 |
| **Harness（代码）** | 载具 | 提供能力、执行动作、连接世界 |

### 1.2 核心洞见

**错误思维**：用代码"制造"智能  
**正确思维**：为已有的智能（模型）构建一个可操作的世界

模型（如 Claude、GPT-4）已经通过大规模训练习得了：
- 如何推理
- 何时使用工具
- 如何拆解任务
- 何时停止

你的代码不需要教它这些——只需**给它施展的空间**。

### 1.3 Harness 的五大组件

```
Harness = Tools + Knowledge + Observation + Action Interfaces + Permissions
```

| 组件 | 回答的问题 | 示例 |
|------|-----------|------|
| **Tools（工具）** | Agent 能做什么？ | bash、read_file、write_file |
| **Knowledge（知识）** | Agent 知道什么？ | SKILL.md、领域文档 |
| **Observation（观察）** | Agent 看到什么？ | git diff、错误日志、文件内容 |
| **Action Interfaces** | Agent 如何与外部交互？ | CLI、API、UI |
| **Permissions（权限）** | Agent 允许做什么？ | 沙箱、审批流程 |

---

## 第二章：Harness 的核心——Agent Loop

### 2.1 最简循环：19 行代码

这是 Harness 的心脏——一个简单的 while 循环：

```python
# agents/s01_agent_loop.py
# Harness: the loop -- the model's first connection to the real world.

def agent_loop(messages: list):
    while True:
        # Think: 让模型思考
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})
        
        # 关键：模型决定何时停止（不是代码决定）
        if response.stop_reason != "tool_use":
            return  # 模型说"我完成了"
            
        # Act: 执行模型请求的工具
        results = []
        for block in response.content:
            if block.type == "tool_use":
                output = run_bash(block.input["command"])
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output
                })
        
        # Observe: 把结果反馈给模型
        messages.append({"role": "user", "content": results})
```

### 2.2 核心理解

**循环永远不变**，变的是：
- 工具数量（1 个 → N 个）
- 上下文管理（简单 → 压缩 → 持久化）
- 执行方式（同步 → 异步 → 多 Agent）

```
┌─────────────────────────────────────────┐
│              Agent Loop                  │
│  ┌──────────────────────────────────┐   │
│  │  Think: 调用 LLM                  │   │
│  └──────────────┬───────────────────┘   │
│                 │                        │
│                 ▼                        │
│  ┌──────────────────────────────────┐   │
│  │  stop_reason == "tool_use"?      │   │
│  │  - Yes → 继续执行工具             │   │
│  │  - No  → 返回（模型完成了）       │   │
│  └──────────────┬───────────────────┘   │
│                 │ Yes                    │
│                 ▼                        │
│  ┌──────────────────────────────────┐   │
│  │  Act: 执行工具，收集结果          │   │
│  └──────────────┬───────────────────┘   │
│                 │                        │
│                 ▼                        │
│  ┌──────────────────────────────────┐   │
│  │  Observe: 反馈结果给模型          │   │
│  └──────────────┴───────────────────┘   │
│                 │                        │
│                 └────────→ 循环 ─────────┘
└─────────────────────────────────────────┘
```

---

## 第三章：工具分发——扩展 Agent 的能力

### 3.1 Dispatch Map 模式

```python
# agents/s02_tool_use.py
# Harness: tool dispatch -- expanding what the model can reach.

TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
}

def dispatch_tool(name: str, args: dict) -> str:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return f"Unknown tool: {name}"
    return handler(**args)
```

### 3.2 核心原则

**循环代码不变**——只需扩展 dispatch map：

```python
# 新增工具？只需一行
TOOL_HANDLERS["search_web"] = lambda **kw: search_web(kw["query"])
```

这就是 Harness 的优雅之处：**工具是可插拔的模块**。

---

## 第四章：上下文隔离——Subagent

### 4.1 问题：上下文污染

当一个复杂任务展开时，上下文迅速膨胀：
- 搜索结果（几千字）
- 文件内容（可能几万字）
- 中间推理过程

后果：模型被噪音淹没，遗忘了原始任务。

### 4.2 解法：Subagent（子 Agent）

```python
# agents/s04_subagent.py
# Harness: context isolation -- protecting the model's clarity of thought.

def run_subagent(prompt: str) -> str:
    """启动一个隔离的子 Agent"""
    # 关键：全新的上下文，不继承主 Agent 的历史
    sub_messages = [{"role": "user", "content": prompt}]
    
    # 子 Agent 运行完整的 agent loop
    while True:
        response = client.messages.create(...)
        if response.stop_reason != "tool_use":
            break
        # ... 执行工具 ...
    
    # 只返回摘要，整个子上下文被丢弃
    return "".join(b.text for b in response.content if hasattr(b, "text"))
```

### 4.3 核心洞见

```
主 Agent 上下文: [任务A] [任务B] [子任务C 的摘要]
                                    ↑
                              只有一行摘要
                              
子 Agent 上下文: [子任务C] [搜索结果1] [搜索结果2] [分析过程] → 被丢弃
                                                        ↑
                                              几千 token 的噪音
```

**子 Agent 是"一次性工人"**：干完活，交报告，走人。

---

## 第五章：技能加载——按需注入知识

### 5.1 问题：模型不懂特定领域

通用模型不知道：
- 你们公司的代码规范
- 特定 API 的使用方式
- 项目特有的架构约定

### 5.2 解法：Skills（技能系统）

```python
# agents/s05_skills.py
# Harness: loadable expertise -- teaching the model your domain.

def load_skill(skill_name: str) -> str:
    """按需加载领域知识"""
    skill_path = f"skills/{skill_name}/SKILL.md"
    return Path(skill_path).read_text()

# 在 system prompt 中动态注入
def build_system_prompt(active_skills: list) -> str:
    base = "You are a helpful assistant..."
    for skill in active_skills:
        base += f"\n\n<skill name='{skill}'>\n{load_skill(skill)}\n</skill>"
    return base
```

### 5.3 SKILL.md 示例

```markdown
# Python Best Practices

## 规则
1. 使用 type hints
2. 函数不超过 20 行
3. 优先使用 pathlib 而非 os.path

## 常用模式
- 文件读写：使用 `with open()` 上下文管理器
- 错误处理：具体异常优于 `except Exception`
```

---

## 第六章：上下文压缩——对抗 Token 限制

### 6.1 问题：上下文爆炸

每次工具调用都往 messages 里加内容，很快就会超出模型的上下文窗口。

### 6.2 三层压缩策略

```python
# agents/s06_context_compact.py

def compact_context(messages: list, max_tokens: int) -> list:
    """三层渐进压缩"""
    
    # 第一层：截断过长的工具输出
    for msg in messages:
        if msg.get("type") == "tool_result":
            msg["content"] = truncate(msg["content"], 5000)
    
    # 第二层：移除中间轮次的详细输出，保留摘要
    if estimate_tokens(messages) > max_tokens:
        messages = keep_recent_n(messages, n=10)
    
    # 第三层：让 LLM 生成摘要替代旧消息
    if estimate_tokens(messages) > max_tokens:
        summary = llm_summarize(messages[:-10])
        messages = [{"role": "user", "content": f"<context_summary>{summary}</context_summary>"}] + messages[-10:]
    
    return messages
```

---

## 第七章：12 个课程的 Harness 演进

项目通过 12 个递进式课程展示 Harness 的完整构建过程：

```
阶段一：基础循环
├── s01: Agent Loop        → while 循环 + stop_reason
└── s02: Tool Dispatch     → dispatch map 扩展工具

阶段二：规划与知识
├── s03: TodoWrite         → 内存任务管理
├── s04: Subagent          → 上下文隔离
├── s05: Skills            → 按需加载知识
└── s06: Context Compact   → 三层压缩策略

阶段三：持久化
├── s07: Task System       → 文件持久化任务图
└── s08: Background Tasks  → 守护线程 + 通知队列

阶段四：多 Agent 协作
├── s09: Agent Teams       → 多 Agent + JSONL 邮箱
├── s10: Team Protocols    → 关机/审批协商协议
├── s11: Autonomous Agents → WORK/IDLE 两阶段循环
└── s12: Worktree Isolation→ git worktree 目录隔离
```

---

## 第八章：Harness 设计哲学

### 8.1 核心原则

| 原则 | 说明 |
|------|------|
| **模型做决策** | 代码不要抢模型的活（如判断任务是否完成） |
| **循环保持简单** | 复杂性在工具层，不在循环层 |
| **工具可插拔** | dispatch map 模式，随时扩展 |
| **上下文是资源** | 像内存一样管理，压缩、隔离、持久化 |
| **失败是信息** | 错误输出反馈给模型，让它自己修复 |

### 8.2 最好的 Harness 代码是"无聊"的

```python
# 好代码：简单、清晰、可预测
while True:
    response = llm.chat(messages)
    if done(response): return
    result = dispatch(response.tool_call)
    messages.append(result)

# 坏代码：试图"智能化"
while True:
    response = llm.chat(messages)
    if my_smart_logic_decides_its_done(response):  # ← 抢模型的活
        return
    if should_i_call_this_tool(response):  # ← 抢模型的活
        result = dispatch(response.tool_call)
```

**魔法不在代码里——在模型里。**

---

## 第九章：快速上手路径

### 9.1 学习顺序

1. **读懂 s01**：理解 Agent Loop 的本质
2. **读懂 s02**：理解工具扩展的模式
3. **读懂 s04**：理解上下文隔离的必要性
4. **动手实践**：用 s01 的模式写一个你自己的小 Agent

### 9.2 关键文件

| 文件 | 说明 |
|------|------|
| `agents/s01_agent_loop.py` | 最简循环，必读 |
| `agents/s02_tool_use.py` | 工具分发模式 |
| `agents/s04_subagent.py` | 上下文隔离 |
| `agents/s_full.py` | 完整实现参考 |
| `skills/agent-builder/references/agent-philosophy.md` | 哲学文档 |
| `skills/agent-builder/references/minimal-agent.py` | ~80 行最简实现 |

### 9.3 练习建议

**练习 1**：用 s01 的模式实现一个"文件整理 Agent"
- 工具：list_dir、move_file、create_folder
- 任务：按文件类型整理 ~/Downloads

**练习 2**：给练习 1 加上 Subagent
- 当需要分析文件内容时，启动子 Agent 处理
- 子 Agent 的分析结果以摘要形式返回

---

## 第十章：总结

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   模型是 Agent。代码是 Harness。                              │
│                                                             │
│   不要试图用代码"制造"智能，                                   │
│   而是为已有的智能（模型）构建一个可以工作的世界。                │
│                                                             │
│   最好的 Harness 代码几乎是无聊的：                            │
│   简单循环、清晰的工具定义、干净的上下文管理。                    │
│                                                             │
│   魔法不在代码里——在模型里。                                   │
│                                                             │
│   Build great harnesses. The agent will do the rest.        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```
