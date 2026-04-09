"""LangGraph 状态机各节点实现。

引入按实体分割的 memory 系统：每个项目/实习/论文独立追踪，不会串。
"""

import logging
from typing import Any

from core.agent.states import InterviewState, ConversationMessage, InterviewMemory, EntityRecord
from core.resume.extractor import extract_resume_info
from core.interview.question_gen import QuestionGenerator
from core.interview.evaluator import AnswerEvaluator
from core.interview.reporter import ReportGenerator
from core.llm.thinker import thinker
from core.llm.prompts import INTERVIEWER_ASK_PROMPT
from config.settings import settings

logger = logging.getLogger(__name__)

_question_gen = QuestionGenerator()
_evaluator = AnswerEvaluator()
_reporter = ReportGenerator()


# ── Memory 工具函数 ──

def _init_memory_from_resume(resume_data: dict) -> InterviewMemory:
    """从简历数据初始化 memory，为每个项目/实习/论文/研究创建独立记录。"""
    entities: dict[str, EntityRecord] = {}

    # 项目
    for proj in resume_data.get("projects", []):
        name = proj.get("name", "未命名项目")
        entities[name] = {
            "name": name, "entity_type": "project",
            "asked_topics": [], "candidate_answers": [], "status": "not_started",
        }

    # 实习
    for intern in resume_data.get("internships", []):
        name = f"{intern.get('company', '')}_{intern.get('role', '')}"
        entities[name] = {
            "name": name, "entity_type": "internship",
            "asked_topics": [], "candidate_answers": [], "status": "not_started",
        }

    # 论文
    for pub in resume_data.get("publications", []):
        name = pub.get("title", "未命名论文")
        entities[name] = {
            "name": name, "entity_type": "publication",
            "asked_topics": [], "candidate_answers": [], "status": "not_started",
        }

    # 研究经历
    for res in resume_data.get("research", []):
        name = res.get("topic", "未命名研究")
        entities[name] = {
            "name": name, "entity_type": "research",
            "asked_topics": [], "candidate_answers": [], "status": "not_started",
        }

    # 教育
    for edu in resume_data.get("education", []):
        name = f"{edu.get('school', '')}_{edu.get('major', '')}"
        entities[name] = {
            "name": name, "entity_type": "education",
            "asked_topics": [], "candidate_answers": [], "status": "not_started",
        }
            "entity_type": "internship",
            "asked_topics": [],
            "candidate_answers": [],
            "status": "not_started",
        }

    # 教育
    for edu in resume_data.get("education", []):
        name = f"{edu.get('school', '')}_{edu.get('major', '')}"
        entities[name] = {
            "name": name,
            "entity_type": "education",
            "asked_topics": [],
            "candidate_answers": [],
            "status": "not_started",
        }

    return {
        "entities": entities,
        "current_entity": "",
        "general_topics": [],
        "covered_dimensions": [],
    }


def _get_memory(state: InterviewState) -> InterviewMemory:
    """获取 memory。"""
    return state.get("interview_memory", {
        "entities": {},
        "current_entity": "",
        "general_topics": [],
        "covered_dimensions": [],
    })


def _format_memory(memory: InterviewMemory) -> str:
    """格式化 memory 为 LLM 可读的结构化文本。按实体分割展示。"""
    parts = []

    current = memory.get("current_entity", "")
    if current:
        parts.append(f"【当前正在聊的项目/经历】{current}")

    entities = memory.get("entities", {})
    if entities:
        # 按状态分组
        done_list = []
        in_progress_list = []
        not_started_list = []

        for name, record in entities.items():
            status = record.get("status", "not_started")
            topics = record.get("asked_topics", [])
            answers = record.get("candidate_answers", [])

            if status == "done":
                done_list.append(f"  - {name}（已完成）已问: {', '.join(topics[:3])}")
            elif status == "in_progress":
                info = f"  - {name}（进行中）已问: {', '.join(topics)}"
                if answers:
                    info += f"｜候选人说: {'；'.join(answers[-2:])}"
                in_progress_list.append(info)
            else:
                not_started_list.append(f"  - {name}（未开始）")

        if in_progress_list:
            parts.append("【进行中的实体】\n" + "\n".join(in_progress_list))
        if done_list:
            parts.append("【已聊完的实体】\n" + "\n".join(done_list))
        if not_started_list:
            parts.append("【还没聊到的实体】\n" + "\n".join(not_started_list))

    dims = memory.get("covered_dimensions", [])
    if dims:
        parts.append(f"【已考察维度】{', '.join(dims)}")

    general = memory.get("general_topics", [])
    if general:
        parts.append(f"【通用话题】{', '.join(general)}")

    return "\n".join(parts) if parts else "（暂无记录）"


def _find_entity_for_question(memory: InterviewMemory, question: dict) -> str:
    """根据题目的 related_resume_point 匹配到 memory 中的实体名。"""
    related = question.get("related_resume_point", "")
    if not related:
        return ""

    entities = memory.get("entities", {})
    # 精确匹配
    if related in entities:
        return related
    # 模糊匹配
    related_lower = related.lower()
    for name in entities:
        if related_lower in name.lower() or name.lower() in related_lower:
            return name
    return related  # 没匹配到就用原文


def _update_memory_for_question(memory: InterviewMemory, question: dict) -> InterviewMemory:
    """提问时更新 memory：设置当前实体、记录话题。"""
    new_memory = {
        "entities": {k: {**v} for k, v in memory.get("entities", {}).items()},
        "current_entity": memory.get("current_entity", ""),
        "general_topics": list(memory.get("general_topics", [])),
        "covered_dimensions": list(memory.get("covered_dimensions", [])),
    }

    entity_name = _find_entity_for_question(memory, question)
    topic = question.get("question", "")[:50]
    dimension = question.get("dimension", "")

    if entity_name and entity_name in new_memory["entities"]:
        # 切换到这个实体
        # 先把之前的实体标记为 done（如果有的话）
        old_entity = new_memory["current_entity"]
        if old_entity and old_entity != entity_name and old_entity in new_memory["entities"]:
            new_memory["entities"][old_entity]["status"] = "done"

        new_memory["current_entity"] = entity_name
        new_memory["entities"][entity_name]["status"] = "in_progress"
        new_memory["entities"][entity_name]["asked_topics"] = \
            list(new_memory["entities"][entity_name].get("asked_topics", [])) + [topic]
    else:
        # 通用话题（如算法题）
        new_memory["general_topics"].append(topic)

    if dimension and dimension not in new_memory["covered_dimensions"]:
        new_memory["covered_dimensions"].append(dimension)

    return new_memory


def _update_memory_for_answer(memory: InterviewMemory, answer: str, question_idx: int) -> InterviewMemory:
    """回答时更新 memory：记录候选人的关键回答。"""
    new_memory = {
        "entities": {k: {**v} for k, v in memory.get("entities", {}).items()},
        "current_entity": memory.get("current_entity", ""),
        "general_topics": list(memory.get("general_topics", [])),
        "covered_dimensions": list(memory.get("covered_dimensions", [])),
    }

    current = new_memory["current_entity"]
    if current and current in new_memory["entities"] and len(answer) > 10:
        answers = list(new_memory["entities"][current].get("candidate_answers", []))
        answers.append(answer[:100])
        new_memory["entities"][current]["candidate_answers"] = answers

    return new_memory


# ── 节点实现 ──

def parse_resume_node(state: InterviewState) -> dict[str, Any]:
    """节点：解析简历，初始化实体级 memory。"""
    resume_file = state["resume_file"]
    logger.info("开始解析简历: %s", resume_file)

    resume_data = extract_resume_info(resume_file)
    logger.info("简历解析完成")

    # 初始化 memory，为每个项目/实习/教育创建独立记录
    memory = _init_memory_from_resume(resume_data)
    entity_names = list(memory["entities"].keys())
    logger.info("初始化 memory，识别到 %d 个实体: %s", len(entity_names), entity_names)

    greeting = f"您好，{resume_data.get('name', '')}！我已经仔细阅读了您的简历。请选择您要面试的目标岗位，我将根据您的经历为您定制面试题目。"

    return {
        "resume_parsed": resume_data,
        "thinker_output": greeting,
        "interview_phase": "job_selection",
        "needs_input": True,
        "conversation_history": [{"role": "interviewer", "content": greeting}],
        "interview_memory": memory,
    }


def generate_questions_node(state: InterviewState) -> dict[str, Any]:
    """节点：生成面试题。题目数量根据简历实体数动态决定。"""
    job_category = state["job_category"]
    resume_parsed = state.get("resume_parsed", {})
    include_coding = state.get("include_coding", True)

    is_algo_only = "算法题" in job_category

    # ── 纯算法题模式：直接从 LeetCode 题库选题 ──
    if is_algo_only:
        import random
        num_algo = 5  # 默认 5 道算法题
        questions = []
        used_ids = set()
        for i in range(num_algo):
            q = _question_gen._pick_leetcode_question()
            # 防重复
            while q and q.get("leetcode_id") in used_ids:
                q = _question_gen._pick_leetcode_question()
            if q:
                used_ids.add(q["leetcode_id"])
                q["id"] = i + 1
                questions.append(q)

        intro = f"纯算法模式，共 {len(questions)} 道 LeetCode 题。请在代码编辑器里完成。"
        history = list(state.get("conversation_history", []))
        history.append({"role": "interviewer", "content": intro})

        return {
            "questions": questions,
            "current_question_idx": 0,
            "follow_up_count": 0,
            "max_follow_ups": 1,
            "evaluations": [],
            "current_question_answers": [],
            "thinker_output": intro,
            "interview_phase": "ready_to_ask",
            "needs_input": False,
            "conversation_history": history,
        }

    # ── 正常模式 ──
    num_projects = len(resume_parsed.get("projects", []))
    num_internships = len(resume_parsed.get("internships", []))
    num_publications = len(resume_parsed.get("publications", []))
    num_research = len(resume_parsed.get("research", []))

    is_deep_mode = "拷打" in job_category

    if is_deep_mode:
        # 实习 3 题，项目 2 题，论文/研究各 2 题
        num_questions = num_internships * 3 + num_projects * 2 + (num_publications + num_research) * 2
    else:
        # 实习 2 题，项目 1 题，论文/研究 1 题，八股 3 题，自介 1 题
        num_questions = 1 + num_internships * 2 + num_projects + (num_publications + num_research) + 3

    num_questions = max(num_questions, 3)
    num_questions = min(num_questions, 18)

    logger.info("生成面试题: 岗位=%s, 实习=%d, 项目=%d, 题目数=%d, 代码题=%s",
                job_category, num_internships, num_projects, num_questions, include_coding)

    questions = _question_gen.generate(
        job_category, resume_data=resume_parsed,
        num_questions=num_questions, include_coding=include_coding,
    )

    # 确认代码题确实在最后（硬保障）
    has_leetcode = any(q.get("leetcode_id") for q in questions)
    if include_coding and not has_leetcode:
        logger.warning("LLM 没生成代码题，系统强制追加")
        algo = _question_gen._pick_leetcode_question()
        if algo:
            algo["id"] = len(questions) + 1
            questions.append(algo)

    intro = f"面试开始，共{len(questions)}道题。请结合你的实际经历作答。"

    history = list(state.get("conversation_history", []))
    history.append({"role": "interviewer", "content": intro})

    return {
        "questions": questions,
        "current_question_idx": 0,
        "follow_up_count": 0,
        "max_follow_ups": settings.max_follow_ups_per_question,
        "evaluations": [],
        "current_question_answers": [],
        "thinker_output": intro,
        "interview_phase": "ready_to_ask",
        "needs_input": False,
        "conversation_history": history,
    }


def ask_question_node(state: InterviewState) -> dict[str, Any]:
    """节点：面试官提出当前问题，带实体级 memory。"""
    idx = state["current_question_idx"]
    questions = state["questions"]
    question = questions[idx]

    memory = _get_memory(state)
    # 更新 memory：切换实体、记录话题
    new_memory = _update_memory_for_question(memory, question)
    memory_str = _format_memory(new_memory)
    conv_str = _format_conversation(state.get("conversation_history", []))

    # 构建当前题目的完整上下文（包含关联项目）
    related_project = question.get("related_resume_point", "")
    question_with_context = question["question"]
    if related_project:
        question_with_context = f"[关于项目/经历: {related_project}] {question['question']}"

    interviewer_speech = thinker.think_with_template(
        INTERVIEWER_ASK_PROMPT,
        {
            "job_category": state["job_category"],
            "current_idx": idx + 1,
            "total_questions": len(questions),
            "current_question": question_with_context,
            "dimension": question.get("dimension", "综合"),
            "conversation_history": conv_str,
            "interview_memory": memory_str,
        },
    )

    history = list(state.get("conversation_history", []))
    history.append({"role": "interviewer", "content": interviewer_speech})

    return {
        "thinker_output": interviewer_speech,
        "interview_phase": "waiting_answer",
        "needs_input": True,
        "follow_up_count": 0,
        "current_question_answers": [],
        "conversation_history": history,
        "interview_memory": new_memory,
    }


def process_answer_node(state: InterviewState) -> dict[str, Any]:
    """节点：处理候选人回答。"""
    answer = state["current_answer"]
    idx = state["current_question_idx"]
    question = state["questions"][idx]
    follow_up_count = state.get("follow_up_count", 0)
    max_follow_ups = state.get("max_follow_ups", settings.max_follow_ups_per_question)

    memory = _get_memory(state)
    new_memory = _update_memory_for_answer(memory, answer, idx)

    history = list(state.get("conversation_history", []))
    history.append({"role": "candidate", "content": answer})

    current_answers = list(state.get("current_question_answers", []))
    current_answers.append(answer)

    # ── 跳过检测：用户说"下一题/不会/跳过"时直接进下一题 ──
    skip_keywords = {"下一题", "跳过", "不会", "pass", "skip", "不知道", "不了解", "不清楚", "算了"}
    answer_stripped = answer.strip().lower().replace("，", "").replace("。", "")
    is_skip = any(kw in answer_stripped for kw in skip_keywords) and len(answer_stripped) < 20

    if is_skip:
        # 直接跳过，不走 LLM 评估
        response = "好，我们换一个。"
        history.append({"role": "interviewer", "content": response})

        # 给这题一个低分评估
        question_eval = {
            "question_id": question["id"],
            "question": question["question"],
            "scores": {},
            "overall_score": 0,
            "strengths": [],
            "improvements": ["候选人选择跳过"],
            "full_answer": answer,
        }
        evaluations = list(state.get("evaluations", []))
        evaluations.append(question_eval)

        next_idx = idx + 1
        is_last = next_idx >= len(state["questions"])

        return {
            "thinker_output": response,
            "interview_phase": "generate_report" if is_last else "ready_to_ask",
            "needs_input": False,
            "current_question_idx": next_idx,
            "current_question_answers": [],
            "follow_up_count": 0,
            "evaluations": evaluations,
            "conversation_history": history,
            "interview_memory": new_memory,
        }

    # ── 正常流程：LLM 评估 ──
    conv_str = _format_conversation(history)
    memory_str = _format_memory(new_memory)

    eval_result = _evaluator.evaluate_for_followup(
        job_category=state["job_category"],
        current_question=question["question"],
        dimension=question.get("dimension", "综合"),
        candidate_answer=answer,
        conversation_history=conv_str,
        follow_up_count=follow_up_count,
        max_follow_ups=max_follow_ups,
        interview_memory=memory_str,
    )

    need_followup = eval_result.get("need_followup", False) and follow_up_count < max_follow_ups
    response = eval_result.get("response", "")

    history.append({"role": "interviewer", "content": response})

    if need_followup:
        return {
            "thinker_output": response,
            "interview_phase": "waiting_answer",
            "needs_input": True,
            "follow_up_count": follow_up_count + 1,
            "current_question_answers": current_answers,
            "conversation_history": history,
            "interview_memory": new_memory,
        }
    else:
        full_answer = "\n".join(current_answers)
        question_eval = _evaluator.evaluate_answer(
            question=question["question"],
            question_type=question.get("type", "behavioral"),
            dimension=question.get("dimension", "综合"),
            full_answer=full_answer,
        )
        question_eval["question_id"] = question["id"]
        question_eval["question"] = question["question"]
        question_eval["full_answer"] = full_answer

        evaluations = list(state.get("evaluations", []))
        evaluations.append(question_eval)

        next_idx = idx + 1
        is_last = next_idx >= len(state["questions"])

        return {
            "thinker_output": response,
            "interview_phase": "generate_report" if is_last else "ready_to_ask",
            "needs_input": False,
            "current_question_idx": next_idx,
            "current_question_answers": [],
            "follow_up_count": 0,
            "evaluations": evaluations,
            "conversation_history": history,
            "interview_memory": new_memory,
        }


def generate_report_node(state: InterviewState) -> dict[str, Any]:
    """节点：生成反馈报告。"""
    candidate_name = state.get("resume_parsed", {}).get("name", "候选人")
    job_category = state["job_category"]

    report = _reporter.generate_report(
        candidate_name=candidate_name,
        job_category=job_category,
        evaluations=state.get("evaluations", []),
        conversation_history=state.get("conversation_history", []),
    )

    closing = (
        f"面试结束。综合评分 {report.get('overall_score', 'N/A')} 分，"
        f"评级 {report.get('overall_rating', 'N/A')}。请查看详细报告。"
    )

    history = list(state.get("conversation_history", []))
    history.append({"role": "interviewer", "content": closing})

    return {
        "final_report": report,
        "thinker_output": closing,
        "interview_phase": "finished",
        "is_finished": True,
        "needs_input": False,
        "conversation_history": history,
    }


def route_after_answer(state: InterviewState) -> str:
    phase = state.get("interview_phase", "")
    if phase == "generate_report":
        return "generate_report"
    elif phase == "waiting_answer":
        return "waiting_answer"
    else:
        return "ask_question"


def _format_conversation(messages: list[ConversationMessage], max_recent: int = 10) -> str:
    recent = messages[-max_recent:] if len(messages) > max_recent else messages
    lines = []
    for msg in recent:
        role = "面试官" if msg["role"] == "interviewer" else "候选人"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)
