"""智规通 v3.2｜银行制度学习与合规工作台（演示版）

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
APP_VERSION = "v3.2 升级演示版"
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
# 升级版：保留三大主入口，并接入依据问答、版本对比和详细工作记录。
# 采用原有规则检索及工作流数据，不声称已经连接大语言模型。
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


def version_comparison_markdown(old: dict, new: dict, changes: list[dict], changed_only: bool = True) -> str:
    """Export source-grounded comparison without inventing policy impact."""
    lines = ["# 智规通 · 模拟制度版本对比", "",
             f"制度：{new['title']}",
             f"旧版：{old['version']}（{old.get('effective_date', '未标注')}）",
             f"新版：{new['version']}（{new.get('effective_date', '未标注')}）", "",
             "> 本对比仅对项目内模拟文本进行逐条比较，未判断制度效力或实际业务影响。", ""]
    for c in changes:
        if changed_only and c["status"] == "未变化":
            continue
        lines.extend([f"## {c['section_id']} {c['title']}｜{c['status']}", "",
                      "**旧版原文：**", c["old_text"], "", "**新版原文：**", c["new_text"], ""])
    return "\n".join(lines)


def pending_check_items(template: dict, checked: list[str], signals: list[str],
                        fields: dict[str, str] | None = None) -> list[str]:
    """Prompt a human to check gaps; selection does not establish compliance."""
    followups = [f"待核对：{item}" for item in template["checklist"] if item not in checked]
    followups.extend(f"需核实疑点：{item}" for item in signals)
    if fields is not None:
        followups.extend(f"待补充记录：{label}" for label, _ in template["fields"] if not fields.get(label, "").strip())
    return followups


def run_app() -> None:
    import hashlib
    import streamlit as st

    st.set_page_config(
        page_title="智规通｜银行制度与合规工作台", page_icon="📘",
        layout="wide", initial_sidebar_state="collapsed",
    )
    st.markdown("""
    <style>
      .block-container {max-width:1140px;padding-top:1.4rem;padding-bottom:2.5rem}
      .zt-hero {background:linear-gradient(120deg,#112d43 0%,#245d72 76%,#327b86 100%);
          border-radius:18px;padding:27px 32px;margin-bottom:13px;color:#f8fafc}
      .zt-hero .zt-kicker {font-size:.78rem;letter-spacing:.14em;color:#c3e4e9;font-weight:650}
      .zt-hero h1 {color:#fff;font-size:2.15rem;letter-spacing:.03em;margin:.26rem 0 .38rem}
      .zt-hero p {color:#e0ebf0;font-size:.98rem;margin:0}
      div[data-testid="stExpander"] {border-radius:11px}
      div[data-testid="stMetric"] {border:1px solid #e0e8ec;border-radius:12px;padding:11px 14px}
      div[data-testid="stFileUploader"] {border-radius:11px}
      .zt-muted {color:#6a7883;font-size:.85rem}
    </style>
    <div class="zt-hero">
       <div class="zt-kicker">BANKING COMPLIANCE WORKSPACE · DEMO</div>
       <h1>📘 智规通 · 升级演示版</h1>
       <p>学制度有出处 · 查流程有路径 · 做尽调有记录 · 看修订有依据</p>
    </div>
    """, unsafe_allow_html=True)
    st.caption("🔒 **仅供参赛及学习演示**｜项目内置制度均为虚构数据；公网演示站不得上传真实客户资料或银行保密文件；当前未接入大语言模型。")

    try:
        policies = load_policies()
    except Exception as exc:
        st.error(f"制度演示资料加载失败：{exc}")
        st.stop()

    for key, default in {
        "uploaded_docs": {}, "last_upload_id": "", "upload_widget_version": 0,
        "study_result_query": "", "qa_messages": [], "qa_topic": None,
        "current_page": "📖 学制度",
    }.items():
        if key not in st.session_state:
            st.session_state[key] = default

    def open_page(target: str, workflow: str | None = None) -> None:
        st.session_state.current_page = target
        if workflow is not None:
            st.session_state.diligence_workflow = workflow

    c1, c2, c3 = st.columns(3)
    c1.metric("演示有效制度", f"{len(active_policies(policies))} 份")
    c2.metric("业务场景模板", f"{len(WORKFLOWS)} 类")
    c3.metric("可对比制度", f"{len(list_versions(policies))} 组")

    page = st.radio(
        "功能导航",
        ["📖 学制度", "🧭 查流程", "✅ 做尽调", "🔎 依据问答", "🔁 版本对比"],
        key="current_page", horizontal=True, label_visibility="collapsed",
    )
    st.divider()

    if page == "📖 学制度":
        st.subheader("制度学习与原文检索")
        st.caption("先从文件中提取重点原句，再根据关键词定位相关片段；不生成未经来源支持的解释。")
        permitted = st.checkbox(
            "我确认上传资料是公开、虚构或已获准用于公网演示的非敏感内容。",
            key="upload_confirm",
        )
        upload = st.file_uploader(
            "选择制度文件（PDF / DOCX / TXT / MD / JSON）",
            type=["pdf", "docx", "txt", "md", "json"], disabled=not permitted,
            key=f"study_upload_{st.session_state.upload_widget_version}",
            help="只支持可提取文本的PDF，扫描版PDF不支持OCR；单个文件最多10MB。",
        )
        if upload is not None and permitted:
            blob = upload.getvalue()
            file_id = f"{upload.name}:{hashlib.sha256(blob).hexdigest()}"
            if len(blob) > 10 * 1024 * 1024:
                st.error("演示版单个文件请控制在10MB以内。")
            elif file_id != st.session_state.last_upload_id:
                try:
                    extracted = extract_uploaded_text(upload.name, blob)
                    if not extracted.strip():
                        st.warning("未提取到文字。扫描版PDF请先用获批准的工具转为可搜索文本。")
                    elif len(extracted) > 400_000:
                        st.error("提取文字过长（超过40万字），演示版不处理。请拆分公开样本文件。")
                    else:
                        st.session_state.uploaded_docs = {upload.name: extracted}
                        st.session_state.last_upload_id = file_id
                        st.session_state.study_result_query = ""
                        st.success("已读取文件，可查看原句重点及检索片段。")
                except Exception as exc:
                    st.error(f"解析文件失败：{exc}")

        docs = st.session_state.uploaded_docs
        if docs:
            filename, fulltext = next(iter(docs.items()))
            st.write("**当前文件：**", filename)
            st.caption(f"共提取约 {len(fulltext):,} 字符｜在应用会话内存中处理｜文件版本和效力须人工核实")
            if st.button("🗑️ 移除当前文件", key="remove_study_file"):
                st.session_state.uploaded_docs = {}
                st.session_state.last_upload_id = ""
                st.session_state.study_result_query = ""
                st.session_state.upload_widget_version += 1
                st.rerun()
            highlights = learning_highlights(fulltext)
            if highlights:
                st.markdown("#### 原文重点摘录")
                st.caption("以下只是按关键词筛选出的原句，不是AI总结或制度解释。")
                for idx, sentence in enumerate(highlights, 1):
                    st.write(f"{idx}. {sentence}")
                highlight_md = "# 智规通 · 制度学习原文摘录\n\n" + filename + "\n\n" + "\n\n".join(
                    f"{idx}. {sentence}" for idx, sentence in enumerate(highlights, 1)
                )
                st.download_button("⬇️ 下载摘录（Markdown）", highlight_md.encode("utf-8"),
                    file_name="智规通_制度原文摘录.md", mime="text/markdown")
            else:
                st.info("这份文件没有识别出明显的义务或风险句式，可以直接检索原文。")
            headings = learning_headings(fulltext)
            if headings:
                with st.expander("查看识别到的章节标题"):
                    for h in headings:
                        st.write(h)
        else:
            st.info("尚未上传文件。仍可以检索项目内的模拟制度和公开监管资料摘要索引。")

        st.markdown("#### 按问题查找原文")
        with st.form("study_search_form"):
            query_input = st.text_input("输入想查的问题", placeholder="例如：企业贷款需要核查哪些申请材料？", max_chars=300)
            scope = st.radio("查询范围", ["当前上传文件", "项目模拟制度与监管索引"] if docs else
                             ["项目模拟制度与监管索引"], horizontal=True)
            search_clicked = st.form_submit_button("🔍 查找相关原文", type="primary")
        if search_clicked:
            st.session_state.study_result_query = query_input.strip()
            st.session_state.study_result_scope = scope
        query = st.session_state.study_result_query
        if query:
            chosen = st.session_state.get("study_result_scope", scope)
            if chosen == "当前上传文件" and docs:
                filename, fulltext = next(iter(docs.items()))
                hits = doc_hits(filename, fulltext, query)
            else:
                hits = retrieve_knowledge(query, policies)["sources"]
            if hits:
                st.caption(f"检索到 {len(hits)} 条候选证据。结果按规则匹配排序，不代表正确性保证。")
                render_sources(st, hits)
            else:
                st.warning("未找到足够相关的片段。请补充业务类型、关键条款或具体办理环节。")

    elif page == "🧭 查流程":
        st.subheader("合规流程工作指引")
        st.caption("通用步骤 + 业务专项核对，实际流程以本行现行制度和授权体系为准。")
        workflow = st.selectbox("选择业务场景", list(WORKFLOWS), key="flow_workflow")
        template = WORKFLOWS[workflow]
        st.info(template["description"])
        st.markdown("#### 通用处理路径")
        steps = [
            "识别业务类型，核对现行适用制度及岗位权限",
            "核实申请主体、真实业务需求及应提交的材料",
            "按业务要求核查事实，记录证据来源与尚待核实事项",
            "遇到异常或疑点，补充核实并按本行流程提交处理",
            "整理工作底稿，完成经办、复核、审批及归档环节",
        ]
        for i, step in enumerate(steps, 1):
            st.markdown(f"**{i:02d}　{step}**")
        x, y = st.columns([1, 1])
        with x:
            st.markdown("#### 重点核对清单")
            for item in template["checklist"]:
                st.write("• " + item)
        with y:
            st.markdown("#### 常见待核实线索")
            for signal in template["signals"]:
                st.write("• " + signal)
        st.warning(template["caution"])
        st.button("➡️ 带入此场景，开始尽调记录", type="primary", on_click=open_page,
                  args=("✅ 做尽调", workflow))

    elif page == "✅ 做尽调":
        st.subheader("尽职调查辅助台账")
        st.caption("勾选进度、标记疑点、补全调查事实、导出可复核的工作记录。所有数据仅用于演示。")
        workflows = list(WORKFLOWS)
        workflow = st.selectbox("业务场景", workflows, key="diligence_workflow")
        template = WORKFLOWS[workflow]
        workflow_id = workflows.index(workflow)
        detailed = st.radio("记录模式", ["快速核对", "详细工作记录"], horizontal=True,
                            key=f"record_mode_{workflow_id}") == "详细工作记录"
        st.markdown("#### 一、基础核对事项")
        checked = []
        for idx, item in enumerate(template["checklist"]):
            if st.checkbox(item, key=f"simple_check_{workflow_id}_{idx}"):
                checked.append(item)
        st.progress(len(checked) / len(template["checklist"]),
                    text=f"已标记核对 {len(checked)} / {len(template['checklist'])} 项（不代表审核通过）")
        st.markdown("#### 二、疑点与待核实事项")
        selected_signals = []
        with st.expander("选择已发现或待验证的疑点（可多选）"):
            for idx, item in enumerate(template["signals"]):
                if st.checkbox(item, key=f"simple_signal_{workflow_id}_{idx}"):
                    selected_signals.append(item)
        notes = st.text_area("补充说明/待办备注（非敏感信息）", max_chars=2000,
                            placeholder="例如：模拟客户A的经营场所资料仍需补充核验。", key=f"record_notes_{workflow_id}")
        field_values: dict[str, str] | None = None
        if detailed:
            st.markdown("#### 三、详细调查记录")
            st.caption("所有栏目为事实记录提示，不会自动推断授信结果或合规结论。")
            field_values = {}
            for idx, (label, hint) in enumerate(template["fields"]):
                field_values[label] = st.text_area(label, placeholder=hint, max_chars=1500,
                     height=80, key=f"detail_{workflow_id}_{idx}")
        pending = pending_check_items(template, checked, selected_signals, field_values)
        st.markdown("#### 复核前提示")
        if pending:
            st.warning(f"共有 {len(pending)} 条待继续核对/补充的事项；以下均为系统依据勾选状态提示，不是AI风险判定。")
            with st.expander("查看待办详情"):
                for task in pending:
                    st.write("• " + task)
        else:
            st.info("模板项已全部标记；这不代表尽职调查充分，仍需核查证据真实性及本行适用制度。")
        if detailed:
            out = build_case_report(workflow, field_values or {}, checked, selected_signals)
            out += "\n\n## 七、其他备注\n" + (notes.strip() or "（未填写）") + "\n"
        else:
            out = simple_checklist_report(workflow, checked, selected_signals, notes)
        with st.expander("预览导出内容"):
            st.markdown(out)
        st.download_button("⬇️ 导出工作记录（Markdown）", out.encode("utf-8"),
                           file_name="智规通_尽调工作记录.md", mime="text/markdown",
                           type="primary", use_container_width=True)
        st.caption("⚠️ 公开演示版无身份认证及正式审计功能。请勿填入客户姓名、身份证件、账号、征信及其他敏感信息。")

    elif page == "🔎 依据问答":
        st.subheader("制度依据问答")
        st.caption("多轮问题的关键词检索演示：列出可核对的原文依据，并非大模型理解、推理或正式合规答复。")
        a, b = st.columns([3, 1])
        with a:
            example = st.selectbox("快速示例", SAMPLE_QUESTIONS, key="qa_example")
        with b:
            st.write("")
            st.write("")
            use_example = st.button("使用示例提问", use_container_width=True)
        if st.button("🗑️ 清空问答历史", key="clear_qa"):
            st.session_state.qa_messages = []
            st.session_state.qa_topic = None
            st.rerun()
        for msg in st.session_state.qa_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg["role"] == "assistant" and msg.get("sources"):
                    render_sources(st, msg["sources"])
        prompt = st.chat_input("输入一个制度或业务问题，例如：小微贷款需要哪些材料？")
        q = example if use_example else prompt
        if q:
            answer = answer_question(q, policies, st.session_state.qa_topic, st.session_state.uploaded_docs)
            st.session_state.qa_messages.extend([
                {"role": "user", "content": q},
                {"role": "assistant", "content": answer["text"], "sources": answer["sources"]},
            ])
            st.session_state.qa_topic = answer["topic"]
            st.rerun()
        if st.session_state.qa_messages:
            st.download_button("⬇️ 导出问答记录（Markdown）",
                report_markdown(st.session_state.qa_messages).encode("utf-8"),
                file_name="智规通_问答检索记录.md", mime="text/markdown")

    else:  # 版本对比
        st.subheader("模拟制度新旧版本对比")
        st.caption("逐条对比项目内置模拟制度的标题和正文变化。只显示文本差异，不自动推断业务影响或法律效力。")
        groups = list_versions(policies)
        if not groups:
            st.info("当前制度库暂无可对比的双版本文件。")
        else:
            ids = list(groups)
            chosen_id = st.selectbox("选择要比较的制度", ids,
                format_func=lambda x: groups[x][-1]["title"])
            versions = groups[chosen_id]
            old, new = versions[0], versions[-1]
            st.caption(f"旧版：{old['version']}（{old.get('effective_date', '未注明')}）｜新版：{new['version']}（{new.get('effective_date', '未注明')}）")
            changes = compare_versions(old, new)
            changed = [r for r in changes if r["status"] != "未变化"]
            cols = st.columns(4)
            for col, (label, count) in zip(cols, [
                ("新增", sum(c["status"] == "新增" for c in changes)),
                ("删除", sum(c["status"] == "删除" for c in changes)),
                ("修改", sum(c["status"] == "修改" for c in changes)),
                ("未变化", sum(c["status"] == "未变化" for c in changes)),
            ]):
                col.metric(label, count)
            only_changed = st.checkbox("仅查看发生变化的条款", value=True)
            for item in changes:
                if only_changed and item["status"] == "未变化":
                    continue
                with st.expander(f"{item['section_id']} {item['title']}　｜　{item['status']}", expanded=False):
                    left, right = st.columns(2)
                    with left:
                        st.markdown("**旧版原文**")
                        st.write(item["old_text"])
                    with right:
                        st.markdown("**新版原文**")
                        st.write(item["new_text"])
                    if item["similarity"] is not None:
                        st.caption(f"机器文本相似度：{item['similarity']}%（不是实质性影响程度）")
            if not changed:
                st.success("这组演示制度未发现条款文本变化。")
            comparison_md = version_comparison_markdown(old, new, changes, only_changed)
            st.download_button("⬇️ 导出版本对比（Markdown）", comparison_md.encode("utf-8"),
                file_name="智规通_制度版本对比.md", mime="text/markdown")

    st.divider()
    with st.expander("📚 公开监管法规参考及使用边界"):
        st.caption("以下为原项目的公开监管文件链接与摘要索引。适用性、有效性及原文内容应以监管部门现行发布为准。")
        for ref in REGULATORY_REFERENCES:
            st.markdown(f"- [{ref['title']}]({ref['url']}) · {ref['number']}")
        st.markdown("**已具备：**模拟制度检索、会话内上传、9类工作流、工作记录导出、模拟制度版本对比、多轮规则检索。")
        st.markdown("**未具备：**大语言模型、真实企业资料自动核验、银行身份授权、审计日志、行内系统连接和正式合规判断。")
        st.caption("任何正式落地需经所属银行的信息安全、数据合规及业务管理审批。")
    st.caption(f"智规通 {APP_VERSION}｜Python + Streamlit｜规则检索与结构化工作辅助原型")


if __name__ == "__main__":
    run_app()
