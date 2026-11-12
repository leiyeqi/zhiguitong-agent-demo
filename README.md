# 智规通｜银行智能知识与制度 Agent（MVP）

## 1. 项目说明
智规通是面向银行员工的智能知识与制度助手比赛原型。当前版本使用**完全虚构的模拟制度**演示以下能力：

- 智能制度问答与制度出处展示
- 业务场景指导
- 制度版本对比
- 业务材料清单生成
- 合规风险提示
- 模拟制度知识库浏览

> 重要：本项目不是任何真实银行的正式制度系统。所有规则、文件编号和版本均为演示数据，不得用于真实业务办理、客户决策或合规审批。

## 2. 本版本技术说明
- Python + Streamlit：交互界面与应用逻辑
- JSON：模拟制度知识库
- 检索与任务路由：本地关键词检索和规则路由，用于无 API Key 的可运行演示
- 预留升级方向：接入经银行批准的大模型、RAG 向量检索、Dify/LangGraph Agent 工作流、权限校验和审计日志

当前 v0.1 是可运行的 Agent 原型，尚未连接真实大模型，也不应在比赛材料中宣称已经实现真实 LLM 自主推理或真实银行知识库。

## 3. 本地运行
建议 Python 3.10 或更高版本。

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
streamlit run app.py
```

浏览器打开 Streamlit 输出的本地地址（通常是 http://localhost:8501）。

## 4. 在线演示部署（仅使用模拟数据）
1. 将本项目文件上传到 GitHub 仓库。
2. 登录 Streamlit Community Cloud。
3. 选择该仓库、分支和 `app.py`。
4. 点击 Deploy，等待构建完成。
5. 复制生成的应用 URL，作为比赛演示链接（先确认比赛允许使用外部托管平台）。

官方入口：
- Streamlit Community Cloud: https://share.streamlit.io/
- Streamlit 文档: https://docs.streamlit.io/

## 5. 银行环境部署注意事项
- 不要把真实客户信息、账户信息、交易数据或未获批准的内部制度上传到公开 GitHub 或公共托管服务。
- 正式环境应优先部署到银行批准的内网、私有云或受控环境。
- 对知识库实施文档级和条款级权限控制。
- 回答必须提供制度名称、版本、生效日期、条款编号和原文引用。
- 旧版本制度应标识为历史版本，不能与现行制度混用。
- 无检索依据时应明确拒答或转人工核实。
- 授信、开户、客户身份识别、投诉处理等高影响事项必须保留人工审核和银行授权流程。

## 6. 项目目录
```text
zhiguitong_agent_mvp/
├── app.py
├── requirements.txt
├── README.md
├── PRODUCT_BRIEF.md
├── PRODUCT_BRIEF.docx
├── DEMO_SCRIPT.md
├── data/
│   └── policies.json
└── tests/
    └── test_policy_data.py
```

## 7. 下一步升级路线
- v0.2：使用真实可控的 embedding + 向量数据库实现 RAG，并提供精确引用。
- v0.3：接入经批准的大模型，增加规划、工具调用、结果校验和多轮澄清。
- v0.4：增加用户角色、部门权限、文档密级和审计日志。
- v1.0：部署至比赛允许且银行批准的环境，完成性能、准确性和安全测试。
