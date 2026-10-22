"""Explainable keyword comparison. No LLM, no hiring prediction."""
import re

# Bounded aliases prevent Java/JavaScript and SQL/MySQL substring collisions.
SKILLS = {
    "Python": r"(?<![a-z0-9])python(?![a-z0-9])",
    "JavaScript": r"(?<![a-z0-9])(?:javascript|js)(?![a-z0-9])",
    "TypeScript": r"(?<![a-z0-9])(?:typescript|ts)(?![a-z0-9])",
    "Java": r"(?<![a-z0-9])java(?![a-z0-9])",
    "HTML": r"(?<![a-z0-9])html(?:5)?(?![a-z0-9])",
    "CSS": r"(?<![a-z0-9])css(?:3)?(?![a-z0-9])",
    "React": r"(?<![a-z0-9])react(?:\.js)?(?![a-z0-9])",
    "Vue": r"(?<![a-z0-9])vue(?:\.js)?(?![a-z0-9])",
    "FastAPI": r"(?<![a-z0-9])fastapi(?![a-z0-9])",
    "Flask": r"(?<![a-z0-9])flask(?![a-z0-9])",
    "Django": r"(?<![a-z0-9])django(?![a-z0-9])",
    "SQL": r"(?<![a-z0-9])sql(?![a-z0-9])",
    "SQLite": r"(?<![a-z0-9])sqlite(?:3)?(?![a-z0-9])",
    "MySQL": r"(?<![a-z0-9])mysql(?![a-z0-9])",
    "PostgreSQL": r"(?<![a-z0-9])(?:postgresql|postgres)(?![a-z0-9])",
    "Git": r"(?<![a-z0-9])git(?![a-z0-9])",
    "Docker": r"(?<![a-z0-9])docker(?![a-z0-9])",
    "Linux": r"(?<![a-z0-9])linux(?![a-z0-9])",
    "API": r"(?<![a-z0-9])(?:restful|rest\s*api|api)(?![a-z0-9])|接口",
    "自动化测试": r"(?<![a-z0-9])(?:pytest|unittest)(?![a-z0-9])|自动化测试|单元测试",
    "Codex": r"(?<![a-z0-9])codex(?![a-z0-9])",
    "Claude Code": r"(?<![a-z0-9])claude\s*code(?![a-z0-9])",
    "DeepSeek": r"(?<![a-z0-9])deepseek(?![a-z0-9])",
    "Agent": r"(?<![a-z0-9])agents?(?![a-z0-9])|智能体",
    "RAG": r"(?<![a-z0-9])rag(?![a-z0-9])|检索增强生成",
    "LangGraph": r"(?<![a-z0-9])langgraph(?![a-z0-9])",
    "LangChain": r"(?<![a-z0-9])langchain(?![a-z0-9])",
    "工具调用": r"(?<![a-z0-9])(?:function\s*calling|tool[ -]?use|tool[ -]?calling)(?![a-z0-9])|工具调用",
    "Prompt": r"(?<![a-z0-9])prompt(?:\s*engineering)?(?![a-z0-9])|提示词",
    "MCP": r"(?<![a-z0-9])mcp(?![a-z0-9])",
    "独立部署": r"独立部署|本地部署|项目部署|跑起来|运行项目",
}

QUESTIONS = {
    "Agent": ("Agent 为什么要限制轮次与工具权限？", "打开 agent.py，解释模型提出调用、程序校验、执行、结果回传和终止的全过程。"),
    "RAG": ("如何区分检索命中率和生成回答正确率？", "说明分块、索引、召回、引用与评测；展示一个检索失败案例。"),
    "工具调用": ("模型生成的参数为什么不能直接执行？", "解释工具白名单、参数校验、异常回传和执行权限。"),
    "Prompt": ("怎样验证提示词修改带来的影响？", "用同一组题目对比结果，记录模型与参数，不能仅展示一个成功例子。"),
    "Python": ("为什么把分析逻辑和 HTTP 接口拆开？", "从职责、可测试性、异常处理三个方面解释，并找到对应源码。"),
    "SQLite": ("SQLite 如何保存投递进度？", "说明表字段、参数化查询、事务，以及为什么每次请求单独连接。"),
    "SQL": ("怎样防止输入内容变成 SQL 指令？", "打开 storage.py，解释占位符与字符串拼接的区别。"),
    "API": ("新增投递记录时，浏览器和服务端怎样协作？", "演示 POST 请求、JSON 校验、状态码与前端刷新。"),
    "JavaScript": ("怎样避免投递备注被当成 HTML 执行？", "查看 textContent 的使用位置，解释用户输入如何进入页面。"),
    "自动化测试": ("你如何验证关键词误匹配和数据库持久化？", "现场运行测试，并新增一个此前没有覆盖的边界案例。"),
    "Codex": ("你如何使用 Codex，并验证生成的代码？", "给出一次真实的需求、生成、运行、发现问题和修复记录。"),
    "Claude Code": ("你用 Claude Code 完成过什么具体任务？", "只回答实际用过的工具，说明验证方式和亲自修改的部分。"),
    "Git": ("如何把一次修复做成可审查的提交？", "演示 diff、选择文件、提交和 .gitignore，解释为什么数据文件不提交。"),
    "独立部署": ("在另一台电脑上怎样把项目跑起来？", "说明 Python 版本、启动命令、端口冲突处理及本地使用边界。"),
}


def extract(text):
    """Return source fragments, not inferred proficiency or semantic proof."""
    parts = [p.strip() for p in re.split(r"[\n。；;!?！？]", text) if p.strip()]
    found = {}
    for name, pattern in SKILLS.items():
        evidence = []
        for part in parts:
            if re.search(pattern, part, re.I):
                evidence.append(part[:220])
        if evidence:
            found[name] = evidence[:3]
    return found


def compare(jd, resume):
    required, stated = extract(jd), extract(resume)
    covered = [{"skill": name, "job_evidence": snippets, "resume_evidence": stated[name]}
               for name, snippets in required.items() if name in stated]
    missing = [{"skill": name, "job_evidence": snippets}
               for name, snippets in required.items() if name not in stated]
    questions = []
    for item in missing + covered:
        name = item["skill"]
        title, guide = QUESTIONS.get(name, (f"请用项目中的真实例子说明 {name} 的用途。", "说明输入、处理、输出和遇到的一个问题；没用过就如实说明。"))
        questions.append({"skill": name, "question": title, "guide": guide,
                          "priority": "先补证据" if name not in stated else "准备讲解"})
    questions.append({"skill": "产品思考", "question": "为什么先做这些功能，下一步会改什么？",
                      "guide": "围绕一个真实用户问题，讲清取舍、当前限制和可验证的改进。", "priority": "准备讲解"})
    return {"required": len(required), "covered": covered, "missing": missing,
            "coverage": round(len(covered) / len(required) * 100) if required else None,
            "questions": questions,
            "notice": "仅对照内置词表的文字提及，不判断熟练度、否定语义或录用概率；请逐条核对原文。未提及不代表不会。"}
