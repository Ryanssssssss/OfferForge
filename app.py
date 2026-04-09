"""面霸 —— AI 简历面试教练 Streamlit 主入口。

支持：文本 + 语音双模式 | 多对话管理 | 历史记录持久化 | 自动清理
"""

import os
import sys
import uuid
import base64
import logging
from pathlib import Path
from datetime import datetime

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from interfaces.voice_interface import VoiceInterviewInterface
from core.session_manager import (
    save_session, load_session, list_sessions, delete_session, cleanup_expired,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logging.getLogger("websocket").setLevel(logging.CRITICAL)
logger = logging.getLogger(__name__)

# 启动时自动清理过期数据
cleanup_expired()

st.set_page_config(page_title="面霸 - AI面试教练", page_icon="🎯", layout="wide", initial_sidebar_state="expanded")

# ── Apple Design 样式 ──
st.markdown("""
<style>
    .stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"], button[kind="primary"] {
        background: #007AFF !important; color: white !important; border: none !important;
        border-radius: 12px !important; padding: 10px 24px !important; font-size: 16px !important;
        font-weight: 500 !important; box-shadow: 0 2px 8px rgba(0,122,255,0.3) !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button[kind="primary"]:hover, button[kind="primary"]:hover {
        background: #0056CC !important; box-shadow: 0 4px 12px rgba(0,122,255,0.4) !important;
    }
    .stButton > button { border-radius: 10px !important; border: 1px solid #E5E5EA !important; font-weight: 500 !important; }
    .stFormSubmitButton > button { background: #007AFF !important; color: white !important; border: none !important; border-radius: 10px !important; }
    .stFormSubmitButton > button:hover { background: #0056CC !important; }
    .score-card { background: linear-gradient(135deg, #007AFF 0%, #5856D6 100%); padding: 20px; border-radius: 16px; color: white; text-align: center; margin: 8px 0; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    .score-card h2 { margin: 0; font-size: 2.5em; }
    .score-card p { margin: 4px 0 0 0; opacity: 0.9; }
    .voice-status { padding: 8px 16px; border-radius: 10px; margin: 8px 0; font-size: 0.9em; text-align: center; }
    .voice-on { background: #E8F5E9; color: #2E7D32; }
    .voice-off { background: #F3F4F6; color: #6B7280; }
    .session-card { padding: 8px 12px; border: 1px solid #E5E5EA; border-radius: 8px; margin: 4px 0; font-size: 0.85em; }
</style>
""", unsafe_allow_html=True)


def play_audio(audio_bytes: bytes):
    if audio_bytes:
        b64_audio = base64.b64encode(audio_bytes).decode()
        st.markdown(f'<audio autoplay><source src="data:audio/wav;base64,{b64_audio}" type="audio/wav"></audio>', unsafe_allow_html=True)


# ── Session State ──
def init_session_state():
    if "interface" not in st.session_state:
        st.session_state.interface = VoiceInterviewInterface()
    for key, default in {
        "session_id": str(uuid.uuid4())[:8],
        "messages": [],
        "phase": "upload",
        "report": None,
        "voice_mode": False,
        "pending_audio": None,
        "input_key": 0,
    }.items():
        if key not in st.session_state:
            st.session_state[key] = default

init_session_state()
interface: VoiceInterviewInterface = st.session_state.interface


def _save_current_session():
    """保存当前会话状态。"""
    candidate_name = ""
    if hasattr(interface, 'text_interface'):
        state = interface.text_interface._agent.state
        candidate_name = state.get("resume_parsed", {}).get("name", "")

    save_session(st.session_state.session_id, {
        "messages": st.session_state.messages,
        "phase": st.session_state.phase,
        "report": st.session_state.report,
        "candidate_name": candidate_name,
        "job_category": interface.text_interface._agent.state.get("job_category", "") if hasattr(interface, 'text_interface') else "",
    })


def _start_new_session():
    """开始新会话。"""
    if st.session_state.messages:
        _save_current_session()
    interface.reset()
    st.session_state.messages = []
    st.session_state.phase = "upload"
    st.session_state.report = None
    st.session_state.pending_audio = None
    st.session_state.input_key = 0
    st.session_state.session_id = str(uuid.uuid4())[:8]


def _load_saved_session(session_id: str):
    """加载已保存的会话（只恢复消息和报告，不恢复 Agent 状态）。"""
    data = load_session(session_id)
    if not data:
        return
    st.session_state.messages = data.get("messages", [])
    st.session_state.report = data.get("report")
    st.session_state.phase = "report" if data.get("report") else "upload"
    st.session_state.session_id = session_id


# ── 侧边栏 ──
with st.sidebar:
    st.title("🎯 面霸")
    st.caption("AI 简历面试教练")
    st.divider()

    # 语音模式
    voice_available = interface.voice_available
    if voice_available:
        st.session_state.voice_mode = st.toggle("🎤 语音面试模式", value=st.session_state.voice_mode)
        if st.session_state.voice_mode:
            st.markdown('<div class="voice-status voice-on">🎤 语音模式已开启</div>', unsafe_allow_html=True)
            # 语速滑块（值自动存在 st.session_state.voice_speed）
            st.slider("语速", min_value=0.75, max_value=2.0, value=1.25, step=0.25, key="voice_speed")
        else:
            st.markdown('<div class="voice-status voice-off">⌨️ 文本模式</div>', unsafe_allow_html=True)
    else:
        st.info("💡 配置 VOICE_API_KEY 可开启语音")
        st.session_state.voice_mode = False

    st.divider()

    # 面试进度
    phase = st.session_state.phase
    phase_labels = {"upload": "📄 上传简历", "job_select": "🎯 选择岗位", "interview": "💬 模拟面试", "report": "📊 反馈报告"}
    st.subheader("面试进度")
    for key, label in phase_labels.items():
        if key == phase:
            st.markdown(f"**▶ {label}**")
        elif list(phase_labels.keys()).index(key) < list(phase_labels.keys()).index(phase):
            st.markdown(f"✅ {label}")
        else:
            st.markdown(f"⬜ {label}")

    if phase == "interview":
        progress = interface.get_current_progress()
        total = progress.get("total_questions", 0)
        current = progress.get("current_question", 0)
        if total > 0:
            st.divider()
            st.progress(current / total, text=f"题目进度: {current}/{total}")

    st.divider()

    # 新建面试 / 重新开始
    col_new, col_reset = st.columns(2)
    with col_new:
        if st.button("➕ 新面试", use_container_width=True):
            _start_new_session()
            st.rerun()
    with col_reset:
        if st.button("🔄 重来", use_container_width=True):
            interface.reset()
            st.session_state.messages = []
            st.session_state.phase = "upload"
            st.session_state.report = None
            st.session_state.pending_audio = None
            st.session_state.input_key = 0
            st.rerun()

    # 历史会话
    saved = list_sessions()
    if saved:
        with st.expander(f"📚 历史面试（{len(saved)}）"):
            for s in saved[:10]:
                ts = datetime.fromtimestamp(s["saved_at"]).strftime("%m/%d %H:%M") if s["saved_at"] else "?"
                name = s.get("candidate_name", "?")
                job = s.get("job_category", "")
                status = "✅" if s.get("has_report") else "⏸️"
                col_info, col_del = st.columns([4, 1])
                with col_info:
                    if st.button(f"{status} {name} {job} ({ts})", key=f"load_{s['session_id']}", use_container_width=True):
                        _load_saved_session(s["session_id"])
                        st.rerun()
                with col_del:
                    if st.button("🗑", key=f"del_{s['session_id']}"):
                        delete_session(s["session_id"])
                        st.rerun()

    # 配置 —— LLM Provider 选择
    with st.expander("⚙️ AI 模型配置"):
        from core.llm.providers import PROVIDERS, get_provider

        provider_options = {k: v.name for k, v in PROVIDERS.items()}
        current_provider = settings.llm_provider

        selected_provider = st.selectbox(
            "选择 AI 提供商",
            options=list(provider_options.keys()),
            format_func=lambda x: provider_options[x],
            index=list(provider_options.keys()).index(current_provider) if current_provider in provider_options else 0,
        )

        if selected_provider != settings.llm_provider:
            settings.llm_provider = selected_provider

        provider = get_provider(selected_provider)

        # Provider 对应的 API Key
        key_attr = f"{selected_provider}_api_key"
        current_key = getattr(settings, key_attr, "")
        new_key = st.text_input(
            f"{provider.name} API Key",
            value=current_key,
            type="password",
            key=f"key_{selected_provider}",
        )
        if new_key and new_key != current_key:
            setattr(settings, key_attr, new_key)
            st.success("API Key 已更新")

        # 模型选择
        if selected_provider == "custom":
            custom_url = st.text_input("Base URL", value=settings.custom_base_url)
            if custom_url != settings.custom_base_url:
                settings.custom_base_url = custom_url
            custom_model = st.text_input("模型名称", value=settings.custom_model_name)
            if custom_model != settings.custom_model_name:
                settings.custom_model_name = custom_model
        elif provider.models:
            current_model = settings.llm_model_name or provider.default_model
            model = st.selectbox(
                "模型",
                options=provider.models,
                index=provider.models.index(current_model) if current_model in provider.models else 0,
                key=f"model_{selected_provider}",
            )
            if model != settings.llm_model_name:
                settings.llm_model_name = model

        st.divider()
        voice_key = st.text_input("语音 API Key (DashScope)", value=settings.voice_api_key or "", type="password")
        if voice_key and voice_key != settings.voice_api_key:
            settings.voice_api_key = voice_key
            st.success("语音 Key 已更新")


# ── 主区域 ──
st.title("🎯 面霸 — AI 简历面试教练")

if st.session_state.pending_audio:
    play_audio(st.session_state.pending_audio)
    st.session_state.pending_audio = None

# ── 阶段1: 上传简历 ──
if st.session_state.phase == "upload":
    st.markdown("### 📄 第一步：上传您的简历")
    st.info("请上传 PDF 格式的简历，AI 将解析您的关键信息并生成个性化面试题。")
    uploaded_file = st.file_uploader("选择 PDF 简历文件", type=["pdf"])

    if uploaded_file is not None:
        if st.button("开始解析", type="primary", use_container_width=True):
            settings.ensure_dirs()
            save_path = Path(settings.upload_dir) / f"{st.session_state.session_id}_{uploaded_file.name}"
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            with st.spinner("正在解析简历..."):
                try:
                    text, audio = interface.start_interview(str(save_path), st.session_state.session_id)
                    st.session_state.messages.append({"role": "assistant", "content": text})
                    if audio and st.session_state.voice_mode:
                        st.session_state.pending_audio = audio
                    st.session_state.phase = "job_select"
                    st.rerun()
                except Exception as e:
                    st.error(f"简历解析失败: {e}")

# ── 阶段2: 选择岗位 ──
elif st.session_state.phase == "job_select":
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    st.markdown("### 🎯 第二步：选择目标岗位")
    col1, col2 = st.columns([3, 1])
    with col1:
        job = st.selectbox("选择岗位", options=settings.job_categories, index=0)
        include_coding = st.checkbox("包含 LeetCode 代码题", value=(job != "简历深度拷打（不限岗位）"))
    with col2:
        st.write(""); st.write("")
        if st.button("开始面试", type="primary"):
            # 记录是否要代码题
            st.session_state.include_coding = include_coding
            with st.spinner(f"正在生成{job}面试题..."):
                try:
                    text, audio = interface.select_job(job, include_coding=include_coding)
                    st.session_state.messages.append({"role": "user", "content": f"我选择面试 **{job}** 岗位"})
                    st.session_state.messages.append({"role": "assistant", "content": text})
                    if audio and st.session_state.voice_mode:
                        st.session_state.pending_audio = audio
                    st.session_state.phase = "interview"
                    st.rerun()
                except Exception as e:
                    st.error(f"生成面试题失败: {e}")

# ── 阶段3: 模拟面试 ──
elif st.session_state.phase == "interview":
    import streamlit.components.v1 as components
    from core.leetcode_manager import get_problem_by_id
    from core.code_runner import verify_solution

    if interface.is_finished:
        _save_current_session()
        st.session_state.report = interface.get_report()
        st.session_state.phase = "report"
        st.rerun()

    # 检测当前是否是算法题（最后一题含 leetcode_id）
    agent_state = interface.text_interface._agent.state
    questions = agent_state.get("questions", [])
    current_idx = agent_state.get("current_question_idx", 0)
    current_q = questions[current_idx] if current_idx < len(questions) else {}
    is_coding = bool(current_q.get("leetcode_id"))

    # ── 算法题代码模式 ──
    if is_coding and agent_state.get("interview_phase") == "waiting_answer":
        lc_id = current_q["leetcode_id"]
        problem = get_problem_by_id(lc_id)

        title = problem.get("title", "") if problem else ""
        st.markdown(f"### 💻 算法题：{lc_id}. {title}")

        if problem and problem.get("description"):
            col_desc, col_code = st.columns([1, 1])

            with col_desc:
                st.markdown("#### 📋 题目描述")
                st.markdown(problem["description"][:4000], unsafe_allow_html=True)
                if problem.get("slug"):
                    st.markdown(f"[🔗 在 LeetCode 上查看](https://leetcode.cn/problems/{problem['slug']}/)")

            with col_code:
                st.markdown("#### ✏️ 编写代码")

                # 代码编辑器
                default_code = problem.get("code_template", "class Solution:\n    pass")
                if "user_code" not in st.session_state:
                    st.session_state.user_code = default_code

                user_code = st.text_area(
                    "代码",
                    value=st.session_state.user_code,
                    height=350,
                    key="code_editor",
                    label_visibility="collapsed",
                )
                st.session_state.user_code = user_code

                col_run, col_done = st.columns(2)

                with col_run:
                    if st.button("▶️ 运行样例", type="primary", use_container_width=True):
                        with st.spinner("运行中..."):
                            result = verify_solution(user_code, problem)
                            if result["success"]:
                                st.success(f"✅ 样例通过 {result['passed']}/{result['total']}")
                            else:
                                st.error(f"❌ {result['passed']}/{result['total']} 通过")
                            if result["output"]:
                                st.code(result["output"], language="text")
                            if result["error"]:
                                st.code(result["error"], language="text")

                with col_done:
                    if st.button("📤 提交并继续", use_container_width=True):
                        # 先跑一遍样例
                        test_result = verify_solution(user_code, problem)
                        test_note = f"样例测试：{test_result['passed']}/{test_result['total']} 通过" if test_result["total"] > 0 else ""

                        answer = f"我的解法：\n```python\n{user_code}\n```\n{test_note}"
                        st.session_state.messages.append({"role": "user", "content": answer})
                        with st.spinner("面试官评估中..."):
                            try:
                                response, audio_out = interface.process_text_input(answer)
                                st.session_state.messages.append({"role": "assistant", "content": response})
                                if audio_out:
                                    st.session_state.pending_audio = audio_out
                                if "user_code" in st.session_state:
                                    del st.session_state["user_code"]
                                st.rerun()
                            except Exception as e:
                                st.error(f"出错: {e}")

                st.caption(f"💡 本地仅跑样例（{len(problem.get('test_cases', []))} 个），完整测试请到 LeetCode 提交")

        else:
            # 没有完整题面，退回口述模式
            st.warning(f"未找到 LeetCode #{lc_id} 的完整题面，请口述解题思路。")
            is_coding = False

    # ── 普通面试模式（非算法题 or 口述） ──
    if not is_coding or agent_state.get("interview_phase") != "waiting_answer":
        latest_interviewer = ""
        history_msgs = []
        latest_user = ""
        for msg in st.session_state.messages:
            if msg["role"] == "assistant":
                if latest_interviewer:
                    history_msgs.append({"role": "assistant", "content": latest_interviewer})
                if latest_user:
                    history_msgs.append({"role": "user", "content": latest_user})
                    latest_user = ""
                latest_interviewer = msg["content"]
            else:
                if latest_user:
                    history_msgs.append({"role": "user", "content": latest_user})
                latest_user = msg["content"]
        if latest_user:
            history_msgs.append({"role": "user", "content": latest_user})

        if st.session_state.voice_mode:
            col_cam, col_q = st.columns([1, 2])
            with col_cam:
                components.html("""
                <div style="display:flex;justify-content:center;">
                    <video id="webcam" autoplay playsinline muted style="width:100%;max-width:400px;aspect-ratio:4/3;border-radius:12px;border:2px solid #007AFF;background:#000;"></video>
                </div>
                <script>
                    const v=document.getElementById('webcam');
                    navigator.mediaDevices.getUserMedia({video:true,audio:false}).then(s=>{v.srcObject=s}).catch(e=>{});
                </script>
                """, height=320)
            with col_q:
                st.markdown("### 🎙️ 面试官提问")
                st.info(latest_interviewer or "等待提问...")
        else:
            st.markdown("### 🎙️ 面试官提问")
            st.info(latest_interviewer or "等待提问...")

        if history_msgs:
            with st.expander(f"📜 历史对话（{len(history_msgs)} 条）", expanded=False):
                for msg in history_msgs:
                    role = "🤖 面试官" if msg["role"] == "assistant" else "👤 候选人"
                    st.markdown(f"**{role}**: {msg['content']}")
                    st.markdown("---")

        st.markdown("---")

        if st.session_state.voice_mode:
            ik = st.session_state.input_key
            col_mic, col_text = st.columns([1, 1])
            with col_mic:
                st.markdown("#### 🎤 语音回答")
                audio_input = st.audio_input("录音", key=f"voice_{ik}")
            with col_text:
                st.markdown("#### ⌨️ 或文字回答")
                with st.form(key=f"form_{ik}", clear_on_submit=True):
                    text_answer = st.text_area("输入回答", height=100)
                    submitted = st.form_submit_button("📤 提交")

            if submitted and text_answer:
                st.session_state.messages.append({"role": "user", "content": text_answer})
                with st.spinner("面试官思考中..."):
                    try:
                        response, audio_out = interface.process_text_input(text_answer)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                        if audio_out: st.session_state.pending_audio = audio_out
                        st.session_state.input_key += 1
                        st.rerun()
                    except Exception as e:
                        st.error(f"出错: {e}")

            if audio_input is not None:
                pk = f"pv_{ik}"
                if pk not in st.session_state:
                    audio_bytes = audio_input.read()
                    if audio_bytes:
                        st.session_state[pk] = True
                    with st.spinner("语音识别中..."):
                        try:
                            user_text, response, audio_out = interface.process_voice_input(audio_bytes)
                            if user_text: st.session_state.messages.append({"role": "user", "content": f"🎤 {user_text}"})
                            st.session_state.messages.append({"role": "assistant", "content": response})
                            if audio_out: st.session_state.pending_audio = audio_out
                            st.session_state.input_key += 1
                            st.rerun()
                        except Exception as e:
                            st.error(f"语音出错: {e}")

        else:
            if prompt := st.chat_input("输入您的回答..."):
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.spinner("面试官思考中..."):
                    try:
                        response, _ = interface.process_text_input(prompt)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                    except Exception as e:
                        st.error(f"出错: {e}")
                st.rerun()

# ── 阶段4: 反馈报告 ──
elif st.session_state.phase == "report":
    _save_current_session()
    report = st.session_state.report
    if not report:
        st.warning("暂无报告")
    else:
        st.markdown("### 📊 面试反馈报告")
        st.divider()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f'<div class="score-card"><h2>{report.get("overall_score", "N/A")}</h2><p>综合评分</p></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="score-card"><h2>{report.get("overall_rating", "N/A")}</h2><p>评级</p></div>', unsafe_allow_html=True)
        with col3:
            history = interface.get_conversation_history()
            st.markdown(f'<div class="score-card"><h2>{len([q for q in history if q.get("role") == "candidate"])}</h2><p>回答次数</p></div>', unsafe_allow_html=True)

        st.divider()

        dim_scores = report.get("dimension_scores", {})
        if dim_scores:
            st.subheader("📈 各维度评分")
            cols = st.columns(len(dim_scores))
            dim_names = {"professional_ability": "专业能力", "communication": "沟通表达", "logical_thinking": "逻辑思维", "stress_handling": "抗压应变", "star_structure": "STAR结构"}
            for col, (k, v) in zip(cols, dim_scores.items()):
                with col:
                    score = v.get("score", 0) if isinstance(v, dict) else v
                    st.metric(label=dim_names.get(k, k), value=f"{score}")
                    if isinstance(v, dict) and v.get("comment"):
                        st.caption(v["comment"])

        st.divider()

        for s in report.get("top_strengths", []):
            st.success(f"✅ {s}")

        for imp in report.get("key_improvements", []):
            if isinstance(imp, dict):
                with st.expander(f"🔧 {imp.get('area', '')}"):
                    st.write(f"**建议**: {imp.get('suggestion', '')}")
                    if imp.get("example"): st.info(f"💡 {imp['example']}")
            else:
                st.warning(f"🔧 {imp}")

        feedback = report.get("overall_feedback", "")
        if feedback:
            st.subheader("💬 综合评语")
            st.info(feedback)

        tips = report.get("preparation_tips", [])
        if tips:
            st.subheader("📚 备面建议")
            for i, tip in enumerate(tips, 1):
                st.write(f"{i}. {tip}")

        st.divider()
        with st.expander("📜 完整对话记录"):
            for msg in st.session_state.messages:
                role = "🤖 面试官" if msg["role"] == "assistant" else "👤 候选人"
                st.markdown(f"**{role}**: {msg['content']}")
                st.write("---")
