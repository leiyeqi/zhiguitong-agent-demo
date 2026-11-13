"""智规通 v3.0｜浙江农信成员行社通用客户经理工作台（演示版）

定位：制度检索 + 客户经理工作流模板 + 可溯源的辅助记录。
重要边界：不接入大语言模型、不做授信/开户/反洗钱自动决策；
内置制度仍是原项目虚构模拟文件，公开监管法规只提供官方来源索引与摘要。
用户上传文件仅保存在当前 Streamlit 会话内存中，不写入项目目录。
"""
from __future__ import annotations

import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from difflib import SequenceMatcher
from typing import Any

BASE = Path(__file__).resolve().parent
DATA_FILE = BASE / "data" / "policies.json"
APP_VERSION = "v3.1 极简界面"
NOTICE = (
    "本项目是比赛/学习演示原型，内置制度为虚构模拟文件，不代表浙江农信或任何成员行社的内部制度、产品政策或授权要求。"
    "当前应用未接入大语言模型，不作授信、准入、开户、反洗钱或合规结论。请勿在当前 Streamlit 公网演示站上传真实客户资料、"
    "身份证件、账户流水、征信报告、内部保密制度或其他敏感数据。真实业务须以本行正式有效制度、系统校验及有权人员审核为准。"
)

# 业务主题仅用于定位已有模拟制度，不代表成员行社产品范围。
TOPIC_ALIASES = {
    "CORP-LOAN-001": ["小微企业流动资金贷款", "小微企业贷款", "小微贷款", "流动资金贷款", "企业贷款", "对公贷款", "企业授信", "公司贷款", "小微企业", "企业融资", "流贷"],
    "RETAIL-LOAN-002": ["个人消费贷款", "消费贷款", "个人贷款", "消费贷", "零售贷款", "个人借款", "个人信贷"],
    "OPS-ACCOUNT-003": ["对公账户", "开立对公账户", "企业开户", "公司开户", "单位开户", "账户开立", "账户开户", "对公开户", "开立账户", "基本户", "开户", "对公结算账户"],
    "OPS-KYC-004": ["客户身份识别", "强化尽职调查", "客户尽职调查", "尽职调查", "受益所有人", "实际控制人", "反洗钱", "身份识别", "客户身份", "kyc", "可疑交易"],
    "CX-COMPLAINT-005": ["投诉处理", "客户投诉", "消费者权益", "投诉", "消保", "服务争议", "客户申诉"],
}
DOMAIN_NAMES = {
    "CORP-LOAN-001": "小微企业流动资金贷款", "RETAIL-LOAN-002": "个人消费贷款",
    "OPS-ACCOUNT-003": "对公账户开立", "OPS-KYC-004": "客户身份识别与尽职调查",
    "CX-COMPLAINT-005": "客户投诉处理",
}
INTENT_TERMS = {
    "版本对比": ["对比", "比较", "变化", "差异", "新旧", "修订", "版本", "改了"],
    "成本披露": ["综合融资成本", "息费", "年化成本", "费用明示", "成本明示表"],
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
    "成本披露": ("成本", "费用", "披露"),
    "制度问答": (), "版本对比": (),
}
SAMPLE_QUESTIONS = [
    "小微企业流动资金贷款需要哪些申请材料？",
    "那风险方面有哪些需要核查？",
    "客户开立对公账户时缺少一项证明材料，应该怎么处理？",
    "个人贷款综合融资成本明示表需要展示哪些内容？",
    "客户投诉受理时应记录什么？",
]

# 公开监管文件来源索引。摘要仅作导航，正式使用应打开原文并由本行归口部门确认适用性。
REGULATORY_REFERENCES = [
    {
        "title": "流动资金贷款管理办法", "issuer": "国家金融监督管理总局", "number": "国家金融监督管理总局令2024年第2号",
        "date": "2024-02-02发布；2024-07-01施行", "summary": "流动资金贷款业务经营与审慎管理的公开监管规章。可作为企业流动资金贷款全流程管理的外部法规检索入口；具体适用和成员行社细则需另行核验。",
        "url": "https://www.nfra.gov.cn/cn/view/pages/governmentDetail.html?docId=1151066&itemId=861",
        "tags": ["小微", "企业贷款", "流动资金", "贷款调查", "贷后"],
    },
    {
        "title": "个人贷款管理办法", "issuer": "国家金融监督管理总局", "number": "国家金融监督管理总局令2024年第3号",
        "date": "2024-01-30公布；2024-07-01施行", "summary": "规范个人消费、生产经营等个人贷款业务。注意：该办法对农户用于生产性贷款等国家有专门政策规定的特殊类个人贷款作了适用范围说明，农户生产性贷款不能不加区分地套用一般个人贷款模板。",
        "url": "https://www.nfra.gov.cn/cn/view/pages/governmentDetail.html?docId=1151064&generaltype=1&itemId=4214",
        "tags": ["个人贷款", "消费贷", "个人经营贷", "还款能力", "面谈"],
    },
    {
        "title": "固定资产贷款管理办法", "issuer": "国家金融监督管理总局", "number": "国家金融监督管理总局令2024年第1号",
        "date": "2024-02-02发布；2024-07-01施行", "summary": "规范固定资产投资用途贷款业务。用于固定资产投资项目时，应核对项目、用途、支付和贷后管理等正式要求。",
        "url": "https://www.nfra.gov.cn/cn/view/pages/governmentDetail.html?docId=1151060&itemId=861",
        "tags": ["固定资产贷款", "项目贷款", "企业贷款", "资金用途"],
    },
    {
        "title": "银行保险机构数据安全管理办法", "issuer": "国家金融监督管理总局", "number": "金规〔2024〕24号",
        "date": "2024-12-27发布", "summary": "要求银行保险机构建立数据安全治理、分类分级、访问授权、风险评估和模型算法管理等机制。对智规通的制度资料导入、客户信息处理、模型应用和上线审批具有重要参考意义。",
        "url": "https://www.nfra.gov.cn/cn/view/pages/governmentDetail.html?docId=1192311",
        "tags": ["数据安全", "个人信息", "人工智能", "模型治理", "权限"],
    },
    {
        "title": "个人贷款业务明示综合融资成本规定", "issuer": "国家金融监督管理总局、中国人民银行", "number": "金规〔2026〕2号",
        "date": "2026-03-03发布；2026-08-01施行", "summary": "要求个人贷款业务向借款人展示综合融资成本明示表，逐项列明本金、息费项目、收取方式、标准和主体，并明示正常履约年化综合融资成本及违约或有成本；现场办理应在签约前由借款人签字确认，线上办理应按规定展示并确认。",
        "url": "https://www.nfra.gov.cn/cn/view/pages/ItemDetail.html?docId=1251479&generaltype=1&itemId=861",
        "tags": ["个人贷款", "综合融资成本", "息费披露", "消费者权益", "助贷"],
    },
]

# 通用客户经理工作流模板：是信息收集提纲，不是任何成员行社的强制材料清单或准入标准。
WORKFLOWS: dict[str, dict[str, Any]] = {
    "小微企业流动资金贷款调查": {
        "group": "对公与普惠", "description": "围绕主体、经营、融资用途、还款来源和风险线索形成调查提纲。",
        "fields": [
            ("客户代号/项目编号", "例如：企业A（请勿填真实名称或统一社会信用代码）"),
            ("主体与股权情况", "主体类型、成立时间、股权结构、实际控制人核验情况"),
            ("主营业务与经营模式", "产品/服务、上下游、主要客户和供应商、经营场所"),
            ("经营持续性与现场核验", "经营年限、现场走访日期、库存/订单/设备/员工等可核验信息"),
            ("融资需求与资金用途", "申请金额、期限、用途、支付对象、测算依据（仅记录，不自动审批）"),
            ("第一还款来源", "经营现金流、回款周期、主要回款账户及可核验佐证"),
            ("现有融资与或有负债", "已知融资、担保、涉诉、逾期等情况及核验来源"),
            ("担保与风险缓释", "担保方式、抵质押物权属/价值/登记核验进度（如适用）"),
            ("待补充资料与后续动作", "待核实问题、补充材料、责任人和计划完成时间"),
        ],
        "checklist": ["主体资格及授权材料已按本行要求核验", "实际控制人及关联关系已核查", "经营场所和主营业务已核实", "融资用途及支付安排已核实", "第一还款来源及现金流佐证已核查", "现有融资及或有负债已核查", "担保措施和权属情况已核查（如适用）", "调查记录和影像/资料已按本行制度归档"],
        "signals": ["经营场所与申报经营情况不一致", "订单/流水/纳税等信息相互矛盾", "融资用途与主营业务明显不匹配", "回款来源不清或依赖非经营性资金", "关联关系或实际控制人识别不充分", "存在重复融资、资金挪用或异常转账线索", "担保权属、价值或登记情况待核实"],
        "caution": "仅用于整理调查事实和待核事项；不计算授信额度、不判断准入、不代替审查审批。",
    },
    "涉农/农户生产经营调查": {
        "group": "涉农与农户", "description": "围绕农业生产周期、经营规模、销售回款和自然风险收集信息。",
        "fields": [
            ("客户代号/经营主体", "使用虚构代号；主体类型及家庭/合作社/企业经营关系"),
            ("生产经营类型与周期", "种植/养殖/农产品加工等，生产周期、季节性和关键节点"),
            ("经营规模与生产条件", "土地/设施/圈舍/设备等规模与权属或使用情况"),
            ("投入成本与资金需求", "种苗、饲料、农资、人工、租金等投入及资金用途"),
            ("销售渠道与回款安排", "订单、收购方、批发/零售渠道、结算周期和佐证"),
            ("收入、支出与还款来源", "历史产量/销售/成本、家庭或经营现金流、其他收入"),
            ("自然灾害与保险情况", "天气、疫病、价格波动、农业保险或其他风险缓释情况"),
            ("现场走访与核验记录", "走访日期、地点类型、现场观察、访谈对象和交叉核验"),
            ("待核事项与后续动作", "待补充材料、复核事项、责任人和计划时间"),
        ],
        "checklist": ["经营主体和实际经营人关系已核实", "生产场地及经营规模已核实", "生产周期和资金需求匹配情况已记录", "销售渠道及回款佐证已核实", "历史产量、成本和收入数据已交叉核验", "自然灾害、疫病、价格波动等风险已了解", "农业保险或其他风险缓释情况已了解（如适用）", "适用专项政策及本行农户贷款细则已核对"],
        "signals": ["生产规模与申报信息差异明显", "销售渠道或收购方真实性待核实", "产量/价格/收入假设过于乐观", "资金需求与生产周期不匹配", "存在重大自然灾害、疫病或价格波动影响", "还款来源主要依赖不确定的非经营性收入"],
        "caution": "农户生产性贷款可能涉及专项政策和不同适用规则；必须先核对现行国家规定及本行正式细则，不得直接套用一般个人贷款模板。",
    },
    "个人经营贷款调查": {
        "group": "零售与个人经营", "description": "整理借款人经营、收入负债、融资用途和还款来源核查事项。",
        "fields": [
            ("客户代号", "使用虚构代号，不填写姓名、身份证号、手机号"),
            ("经营主体及实际经营情况", "经营主体类型、经营年限、场所、主要产品/服务"),
            ("经营收入与成本", "收入来源、主要成本、季节性、可核验凭证"),
            ("贷款用途及资金需求", "用途、金额、期限、交易背景和支付安排"),
            ("收入、支出与负债", "收入构成、家庭/经营支出、现有融资及或有负债"),
            ("还款来源及现金流", "第一还款来源、回款周期、还款安排及佐证"),
            ("担保及其他风险事项", "担保方式、权属核验、经营/信用/涉诉等待核事项"),
            ("待补资料与后续动作", "待核实事项、责任人、计划完成时间"),
        ],
        "checklist": ["客户身份、申请意愿及授权按要求核验", "实际经营情况已核实", "贷款用途明确且有交易背景佐证", "收入、支出、负债和还款来源已调查", "经营及家庭现金流已综合了解", "担保事项已核实（如适用）", "调查意见与证据材料已归档"],
        "signals": ["实际经营人和申请人关系不清", "收入证明与经营流水不一致", "贷款用途或交易背景不清晰", "债务负担和还款来源信息不完整", "第三方代办或中介介入情况异常"],
        "caution": "不得依据本工具输出判断客户是否符合授信条件或确定额度、利率、期限；应按本行授权流程调查、审查和审批。",
    },
    "个人消费贷款业务核对": {
        "group": "零售与个人经营", "description": "核对身份、用途、还款能力、授权和个人贷款综合融资成本披露事项。",
        "fields": [
            ("客户代号", "使用虚构代号，不填写真实个人身份信息"),
            ("申请与身份核验", "申请意愿、身份核验、授权及资料一致性情况"),
            ("贷款用途", "具体用途、交易背景、用途证明及产品允许范围核验情况"),
            ("收入、支出与现有负债", "收入来源、稳定性、家庭/个人支出、其他负债核验情况"),
            ("还款来源与能力核验", "主要还款来源、还款安排、核验依据及待核事项"),
            ("息费及综合融资成本披露", "贷款利息、分期/服务/增信等息费项目、收取主体和标准、年化综合成本明示表确认情况"),
            ("面谈、审批与放款条件", "面谈记录、风险审查、授权审批及放款条件核验进度"),
            ("待补资料与后续动作", "待核实事项、责任人和计划时间"),
        ],
        "checklist": ["客户身份、申请意愿和授权已核验", "贷款用途明确、合法并符合产品要求", "收入、支出、负债和还款来源已调查", "面谈及调查记录已按要求留存", "贷款人及合作机构收取的息费项目已逐项核对", "综合融资成本明示表已按要求展示并留存确认", "审批权限及放款条件已核验"],
        "signals": ["用途说明与交易背景不一致", "收入、支出、负债资料存在矛盾", "息费项目、收取主体或年化成本披露不完整", "合作机构收费与披露内容不一致", "存在中介代办、虚假资料或异常资金流向线索"],
        "caution": "个人贷款综合融资成本明示要求应核对金规〔2026〕2号及本行实施细则；本工具不计算法定年化成本，不替代明示表或客户确认。",
    },
    "对公账户开立与尽职调查": {
        "group": "运营与账户", "description": "整理开户主体、经办权限、受益所有人、经营地址、开户目的和风险核查事项。",
        "fields": [
            ("企业代号", "使用虚构代号，不填写真实客户名称或统一社会信用代码"),
            ("主体资格与存续情况", "主体类型、登记状态、经营范围及核验来源"),
            ("法定代表人/负责人及经办人", "身份核验、授权关系、到场/远程核验情况"),
            ("受益所有人及实际控制人", "识别路径、控制关系、信息来源及疑点"),
            ("经营地址与经营情况", "注册地址、实际经营地址、经营场所和业务情况"),
            ("开户目的与预期交易", "开户用途、主要交易对手、资金来源和预计交易特征"),
            ("风险识别与补充核查", "风险因素、补充核实措施、待确认事项"),
            ("审批、归档与后续管理", "审核流程、资料归档、账户后续监测安排"),
        ],
        "checklist": ["主体资格证明材料已按要求核验", "法定代表人/负责人身份已核验", "经办人身份和授权关系已核验", "受益所有人及实际控制人已识别", "经营地址和经营情况已核实", "开户目的及预期交易特征已了解", "异常或疑点已按内部流程升级", "资料归档和后续管理安排已落实"],
        "signals": ["注册地址与实际经营情况差异较大", "经办人授权关系无法核实", "受益所有人识别链条不清", "开户目的与经营背景不匹配", "预期交易特征异常或解释不足"],
        "caution": "账户开立、客户风险分类、强化尽调和是否准入必须依照本行现行制度及有权岗位判断。",
    },
    "客户身份识别与尽职调查": {
        "group": "运营与账户", "description": "围绕身份真实性、业务关系目的、受益所有人、资金来源和持续尽调形成记录。",
        "fields": [
            ("客户代号与客户类型", "使用虚构代号；自然人/法人/其他组织等类型"),
            ("身份资料核验", "核验资料类别、来源、核验方式和差异情况"),
            ("业务关系目的与性质", "建立业务关系的目的、预期产品/服务和交易特点"),
            ("受益所有人/实际控制人", "识别依据、控制链条、信息来源及不确定事项"),
            ("资金来源与交易背景", "客户说明、佐证材料、交易对手和待核实事项"),
            ("风险变化与持续尽调", "身份资料变化、交易行为变化、异常信号和后续核查"),
            ("记录留存与升级", "核查过程、资料来源、结论依据和升级部门/流程（不填写敏感信息）"),
        ],
        "checklist": ["身份资料真实性和有效性已核验", "业务关系目的和性质已了解", "受益所有人及实际控制人已识别（如适用）", "资金来源和交易背景已了解", "异常情况已采取进一步核实措施", "过程记录、资料来源和处理意见已留存", "无法完成核实或重大疑点已按内部流程升级"],
        "signals": ["身份资料与公开/留存信息不一致", "受益所有人或控制关系不透明", "交易目的、资金来源解释不足", "交易行为与客户经营背景明显不匹配", "必要核实无法完成或重大疑点未排除"],
        "caution": "本工具不进行客户风险等级判定、不替代反洗钱系统监测，也不输出可疑交易报告结论。",
    },
    "贷后检查与风险回访": {
        "group": "贷后管理", "description": "按贷后管理思路整理经营变化、资金用途、还款、担保和风险信号。",
        "fields": [
            ("客户代号/贷款项目", "使用虚构代号，不填写真实客户身份、账号或合同号"),
            ("检查时间与方式", "现场/非现场、检查日期、参与人员岗位"),
            ("经营情况变化", "经营场所、主营业务、订单、库存、人员、上下游变化"),
            ("贷款资金用途核查", "合同约定用途、支付凭证、交易背景和资金流向核查情况"),
            ("回款与还款情况", "销售回款、账户流水核查结论、还款表现及异常"),
            ("担保与抵质押变化", "担保人、抵质押物状态、权属/价值/保险/登记变化"),
            ("外部风险与关联事项", "涉诉、行政处罚、重大舆情、关联方变化等公开/合规来源核查"),
            ("问题、措施与跟踪安排", "风险信号、已采取措施、责任人、完成时限和升级情况"),
        ],
        "checklist": ["经营主体和经营场所状态已检查", "贷款资金用途与合同约定已核对", "销售回款和还款表现已核查", "担保及抵质押状态已核查（如适用）", "重大经营变化和外部风险已了解", "发现问题已记录并明确跟踪责任人", "需要升级的事项已按流程报告", "贷后检查记录已归档"],
        "signals": ["贷款资金流向与约定用途不一致", "经营停滞、停产或主要订单明显下滑", "回款异常或还款来源明显弱化", "担保物/担保人状况发生重大变化", "客户隐瞒重大经营、涉诉或关联关系变化"],
        "caution": "检查频率、风险分类、预警和处置动作以本行贷后管理制度及系统规则为准。",
    },
    "客户走访与营销记录": {
        "group": "客户经营", "description": "把走访事实、客户需求、产品沟通和后续动作整理成结构化记录。",
        "fields": [
            ("客户代号/行业", "使用虚构代号，不填写真实姓名、电话、地址或证件号"),
            ("走访时间与渠道", "日期、现场/电话/线上等渠道"),
            ("走访目的", "维护关系、了解经营、产品咨询、贷后回访等"),
            ("客户经营与需求摘要", "客户主动提供的非敏感摘要、经营变化和融资/结算需求"),
            ("沟通内容与已告知事项", "产品介绍、费用/利率披露、风险提示、待确认事项"),
            ("客户反馈与待办", "客户意见、待补材料、内部协同事项"),
            ("下一步计划", "行动事项、责任岗位、计划完成时间"),
        ],
        "checklist": ["走访目的和时间已记录", "客户需求和经营情况已区分事实与判断", "产品关键信息和风险提示已记录", "客户反馈和待办事项已明确", "后续责任人和时间已明确"],
        "signals": ["客户诉求与产品适用范围不匹配", "客户对费用、利率或产品风险理解存在偏差", "客户资料来源或授权边界不清"],
        "caution": "营销建议不得夸大收益或隐瞒风险；产品适当性、销售话术和信息披露以本行制度为准。",
    },
    "客户投诉受理与跟踪": {
        "group": "消保与服务", "description": "结构化记录诉求、事实、待核事项、处理进展和升级路径。",
        "fields": [
            ("投诉编号/客户代号", "使用虚构编号，不填写客户真实身份或联系方式"),
            ("受理时间与渠道", "日期、网点/电话/线上等渠道"),
            ("涉及产品或服务", "产品/业务环节及发生时间"),
            ("客户主要诉求", "尽量按客户原意摘要，区分事实与主张"),
            ("已核实事实与证据来源", "业务记录、沟通记录、系统日志等可核验来源（不粘贴敏感信息）"),
            ("待核实事项", "尚未确认的事实、责任部门或补充材料"),
            ("已采取措施与沟通安排", "已采取措施、客户告知内容、下一次反馈安排"),
            ("升级与审核情况", "是否需按内部机制升级、审核岗位及处理状态"),
        ],
        "checklist": ["客户诉求已准确记录", "涉及业务和时间线已确认", "事实、主张和待核事项已区分", "相关记录和证据来源已核查", "客户沟通安排已明确", "复杂或重大投诉已按内部机制升级", "对外回复已经适当审核"],
        "signals": ["涉及重大权益影响或群体性风险", "事实争议复杂或涉及监管关注", "客户诉求超出经办岗位权限", "拟对外承诺事项未经核实或审核"],
        "caution": "不得在未经核实或授权的情况下对客户作出责任认定、赔付承诺或最终处理结论。",
    },
}


def load_policies(path: Path = DATA_FILE) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        policies = json.load(fh)
    if not isinstance(policies, list) or not policies:
        raise ValueError("data/policies.json 必须是非空制度列表")
    for policy in policies:
        for key in ("id", "title", "version", "domain", "sections"):
            if key not in policy:
                raise ValueError(f"模拟制度缺少字段：{key}")
        for section in policy["sections"]:
            if not all(key in section for key in ("id", "title", "content")):
                raise ValueError(f"{policy['title']} 存在不完整条款")
    return policies


def normalize(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", str(value or "").lower(), flags=re.UNICODE)


def active_policies(policies: list[dict]) -> list[dict]:
    return [p for p in policies if not str(p.get("status", "")).startswith("历史")]


def detect_topic(query: str, previous_topic: str | None = None) -> tuple[str | None, str]:
    text = normalize(query)
    scored = []
    for policy_id, aliases in TOPIC_ALIASES.items():
        matches = [normalize(alias) for alias in aliases if normalize(alias) in text]
        if matches:
            scored.append((max(map(len, matches)) * 2.3 + min(len(matches) - 1, 3) * .5, policy_id))
    if scored:
        scored.sort(reverse=True)
        return scored[0][1], "明确业务关键词"
    followup_hints = ("那", "还", "这", "材料", "风险", "流程", "申请", "审批", "证件", "需要", "怎么办", "如果", "是否", "业务", "额度", "核查", "处理", "资料", "办理", "怎么", "还有")
    if previous_topic and previous_topic in TOPIC_ALIASES and any(h in text for h in followup_hints):
        return previous_topic, "沿用上一轮业务主题"
    return None, "需要补充业务主题"


def infer_intent(query: str) -> str:
    text = normalize(query)
    for label in ("版本对比", "成本披露", "风险提示", "场景指导", "材料清单", "办理流程"):
        if any(normalize(term) in text for term in INTENT_TERMS[label]):
            return label
    return "制度问答"


def _bigrams(text: str) -> set[str]:
    text = normalize(text)
    return {text[i:i + 2] for i in range(len(text) - 1)}


def _section_score(query: str, section: dict, intent: str) -> float:
    q, title, content = normalize(query), normalize(section.get("title", "")), normalize(section.get("content", ""))
    if not q:
        return 0.0
    grams = _bigrams(q)
    section_grams = _bigrams(title + content)
    score = min(len(grams & section_grams) * .32, 8.0)
    if len(q) >= 4 and q in title + content:
        score += 9.0
    for hint in INTENT_SECTION_TITLE.get(intent, ()):
        if normalize(hint) in title:
            score += 4.5
    for hint in ("登记", "受理", "核验", "审批", "材料", "缺失", "调查", "还款", "用途", "受益所有人", "处理", "归档", "升级", "成本", "费用"):
        h = normalize(hint)
        if h in q and h in title:
            score += 3.5
    for hint in ("材料", "风险", "用途", "开户", "身份", "审批", "受益所有人", "还款", "投诉", "调查", "流程", "成本", "费用"):
        h = normalize(hint)
        if h in q and (h in title or h in content):
            score += 1.1
    if intent == "场景指导" and any(x in q for x in ("缺", "不足", "无法")) and any(x in title for x in ("缺失", "异常", "处理")):
        score += 7
    return round(score, 3)


def retrieve_sections(query: str, policies: list[dict], previous_topic: str | None = None, max_sections: int = 3) -> dict:
    topic, reason = detect_topic(query, previous_topic)
    intent = infer_intent(query)
    if not topic:
        return {"topic": None, "intent": intent, "reason": reason, "sources": [], "policy": None}
    eligible = [p for p in active_policies(policies) if p["id"] == topic]
    if not eligible:
        return {"topic": topic, "intent": intent, "reason": "当前没有对应的演示有效版本", "sources": [], "policy": None}
    policy = sorted(eligible, key=lambda p: str(p.get("effective_date", "")), reverse=True)[0]
    hits = []
    for sec in policy["sections"]:
        item = {"doc_id": policy["id"], "doc": policy["title"], "domain": policy["domain"], "version": policy["version"],
                "effective_date": policy.get("effective_date", "未标注"), "section_id": sec["id"], "title": sec["title"],
                "content": sec["content"], "source_type": "模拟制度", "score": _section_score(query, sec, intent)}
        hits.append(item)
    hits.sort(key=lambda x: (-x["score"], x["section_id"]))
    return {"topic": topic, "intent": intent, "reason": reason, "sources": hits[:max_sections], "policy": policy}


def list_versions(policies: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for p in policies:
        groups.setdefault(p["id"], []).append(p)
    return {pid: sorted(items, key=lambda p: str(p.get("effective_date", ""))) for pid, items in groups.items() if len(items) > 1}


def compare_versions(old: dict, new: dict) -> list[dict]:
    o = {s["id"]: s for s in old["sections"]}
    n = {s["id"]: s for s in new["sections"]}
    changes = []
    for sid in sorted(set(o) | set(n)):
        left, right = o.get(sid), n.get(sid)
        status = "新增" if left is None else "删除" if right is None else "未变化" if (left["title"], left["content"]) == (right["title"], right["content"]) else "修改"
        changes.append({"section_id": sid, "title": (right or left)["title"], "status": status,
                        "old_text": left["content"] if left else "（无该条款）", "new_text": right["content"] if right else "（无该条款）",
                        "similarity": round(SequenceMatcher(None, left["content"] if left else "", right["content"] if right else "").ratio() * 100) if left and right else None})
    return changes


def material_items(policy: dict) -> tuple[list[str], list[dict]]:
    sections = [s for s in policy["sections"] if any(t in s["title"] for t in ("申请材料", "材料清单", "资料清单", "开户材料"))]
    items = []
    for sec in sections:
        content = re.sub(r"^.*?(?:包括|如下)[：:]", "", sec["content"], count=1)
        for piece in re.split(r"[；;。]", content):
            item = piece.strip(" ：;。\n ")
            if 2 <= len(item) <= 110 and not item.startswith(("具体", "实际", "材料清单应", "发现")):
                items.append(item)
    return list(dict.fromkeys(items)), sections


def _token_terms(query: str) -> list[str]:
    lexicon = sorted({term for aliases in TOPIC_ALIASES.values() for term in aliases} | {
        "经营现金流", "第一还款来源", "资金用途", "贷款用途", "贷后检查", "受益所有人", "实际控制人", "客户身份",
        "经营场所", "申请材料", "材料清单", "综合融资成本", "费用明示", "息费披露", "贷款调查", "风险缓释",
        "投诉受理", "投诉登记", "缺失处理", "异常处理", "尽职调查", "面谈", "授权", "审批", "归档",
        "农户", "涉农", "农业", "种植", "养殖", "农产品", "个人经营贷", "消费贷", "对公开户",
        "销售回款", "库存", "订单", "纳税", "流水", "征信", "担保", "抵押", "质押", "合作机构",
    }, key=len, reverse=True)
    q = normalize(query)
    return [term for term in lexicon if normalize(term) in q]


def score_text(query: str, title: str, content: str, intent: str = "制度问答") -> float:
    q, t, c = normalize(query), normalize(title), normalize(content)
    if not q:
        return 0.0
    score = 0.0
    if len(q) >= 4 and q in t + c:
        score += 8.0
    for term in _token_terms(query):
        nt = normalize(term)
        if nt in t:
            score += 5.0 + min(len(nt), 6) * .25
        elif nt in c:
            score += 2.0 + min(len(nt), 6) * .15
    grams = _bigrams(q)
    target = _bigrams(t + c)
    if grams:
        score += min(len(grams & target) / max(1, len(grams)) * 8, 5.0)
    for hint in INTENT_SECTION_TITLE.get(intent, ()):
        if normalize(hint) in t:
            score += 2.5
    if intent == "办理流程" and any(x in q for x in ("流程", "步骤", "办理")) and "流程" in t:
        score += 9.0
    if intent == "材料清单" and any(x in q for x in ("材料", "资料", "清单")) and any(x in t for x in ("材料", "资料", "清单")):
        score += 8.0
    if intent == "风险提示" and any(x in q for x in ("风险", "异常", "疑点")) and any(x in t for x in ("风险", "异常", "核查")):
        score += 7.0
    return round(score, 3)


def chunk_text(text: str, max_chars: int = 850, overlap: int = 100) -> list[str]:
    text = re.sub(r"\r\n?", "\n", text or "").strip()
    if not text:
        return []
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n{2,}|(?<=。)\s*\n", text) if p.strip()]
    chunks, current = [], ""
    for para in paragraphs:
        while len(para) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(para[:max_chars])
            para = para[max_chars - overlap:]
        if len(current) + len(para) + 1 <= max_chars:
            current = (current + "\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks


def extract_docx_text(blob: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for p in root.findall(".//w:p", ns):
        value = "".join((node.text or "") for node in p.findall(".//w:t", ns)).strip()
        if value:
            paragraphs.append(value)
    return "\n\n".join(paragraphs)


def extract_uploaded_text(filename: str, blob: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in (".txt", ".md", ".csv"):
        return blob.decode("utf-8-sig", errors="replace")
    if suffix == ".json":
        try:
            return json.dumps(json.loads(blob.decode("utf-8-sig")), ensure_ascii=False, indent=2)
        except Exception as exc:
            raise ValueError(f"JSON 文件解析失败：{exc}") from exc
    if suffix == ".docx":
        return extract_docx_text(blob)
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("PDF 解析依赖尚未安装。请在 requirements.txt 中加入 pypdf，或先上传 DOCX/TXT/MD 文件。") from exc
        reader = PdfReader(io.BytesIO(blob))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    raise ValueError("暂不支持该文件格式，请上传 PDF、DOCX、TXT、MD 或 JSON。")


def uploaded_doc_chunks(uploaded_docs: dict[str, str]) -> list[dict]:
    rows = []
    for filename, text in uploaded_docs.items():
        for idx, chunk in enumerate(chunk_text(text), 1):
            rows.append({"doc_id": f"UPLOAD-{filename}", "doc": filename, "domain": "用户上传资料（会话临时）", "version": "未核验",
                         "effective_date": "请人工核对", "section_id": f"片段{idx}", "title": f"{filename} · 片段{idx}",
                         "content": chunk, "source_type": "会话临时上传资料", "score": 0.0})
    return rows


def retrieve_knowledge(query: str, policies: list[dict], uploaded_docs: dict[str, str] | None = None,
                       previous_topic: str | None = None, max_results: int = 5) -> dict:
    topic, reason = detect_topic(query, previous_topic)
    intent = infer_intent(query)
    qn = normalize(query)
    generic_only = any(phrase in qn for phrase in ("需要哪些材料", "需要什么材料", "有哪些材料", "准备什么材料", "怎么办", "怎么处理", "有哪些风险")) and not _token_terms(query)
    if not topic and generic_only:
        return {"topic": None, "topic_reason": "问题缺少明确业务主题", "intent": intent, "sources": [], "confidence": "不足"}
    candidates: list[dict] = []
    for p in active_policies(policies):
        if topic and p["id"] != topic:
            continue
        for sec in p["sections"]:
            candidates.append({"doc_id": p["id"], "doc": p["title"], "domain": p["domain"], "version": p["version"],
                               "effective_date": p.get("effective_date", "未标注"), "section_id": sec["id"], "title": sec["title"],
                               "content": sec["content"], "source_type": "模拟制度", "score": 0.0})
    candidates.extend(uploaded_doc_chunks(uploaded_docs or {}))
    # 公开法规摘要索引可被检索；结果明确标注为官方公开资料摘要，不冒充本行制度。
    for idx, ref in enumerate(REGULATORY_REFERENCES, 1):
        candidates.append({"doc_id": f"PUBLIC-LAW-{idx}", "doc": ref["title"], "domain": "公开监管法规索引", "version": ref["number"],
                           "effective_date": ref["date"], "section_id": "官方摘要", "title": ref["title"], "content": ref["summary"],
                           "source_type": "公开监管资料摘要", "url": ref["url"], "score": 0.0})
    for item in candidates:
        item["score"] = score_text(query, item["title"], item["content"] + " " + item.get("domain", ""), intent)
    candidates.sort(key=lambda x: (-x["score"], x["source_type"], x["doc"], x["section_id"]))
    # 低相关度时宁可提示补充，不给用户堆砌无关结果。
    hits = [x for x in candidates if x["score"] >= 1.2][:max_results]
    return {"topic": topic, "topic_reason": reason, "intent": intent, "sources": hits,
            "confidence": "较高" if hits and hits[0]["score"] >= 8 else "一般" if hits else "不足"}


def answer_question(query: str, policies: list[dict], previous_topic: str | None = None,
                    uploaded_docs: dict[str, str] | None = None) -> dict:
    q = query.strip()
    if not q:
        return {"text": "请先输入问题。", "topic": previous_topic, "sources": [], "intent": "待输入", "confidence": "不足"}
    result = retrieve_knowledge(q, policies, uploaded_docs, previous_topic)
    sources = result["sources"]
    if not sources:
        return {"text": "当前知识库没有检索到足够相关的依据。为避免误导，我不会编造制度要求，也不会猜测制度要求。\n\n请补充业务类型、产品名称、办理阶段或上传经批准公开/脱敏的演示资料后再查询。", "topic": result["topic"], "sources": [], "intent": result["intent"], "confidence": "不足"}
    lines = [f"**任务类型：{result['intent']}** · **检索把握：{result['confidence']}**", "", "我找到以下可核对的资料。请注意区分来源类型："]
    for i, src in enumerate(sources, 1):
        source_label = {"模拟制度": "项目虚构模拟制度", "会话临时上传资料": "本次会话临时上传资料（版本/效力待人工核验）", "公开监管资料摘要": "官方公开监管资料摘要（请打开原文核对）"}.get(src["source_type"], src["source_type"])
        lines.extend([f"**{i}. {src['doc']}｜{src['version']}｜{src['section_id']}**", f"来源类型：{source_label}", src["content"], ""])
    if result["topic_reason"] == "沿用上一轮业务主题":
        lines.append("_本轮沿用上一轮业务主题；如果要切换业务，请明确写出新的业务名称。_")
    lines.append("**使用边界：** 本系统只做资料定位和工作辅助，不判断客户准入、授信额度、风险等级、开户结果或可疑交易结论。重要事项请按本行制度提交有权岗位审核。")
    return {"text": "\n\n".join(lines), "topic": result["topic"], "sources": sources, "intent": result["intent"], "confidence": result["confidence"]}


def build_case_report(workflow_name: str, values: dict[str, str], checked_items: list[str], selected_signals: list[str]) -> str:
    template = WORKFLOWS[workflow_name]
    lines = [f"# 智规通客户经理工作记录｜{workflow_name}", "", f"生成日期：{date.today().isoformat()}", "", "> 演示辅助记录：非正式调查报告、授信意见、风险分类或业务审批结论。请由经办人员核实并按本行流程审核。", "", "## 一、信息记录"]
    missing = []
    for section, fields in template["fields"]:
        value = values.get(section, "").strip()
        lines.extend([f"### {section}", value if value else "待补充/待核实"])
        if not value:
            missing.append(section)
    lines.extend(["", "## 二、核对清单"])
    lines.extend([f"- [{'x' if item in checked_items else ' '}] {item}" for item in template["checklist"]])
    lines.extend(["", "## 三、待进一步核查的信号（非风险定级）"])
    lines.extend([f"- {x}" for x in selected_signals] if selected_signals else ["- 暂未勾选；不代表不存在风险。"])
    lines.extend(["", "## 四、待补充事项"])
    lines.extend([f"- {x}" for x in missing] if missing else ["- 表单字段均已填写；仍需核验原始凭证和事实。"])
    lines.extend(["", "## 五、模板边界", template["caution"], "", "## 六、后续跟进", "- 由经办人员核验资料真实性、完整性和来源。", "- 对异常或超权限事项按本行正式制度升级。", "- 将最终记录录入本行批准的业务系统或档案系统。"])
    return "\n".join(lines)


def report_markdown(messages: list[dict]) -> str:
    lines = [f"# 智规通 {APP_VERSION} 演示会话记录", "", "声明：仅供演示，制度来源和效力须人工核验。", ""]
    for msg in messages:
        lines.extend(["## " + ("用户" if msg["role"] == "user" else "智规通"), "", msg["content"], ""])
        for i, src in enumerate(msg.get("sources", []), 1):
            lines.append(f"- 依据{i}：{src['doc']}（{src['version']}，{src['effective_date']}），{src['section_id']}《{src['title']}》；来源：{src.get('source_type', '未知')}")
        lines.append("")
    return "\n".join(lines)


def render_sources(st: Any, sources: list[dict]) -> None:
    if not sources:
        st.info("没有找到足够相关的依据。")
        return
    with st.expander(f"📚 查看资料来源与原文片段（{len(sources)} 条）", expanded=False):
        for idx, src in enumerate(sources, 1):
            st.markdown(f"**{idx}. {src['doc']}｜{src['version']}｜{src['section_id']} {src['title']}**")
            st.caption(f"来源：{src.get('source_type', '未标注')} · 日期/效力：{src.get('effective_date', '未标注')}")
            st.write(src["content"])
            if src.get("url"):
                st.markdown(f"[打开官方来源原文]({src['url']})")
            if idx < len(sources):
                st.divider()



# ---------------------------------------------------------------------------
# 简洁版界面：只展示制度学习、合规流程、尽职调查三个主入口。
# 现有后端检索/文件解析/工作流数据保留，以便和旧版数据兼容。
# ---------------------------------------------------------------------------

def learning_highlights(text: str, limit: int = 6) -> list[str]:
    """仅提取原文中疑似重要的句子；不将关键词提取冒充 AI 解读。"""
    raw = re.split(r"(?<=[。！？；;])\s*|\n{1,}", text)
    triggers = ("应当", "必须", "不得", "严禁", "应", "负责", "调查", "核实", "审查", "审批", "留存", "保存", "报告", "风险", "尽职")
    scored = []
    for index, part in enumerate(raw):
        line = re.sub(r"\s+", " ", part).strip()
        if not 12 <= len(line) <= 330:
            continue
        matches = sum(bool(term in line) for term in triggers)
        if matches:
            scored.append((-matches, index, line))
    # 先找相关性较高的句子，再按照原文顺序展示。
    selected = sorted(sorted(scored)[:limit], key=lambda row: row[1])
    return list(dict.fromkeys(item[2] for item in selected))


def learning_headings(text: str, limit: int = 12) -> list[str]:
    """提取明显的章节/条标题，不推断未出现的章节。"""
    pattern = re.compile(r"^(?:第[一二三四五六七八九十百零〇0-9]+[章节条]|[一二三四五六七八九十]+[、.]|[0-9]+[.、）)])")
    headings = []
    for row in text.splitlines():
        line = re.sub(r"\s+", " ", row).strip()
        if 3 <= len(line) <= 90 and pattern.match(line):
            headings.append(line)
    return list(dict.fromkeys(headings))[:limit]


def doc_hits(filename: str, text: str, question: str, limit: int = 3) -> list[dict]:
    hits = []
    for i, chunk in enumerate(chunk_text(text), 1):
        score = score_text(question, filename, chunk, infer_intent(question))
        if score >= 1.2:
            hits.append({"doc": filename, "section_id": f"原文片段 {i}", "content": chunk,
                         "source_type": "本次会话上传资料", "score": score,
                         "version": "未核验", "effective_date": "待人工核对", "title": "原文摘录"})
    hits.sort(key=lambda item: -item["score"])
    return hits[:limit]


def simple_checklist_report(name: str, checked: list[str], signals: list[str], notes: str) -> str:
    template = WORKFLOWS[name]
    out = [f"# 智规通 · 尽职调查学习核对表", "", f"业务类型：{name}",
           f"生成日期：{date.today().isoformat()}", "",
           "> 公开演示用途；通用工作参考，不是本行正式调查表，也不能证明已尽职。", "",
           "## 一、核对事项"]
    for item in template["checklist"]:
        out.append(f"- [{'x' if item in checked else ' '}] {item}")
    out.extend(["", "## 二、提示的待核风险线索"])
    out.extend([f"- {item}" for item in signals] or ["- 暂未选择，不代表不存在风险。"])
    out.extend(["", "## 三、补充学习笔记", notes.strip() or "（未填写）", "",
                "## 四、使用边界", template["caution"],
                "实际业务须由经办人员核实证据，按照本行有效制度履行调查、复核和审批。"])
    return "\n".join(out)


def run_app() -> None:
    import hashlib
    import streamlit as st

    st.set_page_config(page_title="智规通｜制度学习与合规尽调", page_icon="📘",
                       layout="centered", initial_sidebar_state="collapsed")
    st.markdown("""
    <style>
      .block-container {max-width:890px;padding-top:1.45rem;padding-bottom:2.3rem}
      .main .block-container h3 {padding-top:.5rem}
      .zt-hero {background:linear-gradient(115deg,#173e55,#24617a);color:#fff;
                border-radius:16px;padding:20px 25px;margin:1px 0 17px}
      .zt-hero h1 {font-size:1.85rem;margin:0;color:#fff;letter-spacing:.02em}
      .zt-hero p {margin:5px 0 0;color:#e2eff5;font-size:.94rem}
      div[data-testid="stFileUploader"] {border-radius:12px}
      div[data-testid="stExpander"] {border-radius:10px}
      div[data-testid="stMetric"] {border-radius:10px}
      .zt-tip {font-size:.85rem;color:#596979;margin:.4rem 0 1rem}
      footer {visibility:hidden}
    </style>
    <div class="zt-hero"><h1>📘 智规通</h1><p>读懂银行制度 · 查清合规流程 · 做好尽职调查</p></div>
    """, unsafe_allow_html=True)

    # 在公开网站上持续展示使用边界，但避免占据过大的头部空间。
    st.caption("🔒 公开演示：仅使用公开、模拟或获准外传的非敏感资料。不得上传总行保密文件或真实客户资料。")

    try:
        policies = load_policies()
    except Exception as exc:
        st.error(f"演示资料加载失败：{exc}")
        st.info("请检查仓库中的 data/policies.json 是否仍然存在。")
        st.stop()

    if "uploaded_docs" not in st.session_state:
        st.session_state.uploaded_docs = {}
    if "last_upload_id" not in st.session_state:
        st.session_state.last_upload_id = ""
    if "upload_widget_version" not in st.session_state:
        st.session_state.upload_widget_version = 0
    if "study_result_query" not in st.session_state:
        st.session_state.study_result_query = ""
    if "minimal_page" not in st.session_state:
        st.session_state.minimal_page = "📖 学制度"

    def open_page(name: str, workflow: str | None = None) -> None:
        st.session_state.minimal_page = name
        if workflow is not None:
            st.session_state.diligence_workflow = workflow

    page = st.radio("选择功能", ["📖 学制度", "🧭 查流程", "✅ 做尽调"],
                    horizontal=True, key="minimal_page", label_visibility="collapsed")
    st.divider()

    if page == "📖 学制度":
        st.subheader("学制度")
        st.caption("上传一份文件，先看重点，再按问题查找相关原文。")
        permitted = st.checkbox("我确认资料可以用于本公网演示站，不含内部保密或客户敏感信息。",
                                key="upload_confirm")
        uploaded = st.file_uploader("选择文件", type=["pdf", "docx", "txt", "md", "json"],
                                    disabled=not permitted,
                                    key=f"minimal_uploaded_file_{st.session_state.upload_widget_version}",
                                    help="仅支持可提取文本的文件；扫描版 PDF 暂无法直接识别。")
        if uploaded is not None and permitted:
            blob = uploaded.getvalue()
            if len(blob) > 10 * 1024 * 1024:
                st.error("演示版单个文件请控制在 10MB 以内。")
            else:
                identifier = f"{uploaded.name}:{hashlib.sha256(blob).hexdigest()}"
                if identifier != st.session_state.last_upload_id:
                    try:
                        value = extract_uploaded_text(uploaded.name, blob)
                        if not value.strip():
                            st.warning("没有提取到文字。若是扫描版 PDF，请先使用经过批准的工具处理为可搜索文本。")
                        else:
                            st.session_state.uploaded_docs = {uploaded.name: value}
                            st.session_state.last_upload_id = identifier
                            st.session_state.study_result_query = ""
                            st.success("文件已经读取，可以开始学习。")
                    except Exception as exc:
                        st.error(f"读取失败：{exc}")

        current_docs = st.session_state.uploaded_docs
        if current_docs:
            filename, fulltext = next(iter(current_docs.items()))
            st.markdown(f"**正在学习：{filename}**")
            st.caption(f"已提取约 {len(fulltext):,} 个字符 · 仅在当前会话中临时使用 · 文件效力需自行核实")
            if st.button("移除当前文件", key="clear_study_file"):
                st.session_state.uploaded_docs = {}
                st.session_state.last_upload_id = ""
                st.session_state.study_result_query = ""
                st.session_state.upload_widget_version += 1
                st.rerun()
            highlights = learning_highlights(fulltext)
            if highlights:
                st.markdown("#### 先看这些原文重点")
                st.caption("以下为按关键词选取的原文句子，不是 AI 摘要或合规结论。")
                for i, sentence in enumerate(highlights, 1):
                    st.markdown(f"**{i}.** {sentence}")
            else:
                st.info("未找到明显的重点表述，你可以在下面按问题搜索原文。")
            headings = learning_headings(fulltext)
            if headings:
                with st.expander("查看文件章节线索"):
                    for title in headings:
                        st.write(title)
            notes = "# 制度学习摘录｜" + filename + "\n\n" + "\n\n".join(f"{i}. {x}" for i,x in enumerate(highlights, 1))
            st.download_button("⬇️ 下载学习摘录", notes.encode("utf-8"),
                               file_name="智规通_制度学习摘录.md", mime="text/markdown", key="study_download")
        else:
            st.info("还没有上传文件。你可以先用下面的搜索框，体验公开监管资料和模拟制度检索。")

        st.markdown("#### 找相关条款")
        with st.form("minimal_study_search"):
            question = st.text_input("你想了解什么？",
                                     placeholder="例如：贷款尽职调查要核实哪些内容？",
                                     max_chars=300)
            submitted = st.form_submit_button("查找原文", type="primary", use_container_width=True)
        if submitted:
            st.session_state.study_result_query = question.strip()
        query = st.session_state.study_result_query
        if query:
            if current_docs:
                filename, fulltext = next(iter(current_docs.items()))
                references = doc_hits(filename, fulltext, query)
            else:
                references = retrieve_knowledge(query, policies)["sources"]
            if references:
                st.caption(f"找到 {len(references)} 处相关材料。请打开并结合上下文核对。")
                for i, source in enumerate(references, 1):
                    label = source.get("doc", "资料")
                    section_id = source.get("section_id", "")
                    with st.expander(f"{i}. {label}｜{section_id}", expanded=(i == 1)):
                        st.write(source.get("content", ""))
                        st.caption("来源：" + source.get("source_type", "未标注") +
                                   " · 版本：" + source.get("version", "待核实"))
                        if source.get("url"):
                            st.markdown(f"[查看监管部门公开原文]({source['url']})")
            else:
                st.warning("没有查到足够相关的原文。可以换个关键词，或补充业务类型及办理环节。")
        with st.expander("几个常见制度词，怎么理解？"):
            st.markdown("**应当 / 必须**：一般表达义务要求，需核对适用对象、条件与例外。")
            st.markdown("**不得 / 严禁**：一般表达禁止要求，特别注意禁止的具体行为。")
            st.markdown("**尽职调查**：重点是按适用要求开展核实，并保留充分、可复核的过程与证据。")
            st.markdown("**按权限审批**：需核对本行现行授权、审批岗位和流程，不能由系统代为判断。")
            st.caption("这些是通用学习提示，不代表对某份具体条款的权威解释。")

    elif page == "🧭 查流程":
        st.subheader("查合规流程")
        st.caption("选择业务，先看通用处理思路，再核对关键事项。")
        names = list(WORKFLOWS)
        workflow = st.selectbox("业务类型", names, key="flow_workflow")
        template = WORKFLOWS[workflow]
        st.caption(template["description"])
        st.markdown("#### 通用办理思路")
        steps = ["确认业务类型，查找现行适用制度", "明确岗位职责、授权和业务办理条件",
                 "按照适用要求开展核验并记录证据来源", "对异常或疑点补充调查、按权限报告",
                 "整理办理记录，按本行流程复核和归档"]
        for i, step in enumerate(steps, 1):
            st.markdown(f"**{i:02d}**　{step}")
        st.markdown("#### 重点核对事项")
        for line in template["checklist"]:
            st.markdown(f"- {line}")
        with st.expander("容易忽视的风险线索"):
            for signal in template["signals"]:
                st.markdown(f"- {signal}")
        st.caption("⚠️ 此处是通用学习提纲，不等于本行正式、完整的合规流程。")
        st.button("下一步：打开尽调核对表", type="primary", use_container_width=True,
                  on_click=open_page, args=("✅ 做尽调", workflow))

    else:
        st.subheader("做尽调")
        st.caption("按业务场景逐项检查，查看遗漏，导出个人学习核对表。")
        names = list(WORKFLOWS)
        workflow = st.selectbox("业务类型", names, key="diligence_workflow")
        template = WORKFLOWS[workflow]
        workflow_id = names.index(workflow)
        checked = []
        for i, label in enumerate(template["checklist"]):
            if st.checkbox(label, key=f"simple_check_{workflow_id}_{i}"):
                checked.append(label)
        st.progress(len(checked)/len(template["checklist"]),
                    text=f"已勾选 {len(checked)} / {len(template['checklist'])} 项（仅代表自查进度）")
        with st.expander("需要继续核实的疑点（可选）"):
            signals = []
            for i, signal in enumerate(template["signals"]):
                if st.checkbox(signal, key=f"simple_signal_{workflow_id}_{i}"):
                    signals.append(signal)
        notes = st.text_area("学习备注（可选）", placeholder="例如：本次还需要补查哪些资料？请勿输入真实客户信息。",
                             height=90, key=f"simple_notes_{workflow_id}")
        output = simple_checklist_report(workflow, checked, signals, notes)
        st.download_button("⬇️ 下载尽调学习核对表", output.encode("utf-8"),
                           file_name="智规通_尽调学习核对表.md", mime="text/markdown",
                           use_container_width=True)
        st.caption("⚠️ 勾选全部事项也不代表完成尽职调查。需以本行现行制度、实际证据和审核结果为准。")

    st.divider()
    with st.expander("📚 公开监管参考与使用说明"):
        st.caption("以下是公开监管文件的来源入口，不等于本行内部制度，也不意味着适用于所有业务场景。")
        for ref in REGULATORY_REFERENCES:
            st.markdown(f"- [{ref['title']}]({ref['url']})")
        st.markdown("**当前版本的能力**：可提取文本、识别疑似重点句、检索相关原文和使用通用清单。")
        st.markdown("**尚未具备的能力**：没有接入大语言模型，不具备真正的逐条白话智能讲解，也不能自动认定流程合规或调查充分。")
        st.markdown("**资料安全**：资料仅用于当前会话的临时内存处理，当前网站是公开托管的演示环境；勿上传保密制度、客户信息或真实尽调资料。")
    st.caption(f"智规通 {APP_VERSION} · 制度学习与工作辅助演示 · 非正式合规意见")


if __name__ == "__main__":
    run_app()
