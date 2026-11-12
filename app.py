"""智规通 v0.2｜免费模拟制度检索助手。

特性：中文自然语言聊天、对话续问、条款级规则检索、版本比对、材料清单。
不连接大语言模型、不调用任何外部 API，不提供真实银行业务决策。
仅需将 app.py 替换到现有 GitHub 仓库，保留 data/policies.json 与 requirements.txt。
"""
from __future__ import annotations

import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA_FILE = BASE / "data" / "policies.json"
APP_VERSION = "v0.2"
NOTICE = (
    "本系统仅用于银行 Agent 比赛演示。全部制度为虚构的模拟文件，"
    "不是任何银行或监管部门的正式要求。请勿输入真实客户资料、内部保密制度或其他敏感数据；"
    "实际业务必须以本行正式有效制度及有权人员审核为准。"
)

# “主题”决定检索哪份制度；不凭“客户”“材料”等过于泛化的词猜测业务。
TOPIC_ALIASES = {
    "CORP-LOAN-001": [
        "小微企业流动资金贷款", "小微企业贷款", "小微贷款", "流动资金贷款", "企业贷款",
        "对公贷款", "企业授信", "公司贷款", "小微企业", "企业融资", "流贷",
    ],
    "RETAIL-LOAN-002": [
        "个人消费贷款", "消费贷款", "个人贷款", "消费贷", "零售贷款", "个人借款", "个人信贷",
    ],
    "OPS-ACCOUNT-003": [
        "对公账户", "开立对公账户", "企业开户", "公司开户", "单位开户", "账户开立",
        "账户开户", "对公开户", "开立账户", "基本户", "开户", "对公结算账户",
    ],
    "OPS-KYC-004": [
        "客户身份识别", "强化尽职调查", "客户尽职调查", "尽职调查", "受益所有人",
        "实际控制人", "反洗钱", "身份识别", "客户身份", "kyc", "可疑交易",
    ],
    "CX-COMPLAINT-005": [
        "投诉处理", "客户投诉", "消费者权益", "投诉", "消保", "服务争议", "客户申诉",
    ],
}

# 用词方向决定哪些条款更相关；所有输出仍来自知识库原文。
INTENT_TERMS = {
    "版本对比": ["对比", "比较", "变化", "差异", "新旧", "修订", "版本", "改了"],
    "风险提示": ["风险", "异常", "违规", "合规", "疑点", "不一致", "虚假", "挪用", "识别风险"],
    "场景指导": ["怎么办", "怎么处理", "如何处理", "缺少", "缺失", "不足", "无法", "补充", "特殊情况", "如何办"],
    "材料清单": ["材料", "清单", "资料", "准备什么", "需要什么文件", "提供什么"],
    "办理流程": ["流程", "步骤", "如何办理", "怎么申请", "审批", "操作", "办理", "登记", "受理"],
}
INTENT_SECTION_TITLE = {
    "风险提示": ("风险", "异常", "强化", "升级", "核查", "尽职调查"),
    "场景指导": ("缺失", "异常", "处理", "流程", "材料", "调查", "审批"),
    "材料清单": ("材料", "资料", "清单"),
    "办理流程": ("流程", "审批", "办理", "调查", "受理", "处理"),
    "制度问答": (),
    "版本对比": (),
}
DOMAIN_NAMES = {
    "CORP-LOAN-001": "小微企业流动资金贷款",
    "RETAIL-LOAN-002": "个人消费贷款",
    "OPS-ACCOUNT-003": "对公账户开立",
    "OPS-KYC-004": "客户身份识别与尽职调查",
    "CX-COMPLAINT-005": "客户投诉处理",
}
SAMPLE_QUESTIONS = [
    "小微企业流动资金贷款需要哪些申请材料？",
    "客户开立对公账户时缺少一项证明材料，该怎么办？",
    "个人消费贷款的办理流程有哪些步骤？",
    "企业贷款用途与经营情况不一致，有哪些风险？",
    "客户投诉应该如何登记和处理？",
    "客户尽职调查发现受益所有人信息存在疑点怎么办？",
]


def load_policies(path: Path = DATA_FILE) -> list[dict]:
    """读取现有 v0.1 JSON；不联网、不上传数据。"""
    with path.open("r", encoding="utf-8") as fh:
        policies = json.load(fh)
    if not isinstance(policies, list) or not policies:
        raise ValueError("data/policies.json 必须是非空制度列表")
    for p in policies:
        for k in ("id", "title", "version", "domain", "sections"):
            if k not in p:
                raise ValueError(f"模拟制度缺少字段：{k}")
        for sec in p["sections"]:
            if not all(key in sec for key in ("id", "title", "content")):
                raise ValueError(f"{p['title']} 存在不完整条款")
    return policies


def normalize(s: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", str(s or "").lower(), flags=re.UNICODE)


def detect_topic(query: str, previous_topic: str | None = None) -> tuple[str | None, str]:
    """仅依据明确的业务领域表达判定主题；否则提示澄清。"""
    text = normalize(query)
    scored: list[tuple[float, str]] = []
    for policy_id, aliases in TOPIC_ALIASES.items():
        matches = [normalize(a) for a in aliases if normalize(a) in text]
        if not matches:
            continue
        # 最长匹配 + 少量额外证据，避免“客户”等泛词占优。
        longest = max(len(m) for m in matches)
        scored.append((longest * 2.3 + min(len(matches) - 1, 3) * 0.5, policy_id))
    if scored:
        scored.sort(reverse=True)
        # 遇到“对公账户 + 受益所有人”时，长业务名优先；不跨业务胡乱拼接。
        return scored[0][1], "明确业务关键词"
    followup_hints = ("那", "还", "这", "材料", "风险", "流程", "申请", "审批", "证件", "需要", "怎么办", "如果", "是否", "业务", "额度", "核查", "处理", "资料", "办理", "怎么")
    if previous_topic and previous_topic in TOPIC_ALIASES and any(hint in text for hint in followup_hints):
        return previous_topic, "沿用上一轮业务主题"
    return None, "需要补充业务主题"


def infer_intent(query: str) -> str:
    text = normalize(query)
    for label in ("版本对比", "风险提示", "场景指导", "材料清单", "办理流程"):
        if any(normalize(term) in text for term in INTENT_TERMS[label]):
            return label
    return "制度问答"


def active_policies(policies: list[dict]) -> list[dict]:
    """问答默认排除历史版本，避免 2025/2026 混用。"""
    return [p for p in policies if not str(p.get("status", "")).startswith("历史")]


def _bigrams(text: str) -> set[str]:
    text = normalize(text)
    return {text[i:i + 2] for i in range(len(text) - 1)}


def _section_score(query: str, section: dict, intent: str) -> float:
    title = normalize(section["title"])
    content = normalize(section["content"])
    q = normalize(query)
    # 字符二元组交集，可处理部分中文词组相似；并非语义模型。
    grams = _bigrams(q)
    section_grams = _bigrams(title + content)
    overlap = len(grams & section_grams)
    score = min(overlap * 0.32, 6.0)
    if title and title in q:
        score += 4
    # 显式问法优先对应条款名称，而非单纯按正文出现次数排序。
    for hint in INTENT_SECTION_TITLE.get(intent, ()):
        if normalize(hint) in title:
            score += 5
    # 用户明确提到的条款动作（例如“受理登记”）比泛化的“流程”更优先。
    for hint in ("登记", "受理", "核验", "审批", "材料", "缺失", "调查", "还款", "用途", "受益所有人", "处理", "归档", "升级"):
        if normalize(hint) in q and normalize(hint) in title:
            score += 5
    for hint in ("材料", "风险", "用途", "开户", "身份", "审批", "受益所有人", "还款", "投诉", "调查", "流程"):
        if normalize(hint) in q and (normalize(hint) in title or normalize(hint) in content):
            score += 1.2
    # “缺少材料怎么办”场景：优先材料缺失/异常处理条款。
    if intent == "场景指导" and any(x in q for x in ("缺", "不足", "无法")) and any(x in title for x in ("缺失", "异常", "处理")):
        score += 7
    # 回答时只能引用实存的条款。
    return round(score, 3)


def retrieve_sections(
    query: str,
    policies: list[dict],
    previous_topic: str | None = None,
    max_sections: int = 3,
) -> dict:
    """在最匹配的模拟制度中执行条款级排序，返回可核对的引用。"""
    topic, topic_reason = detect_topic(query, previous_topic)
    intent = infer_intent(query)
    if not topic:
        return {"topic": None, "intent": intent, "reason": topic_reason, "sources": [], "policy": None}
    eligible = [p for p in active_policies(policies) if p["id"] == topic]
    if not eligible:
        return {"topic": topic, "intent": intent, "reason": "当前没有对应的演示有效版本", "sources": [], "policy": None}
    # 如果数据源未来出现同一 ID 的多个有效版，按生效日期排序。
    policy = sorted(eligible, key=lambda p: str(p.get("effective_date", "")), reverse=True)[0]
    hits = []
    for sec in policy["sections"]:
        item = {
            "doc_id": policy["id"],
            "doc": policy["title"],
            "domain": policy["domain"],
            "version": policy["version"],
            "effective_date": policy.get("effective_date", "未标注"),
            "section_id": sec["id"],
            "title": sec["title"],
            "content": sec["content"],
            "score": _section_score(query, sec, intent),
        }
        hits.append(item)
    hits.sort(key=lambda s: (-s["score"], s["section_id"]))
    top = hits[:max_sections]
    return {"topic": topic, "intent": intent, "reason": topic_reason, "sources": top, "policy": policy}


def answer_question(query: str, policies: list[dict], previous_topic: str | None = None) -> dict:
    question = query.strip()
    if not question:
        return {"text": "请先输入一个制度问题。", "topic": previous_topic, "sources": [], "intent": "待输入"}
    found = retrieve_sections(question, policies, previous_topic)
    if not found["sources"]:
        return {
            "text": "目前无法从模拟制度库中确定你问的是哪类业务，因此不会编造制度要求。\n\n"
                    "请在问题中补充 **小微企业贷款 / 个人消费贷款 / 对公账户开户 / 客户身份识别 / 客户投诉** 等业务名称。",
            "topic": None,
            "sources": [],
            "intent": found["intent"],
        }
    topic = found["topic"]
    intent = found["intent"]
    sources = found["sources"]
    header = f"**匹配业务：{DOMAIN_NAMES.get(topic, '相关业务')}** · **分析类型：{intent}**"
    notes = [header, "", "以下内容摘自**模拟制度**，为便于演示按相关度排列，不构成真实银行办理依据：", ""]
    for index, source in enumerate(sources, 1):
        notes.append(f"**{index}. {source['title']}** 〔依据 {index}〕")
        notes.append(source["content"])
        notes.append("")
    if intent == "版本对比":
        notes.append("如需查看完整新旧变化，请打开左侧的 **制度版本对比** 功能（演示库目前仅为小微企业贷款设置了新旧版本）。")
    elif intent == "材料清单":
        notes.append("需要可勾选的材料表时，请打开左侧的 **材料清单** 功能。")
    if found["reason"] == "沿用上一轮业务主题":
        notes.append("_本轮已沿用上一轮的业务主题；如需切换业务，请在问题中明确写出业务名称。_")
    notes.append("**办理提示：** 如涉及材料豁免、例外事项、授信或账户审批，请依据本行正式制度转有权人员审核。")
    return {"text": "\n\n".join(notes), "topic": topic, "sources": sources, "intent": intent}


def list_versions(policies: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for p in policies:
        groups.setdefault(p["id"], []).append(p)
    return {pid: sorted(items, key=lambda p: str(p.get("effective_date", ""))) for pid, items in groups.items() if len(items) > 1}


def compare_versions(old: dict, new: dict) -> list[dict]:
    """根据条款 ID 对齐；显示原文，避免误称为 AI 语义修订分析。"""
    o = {sec["id"]: sec for sec in old["sections"]}
    n = {sec["id"]: sec for sec in new["sections"]}
    changes = []
    for sid in sorted(set(o) | set(n)):
        left = o.get(sid)
        right = n.get(sid)
        if left is None:
            status = "新增"
        elif right is None:
            status = "删除"
        elif (left["title"], left["content"]) == (right["title"], right["content"]):
            status = "未变化"
        else:
            status = "修改"
        changes.append({
            "section_id": sid,
            "title": (right or left)["title"],
            "status": status,
            "old_text": left["content"] if left else "（无该条款）",
            "new_text": right["content"] if right else "（无该条款）",
            "similarity": round(SequenceMatcher(None, left["content"] if left else "", right["content"] if right else "").ratio() * 100) if left and right else None,
        })
    return changes


def material_items(policy: dict) -> tuple[list[str], list[dict]]:
    """仅从已存在的材料条款中提取清单，不编造材料要求。"""
    material_sources = [s for s in policy["sections"] if any(term in s["title"] for term in ("申请材料", "材料清单", "资料清单", "开户材料"))]
    items = []
    for s in material_sources:
        # 示例制度中清单用分号分隔；过滤掉描述性引导语。
        content = re.sub(r"^.*?(?:包括|如下)[：:]", "", s["content"], count=1)
        for piece in re.split(r"[；;。]", content):
            item = piece.strip(" ：;。\n ")
            if 2 <= len(item) <= 110 and not item.startswith(("具体", "实际", "材料清单应", "发现")):
                items.append(item)
    # 保持原始顺序去重。
    return list(dict.fromkeys(items)), material_sources


def report_markdown(messages: list[dict]) -> str:
    lines = ["# 智规通 v0.2 演示会话记录", "", "声明：仅供模拟制度比赛演示，不可用于真实业务。", ""]
    for msg in messages:
        lines.extend(["## " + ("用户" if msg["role"] == "user" else "智规通"), "", msg["content"], ""])
        for i, source in enumerate(msg.get("sources", []), 1):
            lines.append(f"- 依据{i}：{source['doc']}（{source['version']}，{source['effective_date']}），第{source['section_id']}条《{source['title']}》")
        lines.append("")
    return "\n".join(lines)


def run_app() -> None:
    import streamlit as st

    st.set_page_config(page_title="智规通 v0.2｜银行智能制度助手", page_icon="🏦", layout="wide", initial_sidebar_state="expanded")
    st.markdown("""
    <style>
      .block-container {max-width:1140px; padding-top:1.3rem; padding-bottom:3rem}
      .hero {background:linear-gradient(120deg,#0c2941 0%,#165270 100%);padding:1.1rem 1.35rem;
          border-radius:16px;color:#f2f7fa;margin-bottom:.9rem}
      .hero .kicker {font-size:.76rem;letter-spacing:.11em;color:#afc9db}
      .hero h1 {color:#fff;margin:.2rem 0 .3rem;font-size:1.8rem}
      .hero p {margin:0;color:#d7e8f4;font-size:.97rem}
      .small-note {font-size:.85rem;color:#65758a}
      div[data-testid="stMetric"] {background:rgba(80,130,170,.06);padding:.65rem 1rem;border-radius:12px}
      div[data-testid="stChatMessage"] {border-radius:13px}
    </style>
    """, unsafe_allow_html=True)

    try:
        policies = load_policies()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        st.error(f"无法读取模拟制度知识库：{exc}")
        st.info("请确认 GitHub 仓库根目录有 data/policies.json；不要删除原来的 data 文件夹。")
        st.stop()

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "last_topic" not in st.session_state:
        st.session_state.last_topic = None
    if "nav_page" not in st.session_state:
        st.session_state.nav_page = "💬 智能问答"

    def ask(question: str) -> None:
        question = question.strip()[:1000]
        if not question:
            return
        previous = st.session_state.last_topic
        response = answer_question(question, policies, previous_topic=previous)
        st.session_state.chat_history.append({"role": "user", "content": question})
        st.session_state.chat_history.append({"role": "assistant", "content": response["text"], "sources": response["sources"], "intent": response["intent"], "topic": response["topic"]})
        if response["topic"]:
            st.session_state.last_topic = response["topic"]

    st.markdown("""
    <div class="hero">
      <div class="kicker">BANKING INTELLIGENCE ASSISTANT · DEMO v0.2</div>
      <h1>🏦 智规通</h1>
      <p>先找制度，再谈操作｜模拟制度智能检索 · 可追溯业务辅助</p>
    </div>
    """, unsafe_allow_html=True)
    st.warning(NOTICE, icon="⚠️")

    with st.sidebar:
        st.markdown("## 🏦 智规通")
        st.caption("模拟制度知识库 · 免费规则检索版 v0.2")
        pages = ["💬 智能问答", "📋 材料清单", "🔁 制度版本对比", "📚 制度库浏览", "ℹ️ 使用说明"]
        page = st.radio("功能导航", pages, key="nav_page")
        st.divider()
        st.caption("演示数据")
        st.write(f"📚 {len(policies)} 份模拟制度版本")
        st.write("🏷️ 对公 / 零售 / 运营 / 客服")
        st.write("🧮 本地规则检索：无大模型 API 费用")
        if st.session_state.chat_history:
            st.download_button("⬇️ 导出对话记录", report_markdown(st.session_state.chat_history).encode("utf-8"), file_name="智规通演示会话.md", mime="text/markdown", use_container_width=True)
            if st.button("🗑️ 清空聊天记录", use_container_width=True):
                st.session_state.chat_history = []
                st.session_state.last_topic = None
                st.rerun()

    if page == "💬 智能问答":
        st.subheader("智能制度问答")
        st.caption("直接在页面下方输入问题，也可以点击示例；支持继续追问，如“那风险有哪些？”")
        if not st.session_state.chat_history:
            st.info("这是真正可输入的聊天界面。当前回答来自模拟制度条款排序，不使用大模型。")
            st.markdown("**试试这些问题**")
            for row_start in range(0, len(SAMPLE_QUESTIONS), 2):
                cols = st.columns(2)
                for j, question in enumerate(SAMPLE_QUESTIONS[row_start:row_start + 2]):
                    with cols[j]:
                        if st.button(question, key=f"sample_{row_start}_{j}", use_container_width=True):
                            ask(question)
                            st.rerun()
        for entry in st.session_state.chat_history:
            with st.chat_message(entry["role"]):
                st.markdown(entry["content"])
                sources = entry.get("sources", [])
                if sources:
                    with st.expander(f"📑 查看引用原文 · {len(sources)} 条"):
                        for i, src in enumerate(sources, 1):
                            st.markdown(f"**依据 {i}｜{src['doc']} · {src['version']} · 第 {src['section_id']} 条《{src['title']}》**")
                            st.caption(f"文件编号：{src['doc_id']}｜演示生效日期：{src['effective_date']}")
                            st.write(src["content"])
                            if i != len(sources):
                                st.divider()
        question = st.chat_input("例如：对公账户开户材料缺失该怎么处理？（请勿输入真实客户资料）", max_chars=1000)
        if question:
            ask(question)
            st.rerun()

    elif page == "📋 材料清单":
        st.subheader("材料清单生成器")
        st.caption("条目仅从模拟制度材料条款提取；清单可逐项勾选、下载。")
        candidates = []
        for p in active_policies(policies):
            if any("材料" in sec["title"] for sec in p["sections"]):
                candidates.append(p)
        chosen = st.selectbox("业务类型", candidates, format_func=lambda p: DOMAIN_NAMES.get(p["id"], p["title"]))
        items, secs = material_items(chosen)
        st.markdown(f"**制度依据：** {chosen['title']} · {chosen['version']}")
        if items:
            marked = []
            for idx, item in enumerate(items):
                if st.checkbox(item, key=f"check_{chosen['id']}_{idx}"):
                    marked.append(item)
            st.progress(len(marked) / len(items), text=f"已核对 {len(marked)} / {len(items)} 项")
            export = "# 智规通模拟材料清单\n\n" + f"业务：{DOMAIN_NAMES.get(chosen['id'], chosen['title'])}\n制度：{chosen['title']}（{chosen['version']}）\n\n"
            export += "\n".join(f"- [{'x' if x in marked else ' '}] {x}" for x in items)
            export += "\n\n注意：这是一份虚构模拟材料清单，不可用于真实业务。"
            st.download_button("⬇️ 下载清单（Markdown）", export.encode("utf-8"), file_name="模拟材料清单.md", mime="text/markdown")
        else:
            st.info("所选模拟制度中未发现可直接列举的材料条款，请以正式制度为准。")
        with st.expander("查看材料来源原文"):
            for sec in secs:
                st.markdown(f"**第 {sec['id']} 条｜{sec['title']}**")
                st.write(sec["content"])

    elif page == "🔁 制度版本对比":
        st.subheader("新旧制度版本对比")
        st.caption("按条款编号对齐，列出新增 / 删除 / 修改 / 未变化（当前仅有一组模拟制度设有新旧版）。")
        groups = list_versions(policies)
        if not groups:
            st.info("模拟数据里暂无可比较的制度版本。")
        else:
            pid = st.selectbox("选择制度", list(groups), format_func=lambda x: DOMAIN_NAMES.get(x, x))
            variants = groups[pid]
            old, new = variants[0], variants[-1]
            a, b = st.columns(2)
            a.info(f"旧版：{old['version']}（{old.get('effective_date', '未标注')}）")
            b.success(f"新版：{new['version']}（{new.get('effective_date', '未标注')}）")
            diffs = compare_versions(old, new)
            counts = Counter(item["status"] for item in diffs)
            st.write(" · ".join(f"{label} {counts.get(label, 0)} 条" for label in ("新增", "删除", "修改", "未变化")))
            for change in diffs:
                if change["status"] == "未变化":
                    continue
                with st.expander(f"{change['status']}｜第 {change['section_id']} 条 {change['title']}", expanded=True):
                    col_old, col_new = st.columns(2)
                    col_old.markdown("**旧版原文**")
                    col_old.write(change["old_text"])
                    col_new.markdown("**新版原文**")
                    col_new.write(change["new_text"])
            st.caption("本页比较的是虚构条款文本，不代表真实政策修订；相似度仅作文字比较，不等于风险影响程度。")

    elif page == "📚 制度库浏览":
        st.subheader("模拟制度知识库")
        domains = ["全部"] + sorted({p["domain"] for p in policies})
        selected_domain = st.selectbox("筛选业务领域", domains)
        items = [p for p in policies if selected_domain == "全部" or p["domain"] == selected_domain]
        st.caption(f"共 {len(items)} 份模拟制度版本；历史版本不参与默认智能问答。")
        for policy in items:
            with st.expander(f"{policy['title']} · {policy['version']} · {policy['domain']}"):
                st.caption(f"文件编号：{policy['id']}｜演示生效日期：{policy.get('effective_date', '未标注')}｜状态：{policy.get('status', '未标注')}")
                for section in policy["sections"]:
                    st.markdown(f"**第 {section['id']} 条 {section['title']}**")
                    st.write(section["content"])

    else:
        st.subheader("关于智规通 v0.2")
        st.markdown("""
        **这是零模型 API 费用的演示版，不是假装已经调用大模型的产品。**

        - **问答方式**：直接键入业务问题，匹配五类模拟银行制度；还可以连续追问上一轮业务。
        - **检索方式**：明确业务主题 + 条款标题优先级 + 中文字符片段重合；不使用向量数据库或模型推理。
        - **证据机制**：显示制度标题、版本、生效日期和条款原文；不确定业务时要求补充，而非编造。
        - **文件范围**：使用仓库原有 `data/policies.json`，不上传真实制度，也不请求外部 API。
        - **准确性边界**：检索不是语义理解，可能漏掉同义词、否定或复杂交叉制度关系。需要真实金融决策时必须转人工。
        - **后续升级**：若比赛明确要求 LLM Agent，可再接入银行批准的模型和检索工具，**不能**把本版本称为已实现真实大模型 Agent。
        """)
        st.code("streamlit run app.py", language="bash")

    st.divider()
    st.caption("智规通 v0.2 · 免费规则检索演示 · 虚构模拟制度 · 无外部模型 API · 不构成金融、法律或合规建议")


if __name__ == "__main__":
    run_app()
