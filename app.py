             "> 仅供公开/模拟资料演示和个人学习；本记录不证明尽职调查履职完成，也不替代本行正式业务系统、调查报告或有权审核。", "",
             "## 逐项核对"]
    for i, row in enumerate(result["rows"], 1):
        lines.append(f"{i}. {row['item']}｜状态：{row['status']}｜证据/理由：{row['evidence'] or '未填写'}")
    lines.extend(["", "## 待进一步核实或补齐的事项"])
    lines.extend([f"- {x}" for x in result["gaps"]] or ["- 演示模板中的项目均已填写核对结果；仍需依据有效制度检查完整性和证据真实性。"])
    lines.extend(["", "## 用户勾选的风险线索"])
    lines.extend([f"- {x}" for x in signals] or ["- 未勾选（不代表不存在风险）。"])
    lines.extend(["", "## 其他学习备注", memo or "（未填写）", "", "## 提示", WORKFLOWS[workflow]["caution"],
                  "本清单来自通用演示模板；是否适用、调查是否充分、是否允许流转或放款，均由本行有效制度及有权人员决定。"])
    return "\n".join(lines)


def run_app() -> None:
    import streamlit as st

    st.set_page_config(page_title="智规通 3.1｜制度学习与尽职调查", page_icon="📖", layout="wide")
    st.markdown("""
    <style>
      .block-container{max-width:1120px;padding-top:1.2rem;padding-bottom:3rem}
      .study-hero{background:linear-gradient(115deg,#10334c,#236079);color:#fff;border-radius:16px;padding:1.2rem 1.5rem;margin-bottom:1rem}
      .study-hero h1{color:white;font-size:2rem;margin:0 0 .3rem}.study-hero p{color:#e0edf4;margin:0}
    </style>
    """, unsafe_allow_html=True)
    st.markdown('<div class="study-hero"><h1>📖 智规通</h1><p>银行制度学习与尽职调查助手｜读懂文件 · 查明流程 · 核对遗漏</p></div>', unsafe_allow_html=True)
    st.warning("演示版仅限公开、模拟或已经本行批准可以外部处理的资料。当前网站运行在公网云端，禁止上传未获授权的总行内部制度及真实客户资料。流程和清单是通用学习提纲，不是本行正式合规标准。", icon="🔒")

    try:
        policies = load_policies()
    except Exception as exc:
        st.error(f"模拟数据载入失败：{exc}。请确保 data/policies.json 文件仍在仓库。")
        st.stop()

    if "study_doc" not in st.session_state:
        st.session_state.study_doc = None
    if "study_doc_token" not in st.session_state:
        st.session_state.study_doc_token = ""
    if "due_report" not in st.session_state:
        st.session_state.due_report = ""

    with st.sidebar:
        st.markdown("### 智规通 v3.1")
        page = st.radio("我今天想做什么", ["📖 学制度", "🧭 查流程", "✅ 做尽调"], key="v31_nav")
        st.divider()
        if st.session_state.study_doc:
            st.success(f"已读取：{st.session_state.study_doc['name']}")
            st.caption("只用于当前会话；不是永久知识库。")
        else:
            st.caption("尚未导入公开测试文件。")
        st.caption("当前不接入大模型，不产生 API 费用。")
        with st.expander("公开法规入口及使用说明"):
            for ref in REGULATORY_REFERENCES:
                st.markdown(f"[{ref['title']}]({ref['url']})")
            st.caption("公开法规仅提供索引；应核对最新正式有效文本及本行细则。")

    if page == "📖 学制度":
        st.subheader("第一步：把文件读懂")
        st.write("选择一份可用于外部演示的 PDF、Word 或文本文件。系统会抽取原文、标出重要表述，并提供逐项学习提示和原文检索。")
        permitted = st.checkbox("我确认文件为公开、模拟或已经批准可在当前公网环境处理的非敏感资料", key="v31_permitted")
        uploaded = st.file_uploader("上传一份制度学习资料", type=["pdf", "docx", "txt", "md"], disabled=not permitted, key="v31_file")
        if uploaded is not None and permitted:
            blob = uploaded.getvalue()
            token = f"{uploaded.name}:{hashlib.sha256(blob).hexdigest()}"
            if token != st.session_state.study_doc_token:
                try:
                    st.session_state.study_doc = parse_study_file(uploaded.name, blob)
                    st.session_state.study_doc_token = token
                except Exception as exc:
                    st.session_state.study_doc = None
                    st.session_state.study_doc_token = ""
                    st.error(f"文件读取失败：{exc}")
        doc = st.session_state.study_doc
        if doc:
            st.success(f"已提取《{doc['name']}》，共 {len(doc['parts'])} 个可定位文本片段。")
            st.info("本阶段是**原文抽取 + 关键词学习提示**，不是 AI 自动理解。正式的逐条白话解释需要在经批准的环境接入大模型。")
            c1, c2, c3 = st.columns(3)
            c1.metric("可读取字符", len(doc["text"]))
            points = extract_learning_points(doc)
            c2.metric("重点原文候选", len(points))
            present_terms = [(k, v) for k, v in READING_GLOSSARY.items() if k in doc["text"]]
            c3.metric("相关术语", len(present_terms))
            tab1, tab2, tab3 = st.tabs(["⭐ 重点原文学", "💬 带着问题查", "🗒️ 我的学习笔记"])
            with tab1:
                if points:
                    for i, point in enumerate(points, 1):
                        with st.expander(f"重点 {i}｜{point['locator']}｜{point['text'][:46]}…", expanded=i <= 2):
                            st.markdown("**制度原文摘录**")
                            st.write(point["text"])
                            st.markdown("**怎么读这条？**")
                            st.write(reading_hint(point["text"]))
                            st.caption("阅读提示用于辅助理解条款结构，不能替代完整上下文或正式制度解释。")
                else:
                    st.info("这份资料没有检出常见规范性用语，可通过“带着问题查”阅读原文。")
                if present_terms:
                    st.markdown("#### 常见术语怎么理解")
                    for term, meaning in present_terms[:10]:
                        st.markdown(f"**{term}**：{meaning}")
                    st.caption("术语说明为通用教学解释，遇到本行制度中的专门定义，以文件原文为准。")
            with tab2:
                question = st.text_input("你现在看不懂什么？", placeholder="例如：文件对尽职调查、核验和资料留存有哪些要求？", key="v31_doc_question")
                if question:
                    hits = find_doc_passages(doc, question)
                    if hits:
                        st.markdown("**以下是可能相关的原文，建议结合上下文阅读：**")
                        for idx, part in enumerate(hits, 1):
                            with st.expander(f"原文 {idx}｜{part['locator']}", expanded=idx == 1):
                                st.write(part["text"])
                                st.caption("关键词/字符匹配结果，不代表已经正确解释或认定该条适用。")
                    else:
                        st.info("没有可靠的相近片段。请换成文件中的关键词、条款编号或更具体的提问。")
                st.caption("目前不会编造某一条制度的意思；暂不支持真正的自然语言连续追问。")
            with tab3:
                note = st.text_area("用自己的话写下理解、不懂的地方或待向主管确认的问题", height=170, key="v31_study_note")
                highlights = "\n".join(f"- [{p['locator']}] {p['text']}" for p in points)
                exported = f"# 智规通制度学习笔记\n\n文件：{doc['name']}\n生成日期：{date.today().isoformat()}\n\n## 重点原文候选\n{highlights}\n\n## 我的学习笔记\n{note}\n\n提示：本文件包含自动提取片段，不构成正式制度解释。"
                st.download_button("下载学习笔记（Markdown）", exported.encode("utf-8"), "智规通制度学习笔记.md", mime="text/markdown", use_container_width=True)
            with st.expander("查看提取出的完整文字（最多显示前一万字）"):
                st.text(doc["text"][:10000])
        else:
            st.info("还没有文件？可先在左侧“公开法规入口”寻找公开资料，或使用自己编写的模拟制度文本练习。")
            st.markdown("**建议第一次练习：**准备一份公开文件，先看重点原文，再搜索“尽职调查”或“核验”这样的关键词。")

    elif page == "🧭 查流程":
        st.subheader("第二步：把业务流程弄明白")
        st.warning("以下流程来自原项目通用演示模板。每一步是否为强制要求、适用哪些机构与业务，应以现行制度和本行权限流程核准。", icon="⚠️")
        workflow = st.selectbox("选择要学习的业务", STUDY_WORKFLOWS, key="v31_flow")
        template = WORKFLOWS[workflow]
        st.write(template["description"])
        for i, (stage, action, proof) in enumerate(PROCESS_STAGES[workflow], 1):
            with st.expander(f"第 {i} 步｜{stage}", expanded=i == 1):
                st.markdown(f"**客户经理要理解的动作：** {action}")
                st.markdown(f"**建议核实和记录：** {proof}")
        with st.expander("这个流程容易忽视哪些问题？"):
            for signal in template["signals"]:
                st.markdown(f"- {signal}")
        if st.session_state.study_doc:
            st.markdown("#### 对照刚才上传的文件找依据")
            st.caption("下面只是检索可能相关原文，不会把通用模板误认作已得到总行制度授权。")
            search = st.text_input("从文件中查询对应内容", value="尽职调查", key="v31_flow_search")
            if search:
                hits = find_doc_passages(st.session_state.study_doc, search, limit=3)
                for hit in hits:
                    with st.expander(hit["locator"]):
                        st.write(hit["text"])
                if not hits:
                    st.info("没有找到明显相关的原文，请核对文件是否涵盖这一业务。")
        st.markdown("#### 接下来怎么做？")
        st.write("理解后可以进入左侧的 **✅ 做尽调**，对照清单核实哪些项目还有疑点。")

    else:
        st.subheader("第三步：检查尽职调查有没有遗漏")
        st.warning("这里是**尽调学习核对清单**，不是正式履职记录，也不能自动判断“尽职调查已完成”。请只填虚构代号、模拟证据描述，不要填写真实客户信息。", icon="⚠️")
        workflow = st.selectbox("选择调查业务", STUDY_WORKFLOWS, key="v31_due_flow")
        template = WORKFLOWS[workflow]
        st.caption(template["description"])
        st.markdown("**使用方法：**对每个核对点选择状态。选择“已核实”时填一个模拟证据位置，选择“不适用”时填理由；否则系统会提示仍有遗漏。")
        with st.form(f"v31_due_form_{STUDY_WORKFLOWS.index(workflow)}"):
            statuses, evidences = [], []
            for i, item in enumerate(template["checklist"]):
                st.markdown(f"**{i+1}. {item}**")
