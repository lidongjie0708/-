from __future__ import annotations

from app.infra.llm import llm_client


def generate_article(topic: str, keywords: list[str], style: str, requirement: str | None = None) -> dict:
    fallback = {
        "title": f"{topic}实战指南",
        "outline": ["背景与目标", "核心设计", "实现步骤", "常见问题", "总结"],
        "content": (
            f"# {topic}实战指南\n\n"
            "## 背景与目标\n\n本文围绕实际博客系统场景，说明需求、架构和实现路径。\n\n"
            "## 核心设计\n\n采用服务解耦方式，由 Spring Boot 负责业务，Python Agent 服务负责 AI 能力。\n\n"
            "## 实现步骤\n\n1. 定义接口。\n2. 编排 Agent。\n3. 接入 RAG。\n4. 保存结果。\n\n"
            "## 总结\n\n该方案适合逐步迭代，并能体现 AI 应用工程能力。"
        ),
        "summary": f"本文介绍{topic}的设计与实现。",
        "tags": keywords[:5] or [topic, "AI Agent", "RAG"],
        "coverPrompt": f"一张简洁现代的技术博客封面，主题是{topic}",
    }
    prompt = {
        "topic": topic,
        "keywords": keywords,
        "style": style,
        "requirement": requirement or "",
        "output": "JSON with title, outline, content, summary, tags, coverPrompt",
    }
    return llm_client.complete_json(
        "你是智能写作 Agent，输出严格 JSON，不要 Markdown 包裹。",
        str(prompt),
        fallback,
    )


def summarize(title: str | None, content: str | None) -> dict:
    text = (content or "").strip()
    if not text:
        return {"summary": ""}
    fallback = {"summary": text[:180] + ("..." if len(text) > 180 else "")}
    return llm_client.complete_json(
        "你是文章摘要 Agent，输出 JSON：{\"summary\":\"...\"}",
        f"标题：{title or ''}\n正文：{text[:4000]}",
        fallback,
    )


def recommend_tags(title: str | None, content: str | None) -> dict:
    words = [word for word in [title, "LangChain", "LangGraph", "RAG", "Spring Boot"] if word]
    fallback = {"tags": list(dict.fromkeys(words))[:5]}
    return llm_client.complete_json(
        "你是标签推荐 Agent，输出 JSON：{\"tags\":[\"...\"]}",
        f"标题：{title or ''}\n正文：{(content or '')[:3000]}",
        fallback,
    )
