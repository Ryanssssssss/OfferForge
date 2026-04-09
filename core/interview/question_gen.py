"""智能面试题生成器。

新流程：
1. RAG 从真题库搜索与岗位+简历匹配的面试真题
2. LLM 根据真题 + 简历信息，生成个性化面试题（确保与候选人项目相关）
3. 一次只出一道题，根据回答动态决定下一题
"""

import json
import logging
from typing import Any

from core.llm.thinker import thinker
from core.llm.prompts import QUESTION_GENERATION_PROMPT
from core.rag.question_bank_rag import search_questions
from config.settings import settings

logger = logging.getLogger(__name__)


class QuestionGenerator:
    """面试题生成器：RAG 检索真题 + LLM 个性化改编。"""

    def _build_resume_context(self, resume_data: dict[str, Any]) -> str:
        """将结构化简历数据转为 LLM 可读的文本。"""
        parts = []

        name = resume_data.get("name", "未知")
        parts.append(f"姓名: {name}")

        education = resume_data.get("education", [])
        if education:
            parts.append("\n【教育背景】")
            for edu in education:
                if isinstance(edu, dict):
                    parts.append(f"- {edu.get('school', '')} {edu.get('major', '')} {edu.get('degree', '')}")
                else:
                    parts.append(f"- {edu}")

        skills = resume_data.get("skills", [])
        if skills:
            skill_str = ", ".join(skills) if isinstance(skills[0], str) else json.dumps(skills, ensure_ascii=False)
            parts.append(f"\n【技能】\n{skill_str}")

        projects = resume_data.get("projects", [])
        if projects:
            parts.append("\n【项目经历】")
            for proj in projects:
                if isinstance(proj, dict):
                    parts.append(f"项目: {proj.get('name', '未命名')}")
                    if proj.get("description"):
                        parts.append(f"  描述: {proj['description']}")
                    if proj.get("tech_stack"):
                        stack = proj["tech_stack"]
                        parts.append(f"  技术栈: {', '.join(stack) if isinstance(stack, list) else stack}")
                    if proj.get("highlights"):
                        highlights = proj["highlights"]
                        if isinstance(highlights, list):
                            for h in highlights:
                                parts.append(f"  - {h}")

        internships = resume_data.get("internships", [])
        if internships:
            parts.append("\n【实习/工作经历】")
            for intern in internships:
                if isinstance(intern, dict):
                    parts.append(f"- {intern.get('company', '')} | {intern.get('role', '')} ({intern.get('duration', '')})")
                    if intern.get("responsibilities"):
                        resp = intern["responsibilities"]
                        if isinstance(resp, list):
                            for r in resp:
                                parts.append(f"    · {r}")

        return "\n".join(parts)

    def generate(
        self,
        job_category: str,
        resume_data: dict[str, Any] | None = None,
        num_questions: int | None = None,
        include_coding: bool = True,
    ) -> list[dict[str, Any]]:
        """根据真题库 + 简历生成个性化面试题。

        流程：RAG 搜索真题 → LLM 结合简历改编 → 返回题目列表
        """
        num_questions = num_questions or settings.max_questions

        # 构建简历上下文
        resume_context = ""
        if resume_data:
            resume_context = self._build_resume_context(resume_data)
            raw_text = resume_data.get("_raw_text", "")
            if raw_text:
                resume_context += f"\n\n【简历原文】\n{raw_text[:2000]}"

        # 1. RAG 检索真题
        rag_questions = search_questions(
            job_category=job_category,
            resume_context=resume_context,
            top_k=num_questions + 5,  # 多检索一些，LLM 筛选
        )

        # 格式化真题供 LLM 参考
        rag_context = ""
        if rag_questions:
            rag_lines = []
            for i, q in enumerate(rag_questions, 1):
                rag_lines.append(
                    f"{i}. [{q.get('dimension', '')}][{q.get('difficulty', '')}] {q['question']}"
                )
                follow_ups = q.get("follow_ups", [])
                if follow_ups:
                    rag_lines.append(f"   追问参考: {'; '.join(follow_ups)}")
            rag_context = "\n".join(rag_lines)

        logger.info("RAG 检索到 %d 道真题, 简历上下文 %d 字", len(rag_questions), len(resume_context))

        # 2. LLM 结合简历 + 真题生成个性化题目
        try:
            questions = thinker.think_json_with_template(
                QUESTION_GENERATION_PROMPT,
                {
                    "job_category": job_category,
                    "resume_context": resume_context,
                    "rag_questions": rag_context,
                    "num_questions": num_questions,
                },
            )
        except Exception as e:
            logger.error("面试题生成失败: %s", e)
            # 降级：直接用 RAG 真题
            if rag_questions:
                logger.info("降级使用 RAG 真题")
                return [{"id": i + 1, **q} for i, q in enumerate(rag_questions[:num_questions])]
            raise ValueError(f"面试题生成失败: {e}") from e

        if not isinstance(questions, list):
            raise ValueError("LLM 返回的面试题格式异常")

        for i, q in enumerate(questions):
            if "id" not in q:
                q["id"] = i + 1

        # 3. 技术岗最后追加一道 LeetCode Hot 100 算法题
        tech_categories = {"后端开发", "前端开发", "全栈开发", "数据工程师", "算法工程师", "测试工程师", "DevOps"}
        if job_category in tech_categories:
            algo_question = self._pick_leetcode_question()
            if algo_question:
                algo_question["id"] = len(questions) + 1
                questions.append(algo_question)

        logger.info("成功生成 %d 道面试题 (岗位: %s)", len(questions), job_category)
        return questions

    @staticmethod
    def _pick_leetcode_question() -> dict[str, Any] | None:
        """从 LeetCode Hot 100 题库随机选一道，作为算法题。"""
        import random
        from pathlib import Path

        lc_path = Path(settings.question_bank_path).parent / "leetcode_hot100.json"
        if not lc_path.exists():
            return None

        try:
            with open(lc_path, "r", encoding="utf-8") as f:
                lc_questions = json.load(f)
        except Exception:
            return None

        if not lc_questions:
            return None

        # 优先选 medium 难度（面试最常见）
        medium_qs = [q for q in lc_questions if q.get("difficulty") == "medium"]
        pool = medium_qs if medium_qs else lc_questions
        chosen = random.choice(pool)

        return {
            "question": f"算法题：LeetCode {chosen['id']}. {chosen['title']}。请在右侧代码编辑器中完成解题，也可以在下方输入框讨论思路。",
            "type": "technical",
            "dimension": "算法与数据结构",
            "difficulty": chosen.get("difficulty", "medium"),
            "related_resume_point": "编程基础",
            "follow_up_hints": ["时间复杂度能优化吗？", "有没有其他解法？"],
            "leetcode_id": chosen["id"],
            "leetcode_tags": chosen.get("tags", []),
        }
