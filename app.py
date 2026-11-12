import json
import re
from pathlib import Path
from datetime import datetime
import streamlit as st

BASE = Path(__file__).parent
POLICY_FILE = BASE / "data" / "policies.json"

st.set_page_config(page_title="智规通 | 银行智能知识与制度 Agent", page_icon="🏦", layout="wide")

with open(POLICY_FILE, "r", encoding="utf-8") as f:
    POLICIES = json.load(f)

DISCLAIMER = "本产品为比赛演示原型，知识库内容均为模拟制度，不代表任何真实银行制度、监管要求或业务授权。真实业务须以本行正式有效制度、系统校验及有权审批为准。"

st.markdown("""
<style>
.block-container {padding-top: 1.4rem; padding-bottom: 2.5rem; max-width: 1220px;}
.hero {padding: 1.35rem 1.5rem; border-radius: 18px; background: linear-gradient(120deg,#102f4a,#1d5576); color: white; margin-bottom: 1rem;}
.hero h1 {color:white; margin:0 0 .35rem 0; font-size:2rem;}
.hero p {color:#d8e8f3; margin:0;}
.metric-card {border:1px solid rgba(120,140,160,.25); padding:1rem; border-radius:14px; min-height:105px;}
.small-muted {color:#6b7280; font-size:.86rem;}
.source-card {border-left:4px solid #2684c7; padding:.6rem .85rem; background:rgba(38,132,199,.06); border-radius:6px; margin:.4rem 0;}
div[data-testid="stMetric"] {background:rgba(100,120,140,.06); padding:12px; border-radius:12px;}
</style>
""", unsafe_allow_html=True)

def norm(s):
    return re.sub(r"\s+", "", str(s or "")).lower()

def infer_intent(q):
    qn = norm(q)
    if any(x in qn for x in ["对比", "比较", "变化", "差异", "新旧", "版本"]):
        return "制度对比"
    if any(x in qn for x in ["清单", "材料", "资料", "准备什么", "需要什么文件"]):
        return "材料清单"
    if any(x in qn for x in ["风险", "违规", "合规", "异常", "隐患"]):
        return "合规风险分析"
    if any(x in qn for x in ["怎么办", "如何办理", "流程", "处理", "场景", "帮我分析", "指导"]):
        return "业务场景指导"
    return "智能制度问答"

def score_policy(query, policy):
    q = norm(query)
    score = 0
    for kw in policy.get("keywords", []):
        if norm(kw) and norm(kw) in q:
            score += 3 + min(len(kw), 4)
    for sec in policy.get("sections", []):
        text = norm(sec["title"] + sec["content"])
        for token in ["材料", "审批", "风险", "流程", "身份", "用途", "调查", "投诉", "账户", "还款"]:
            if token in q and token in text:
                score += 1
    return score

def retrieve(query, top_k=4, include_history=False):
    scored = []
    for p in POLICIES:
        if not include_history and p.get("status", "").startswith("历史"):
            continue
        s = score_policy(query, p)
        if s > 0:
            scored.append((s, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:top_k]]

def sources_for(policies):
    rows = []
    for p in policies:
        for sec in p["sections"]:
            rows.append({
                "doc": p["title"], "id": p["id"], "version": p["version"],
                "effective": p["effective_date"], "section": sec["id"],
                "section_title": sec["title"], "content": sec["content"]
            })
    return rows

def build_answer(query, mode="auto"):
    intent = infer_intent(query) if mode == "auto" else mode
    found = retrieve(query)
    if not found:
        return {
            "intent": intent,
            "answer": "当前模拟知识库未检索到足够相关的制度依据。建议补充业务类型、产品名称或具体问题，并向制度归口部门核实。为避免误导，本 Agent 不会在缺乏依据时编造制度要求。",
            "sources": []
        }
    sections = sources_for(found)
    if intent == "材料清单":
        chosen = [s for s in sections if "材料" in s["section_title"] or "申请材料" in s["section_title"]]
        if not chosen:
            chosen = sections[:3]
        lines = ["根据检索到的模拟制度，建议先按以下清单核对："]
        for s in chosen[:4]:
            lines.append(f"- {s['content']}")
        lines.append("提示：清单为演示参考，实际材料要求需结合客户类型、产品细则和正式制度确认。")
        answer = "\n\n".join(lines)
    elif intent == "合规风险分析":
        chosen = [s for s in sections if "风险" in s["section_title"] or "异常" in s["section_title"] or "升级" in s["section_title"]]
        if not chosen:
            chosen = sections[:3]
        answer = "我按“风险信号—核查动作—升级要求”整理如下：\n\n"
        for s in chosen[:4]:
            answer += f"**{s['section_title']}**：{s['content']}\n\n"
        answer += "请注意：本工具只提供风险提示，不作合规结论、授信决定或业务放行决定。"
    elif intent == "业务场景指导":
        answer = "我将任务拆解为“业务识别—制度核对—办理步骤—风险检查”四步：\n\n"
        for i, s in enumerate(sections[:5], 1):
            answer += f"**{i}. {s['section_title']}（{s['doc']} · 第{s['section']}条）**\n{s['content']}\n\n"
        answer += "如涉及材料豁免、例外处理、审批权限或客户权益，应暂停自动判断并转有权人员确认。"
    elif intent == "制度对比":
        answer = "已识别为制度版本对比需求。请进入左侧“制度版本对比”模块选择具体制度，系统会按条款输出差异。当前检索到的相关制度如下：\n\n"
        for p in found:
            answer += f"- {p['title']}（{p['version']}，{p['effective_date']}）\n"
    else:
        answer = "根据当前模拟知识库检索结果，整理如下：\n\n"
        for s in sections[:5]:
            answer += f"**{s['doc']} · {s['version']} · 第{s['section']}条：{s['section_title']}**\n{s['content']}\n\n"
        answer += "如需办理具体业务，建议补充客户类型、产品、业务阶段和具体疑点，以便进一步定位适用条款。"
    return {"intent": intent, "answer": answer, "sources": sections[:8]}

COMPARE = {
    "小微企业流动资金贷款管理办法": {
        "old": next(p for p in POLICIES if p["id"]=="CORP-LOAN-001" and p["version"]=="2025版"),
        "new": next(p for p in POLICIES if p["id"]=="CORP-LOAN-001" and p["version"]=="2026版")
    }
}

def compare_versions(name):
    pair = COMPARE[name]
    old = {s["id"]: s for s in pair["old"]["sections"]}
    new = {s["id"]: s for s in pair["new"]["sections"]}
    diffs = []
    for sid in sorted(set(old) | set(new)):
        a, b = old.get(sid), new.get(sid)
        if a and b and a["content"] != b["content"]:
            diffs.append((sid, a["title"], a["content"], b["content"]))
        elif a and not b:
            diffs.append((sid, a["title"], a["content"], "该条款在新版本模拟文件中未出现"))
        elif b and not a:
            diffs.append((sid, b["title"], "旧版本模拟文件中未出现", b["content"]))
    return pair, diffs

def make_checklist(kind):
    mapping = {
        "小微企业流动资金贷款": [
            "营业执照或主体资格证明", "法定代表人及授权经办人身份证明", "企业基本信息及实际控制人信息",
            "经营情况说明", "融资用途及资金需求说明", "财务、纳税、账户流水等佐证材料（按实际要求）"
        ],
        "个人消费贷款": [
            "有效身份证明", "贷款申请及必要授权", "收入或还款能力证明", "贷款用途证明或用途说明", "银行要求的其他材料"
        ],
        "对公账户开立": [
            "主体资格证明文件", "法定代表人或单位负责人身份证明", "授权经办人身份证明及授权材料（如适用）",
            "受益所有人及实际控制人信息", "经营地址、联系方式和开户用途说明", "风险核查所需补充材料"
        ],
        "客户投诉处理": [
            "客户诉求及联系方式", "涉及产品或服务信息", "投诉发生时间及渠道", "相关业务办理记录", "历史沟通记录", "已采取措施及待核实事项"
        ]
    }
    return mapping[kind]

st.markdown("""
<div class="hero">
  <div style="font-size:.85rem;letter-spacing:.08em;opacity:.8;">BANKING INTELLIGENCE AGENT</div>
  <h1>🏦 智规通</h1>
  <p>银行智能知识与制度 Agent · 让制度查询更快，让业务指导更清晰</p>
</div>
""", unsafe_allow_html=True)

st.warning(DISCLAIMER, icon="⚠️")

with st.sidebar:
    st.markdown("## 🏦 智规通")
    st.caption("银行智能知识与制度 Agent")
    page = st.radio("功能导航", ["工作台", "智能制度问答", "业务场景指导", "制度版本对比", "材料清单生成", "合规风险分析", "知识库浏览"])
    st.divider()
    st.caption("演示知识库")
    st.write(f"📚 {len(POLICIES)} 份模拟制度版本")
    st.write("🏢 对公 · 零售 · 运营 · 客户服务")
    st.caption("Prototype v0.1")

if page == "工作台":
    st.subheader("欢迎使用智规通")
    st.write("面向银行员工的制度知识助手。选择一个任务开始，或直接进入智能问答。")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("模拟制度", "5 类")
    c2.metric("制度版本", f"{len(POLICIES)} 份")
    c3.metric("核心能力", "6 项")
    c4.metric("覆盖领域", "4 个")
    st.markdown("### 快速开始")
    samples = [
        ("🔎 制度查询", "小微企业流动资金贷款需要哪些申请材料？"),
        ("🧭 业务指导", "客户开立对公账户时缺少一项证明材料，应该怎么处理？"),
        ("⚖️ 风险分析", "企业贷款用途说明与实际经营情况不一致，有哪些风险需要核查？"),
        ("📋 材料清单", "请生成个人消费贷款申请材料清单。")
    ]
    for label, q in samples:
        with st.expander(label):
            st.write(q)
            st.code("可复制到“智能制度问答”或对应功能模块体验。", language="text")
    st.info("建议演示路线：制度问答 → 业务场景指导 → 制度版本对比 → 风险分析。")

elif page in ["智能制度问答", "业务场景指导", "合规风险分析"]:
    titles = {
        "智能制度问答": ("智能制度问答", "用自然语言查询制度条款，回答附带制度来源。", "例如：小微企业流动资金贷款需要哪些申请材料？"),
        "业务场景指导": ("业务场景指导", "描述业务情况，Agent 自动拆解任务并匹配相关制度。", "例如：客户开立对公账户时缺少一项证明材料，应该怎么处理？"),
        "合规风险分析": ("合规风险分析", "输入业务操作或异常情况，获取制度依据和核查建议。", "例如：企业贷款用途与经营情况不匹配，有哪些风险需要核查？")
    }
    title, desc, placeholder = titles[page]
    st.subheader(title)
    st.caption(desc)
    q = st.text_area("请输入您的问题或业务场景", placeholder=placeholder, height=130, key=f"q_{page}")
    if st.button("🚀 开始分析", type="primary", use_container_width=True, disabled=not q.strip()):
        mode = {"智能制度问答":"智能制度问答","业务场景指导":"业务场景指导","合规风险分析":"合规风险分析"}[page]
        result = build_answer(q, mode=mode)
        st.session_state[f"last_result_{page}"] = result
        st.session_state[f"last_question_{page}"] = q
    if f"last_result_{page}" in st.session_state:
        result = st.session_state[f"last_result_{page}"]
        st.markdown("### Agent 分析结果")
        st.success(f"任务识别：{result['intent']}")
        st.markdown(result["answer"])
        st.markdown("### 📚 制度依据")
        if result["sources"]:
            for s in result["sources"]:
                with st.expander(f"{s['doc']} · {s['version']} · 第{s['section']}条 {s['section_title']}"):
                    st.write(s["content"])
                    st.caption(f"文件编号：{s['id']}｜生效日期：{s['effective']}")
        else:
            st.info("没有检索到足够的模拟制度依据。")
        question_for_report = st.session_state.get(f"last_question_{page}", "")
        report = f"# 智规通分析报告\n\n问题：{question_for_report}\n\n任务类型：{result['intent']}\n\n{result['answer']}\n\n## 制度依据\n"
        for s in result["sources"]:
            report += f"\n- {s['doc']}（{s['version']}）第{s['section']}条 {s['section_title']}：{s['content']}\n"
        st.download_button("⬇️ 下载分析报告", report.encode("utf-8"), file_name="智规通分析报告.md", mime="text/markdown")

elif page == "制度版本对比":
    st.subheader("制度版本智能对比")
    st.caption("当前提供一组模拟新旧版本，用于展示条款差异分析能力。")
    name = st.selectbox("选择制度", list(COMPARE.keys()))
    pair, diffs = compare_versions(name)
    a,b = st.columns(2)
    with a:
        st.markdown("#### 旧版本")
        st.info(f"{pair['old']['version']} · {pair['old']['effective_date']}")
    with b:
        st.markdown("#### 新版本")
        st.success(f"{pair['new']['version']} · {pair['new']['effective_date']}")
    st.markdown(f"### 检测到 {len(diffs)} 项条款差异")
    for sid, title, old_text, new_text in diffs:
        with st.expander(f"第 {sid} 条 · {title}", expanded=True):
            x,y = st.columns(2)
            with x:
                st.markdown("**旧版本内容**")
                st.write(old_text)
            with y:
                st.markdown("**新版本内容**")
                st.write(new_text)
            st.caption("以上差异为本项目模拟数据，不代表真实制度修订。")
    st.info("正式版本可进一步增加差异分类：新增、删除、修改、审批权限变化及业务影响。")

elif page == "材料清单生成":
    st.subheader("业务材料清单生成")
    st.caption("根据模拟制度生成业务办理前的材料核对清单。")
    kind = st.selectbox("选择业务类型", ["小微企业流动资金贷款", "个人消费贷款", "对公账户开立", "客户投诉处理"])
    if st.button("生成材料清单", type="primary"):
        st.session_state["generated_checklist_kind"] = kind
    if st.session_state.get("generated_checklist_kind") == kind:
        items = make_checklist(kind)
        st.markdown(f"### {kind} · 材料核对清单")
        checked_items = []
        for item in items:
            if st.checkbox(item, key=f"check_{kind}_{item}"):
                checked_items.append(item)
        checklist_text = f"# {kind}材料核对清单\n\n"
        checklist_text += "\n".join([f"- [{'x' if x in checked_items else ' '}] {x}" for x in items])
        st.download_button("⬇️ 下载清单", checklist_text.encode("utf-8"), file_name="业务材料清单.md", mime="text/markdown")
        st.caption("清单仅用于演示，实际材料要求以正式有效制度和具体产品细则为准。")

elif page == "知识库浏览":
    st.subheader("模拟制度知识库")
    st.caption("可按业务领域筛选，查看文件版本、条款内容和生效日期。")
    domains = ["全部"] + sorted(set(p["domain"] for p in POLICIES))
    domain = st.selectbox("业务领域", domains)
    items = [p for p in POLICIES if domain == "全部" or p["domain"] == domain]
    for p in items:
        with st.expander(f"{p['title']} · {p['version']} · {p['domain']}"):
            st.write(f"文件编号：{p['id']}  |  生效日期：{p['effective_date']}  |  状态：{p['status']}")
            for sec in p["sections"]:
                st.markdown(f"**第 {sec['id']} 条 · {sec['title']}**")
                st.write(sec["content"])

st.divider()
st.caption("智规通 Prototype v0.1 · 模拟制度知识库 · 不构成真实业务、法律、合规或授信意见")
