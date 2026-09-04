import type { Metric, Scenario } from './types'

export const scenarios: Scenario[] = [
  { id:'A', group:'取消与变更', name:'条款内免费取消', goal:'验证确定性退款', query:'帮我取消明天去杭州的酒店。', conclusion:'可以免费取消', money:['预计退回','¥688'], fee:['取消费','¥0'], status:'需要你确认', update:'确认后立即提交退款', action:'确认取消并申请退款', route:'确定性交易', risk:'L1', planTitle:'免费取消并原路退款', planCopy:'确认后立即取消订单，预计退回 ¥688，不收取消费。', impact:'订单将取消', riskNote:'取消成功后订单不可恢复。', resultTitle:'取消与退款申请已提交', afterTitle:'等待原路退款', resultCopy:'无需重复操作，退款状态更新后会在这里同步。', trace:[['LLM','识别取消退款意图'],['READ Tool','读取订单与政策快照'],['规则引擎','计算退款 ¥688，扣费 ¥0'],['WRITE Gate','核验确认令牌与订单版本'],['交易 Tool','取消订单并创建退款单']] },
  { id:'B', group:'取消与变更', name:'明确扣费取消', goal:'验证损失透明', query:'今天不去了，取消要扣多少钱？', conclusion:'可以取消，但会扣除首晚房费', money:['预计退回','¥600'], fee:['取消费','¥600'], status:'需要你选择', update:'报价 10 分钟内有效', action:'接受扣费并取消', route:'确定性交易', risk:'L1', planTitle:'接受 ¥600 取消费并退款', planCopy:'确认后取消订单，扣除首晚房费 ¥600，预计退回 ¥600。', impact:'订单取消，扣费 ¥600', riskNote:'提交后订单不可恢复；当前报价 10 分钟内有效。', resultTitle:'扣费取消申请已提交', afterTitle:'等待剩余款项退回', resultCopy:'退款将按原支付路径处理，无需重复申请。', trace:[['LLM','识别扣费查询与取消意图'],['READ Tool','读取订单版本'],['规则引擎','命中阶梯扣费档'],['WRITE Gate','绑定报价与用户确认'],['交易 Tool','提交扣费取消']] },
  { id:'F', group:'取消与变更', name:'不可取消例外协商', goal:'推荐演示 · 验证外部协同', query:'临时有事去不了了，酒店说不能退，能帮我争取吗？', conclusion:'不能直接退款，可以替你发起协商', money:['订单金额','¥1,280'], fee:['当前可直接退','¥0'], status:'提交前确认', update:'预计明天 14:00 前首次回复', action:'确认提交协商', route:'供应商协同', risk:'L2', planTitle:'申请例外退款协商', planCopy:'平台代你向酒店或供应商争取部分退款、免费改期等可行方案。', impact:'暂不取消订单', riskNote:'协商结果可能为部分退款、免费改期或拒绝，不承诺成功。', resultTitle:'协商请求已提交', afterTitle:'等待酒店或供应商回复', resultCopy:'无需重复联系，结果返回后会在这里更新。', trace:[['LLM','确认原因和期望结果'],['READ Tool','核对不可取消政策'],['规则引擎','禁止直接退款，允许例外协商'],['协同 Tool','创建供应商协商单'],['状态机','进入外部等待并设置 SLA']] },
  { id:'I', group:'取消与变更', name:'日期或房型改错', goal:'验证替代方案', query:'日期订错了一天，能改吗？', conclusion:'可以改到 9 月 13 日入住', money:['需要补差','¥80'], fee:['取消对比扣费','¥300'], status:'需要你确认', update:'报价 10 分钟内有效', action:'补 ¥80 并确认改期', route:'确定性交易', risk:'L1', planTitle:'改至 9 月 13 日入住', planCopy:'补差 ¥80，确认后提交订单日期变更。', impact:'入住日期将变更', riskNote:'报价 10 分钟内有效；变更成功后原日期不可恢复。', resultTitle:'改期申请已提交', afterTitle:'等待订单变更结果', resultCopy:'变更完成后会同步新的入住日期与订单信息。', trace:[['LLM','识别日期修改'],['库存 Tool','检查目标日期'],['规则引擎','生成改期与取消对比'],['WRITE Gate','核验新日期和补差'],['交易 Tool','提交订单变更']] },
  { id:'C', group:'退款与支付', name:'已退款未到账', goal:'验证预期管理', query:'三天前说退了，怎么还没收到？', conclusion:'退款已发起，资金尚未到账', money:['退款金额','¥860'], fee:['当前阶段','渠道处理中'], status:'无需重复申请', update:'最晚 9 月 7 日 18:00', action:'查看最新进度', route:'只读查询', risk:'L1', planTitle:'继续等待原路退款', planCopy:'退款已经提交，目前无需重新申请。', impact:'订单退款已发起', riskNote:'超过预计时间仍未到账，平台会自动创建支付调查。', resultTitle:'退款状态已刷新', afterTitle:'预计最晚 9 月 7 日到账', resultCopy:'当前仍由支付渠道处理，尚未到账。', trace:[['LLM','识别退款进度查询'],['退款 Tool','读取退款单状态'],['支付 Tool','确认渠道处理中'],['状态机','设置 SLA 到期检查']] },
  { id:'J', group:'退款与支付', name:'重复扣款或押金异常', goal:'验证支付语义', query:'同一笔房费扣了两次，押金也没退。', conclusion:'目前确认一笔实扣和一笔预授权冻结', money:['实际扣款','¥1,600'], fee:['预授权冻结','¥500'], status:'财务核验中', update:'明天 18:00 前', action:'查看财务工单', route:'支付协同', risk:'L3', planTitle:'继续财务核验', planCopy:'已区分一笔实扣和一笔预授权，财务专席将核验异常交易。', impact:'暂不重复退款', riskNote:'预授权冻结不等于第二笔实扣。', resultTitle:'财务工单状态已刷新', afterTitle:'等待财务核验结论', resultCopy:'核验结果预计明天 18:00 前更新。', trace:[['LLM','识别支付异常'],['支付 Tool','读取交易事件'],['规则引擎','区分实扣与预授权'],['协同 Tool','创建财务核验工单']] },
  { id:'D', group:'履约与住宿', name:'入住前无房或加价', goal:'验证履约恢复', query:'酒店刚通知没房，让我加 300 元换房。', conclusion:'先确认今晚可住的替代方案', money:['原订单','¥780'], fee:['替代差价上限','¥140'], status:'紧急协同', update:'预计 5 分钟内接入', action:'联系紧急专员', route:'履约恢复', risk:'L3', planTitle:'由紧急专员确认替代住宿', planCopy:'优先确认今晚可住的房源，差价保障上限 ¥140。', impact:'原订单暂不取消', riskNote:'任何额外费用都会先征得你的确认。', resultTitle:'紧急专员已接入', afterTitle:'正在确认替代住宿', resultCopy:'预计 5 分钟内给出可选房源与费用方案。', trace:[['安全分类器','识别高紧急履约失败'],['房源 Tool','搜索同区域替代住宿'],['规则引擎','计算差价保障预览'],['人工协同','携带事实转紧急专员']] },
  { id:'E', group:'履约与住宿', name:'到店后无房', goal:'验证目标重排', query:'我已经在前台了，他们说没有我的房间。', conclusion:'先帮你解决今晚住哪里', money:['附近可住房源','1 家'], fee:['专员接入','约 3 分钟'], status:'最高优先级', update:'3 分钟内首次响应', action:'立即联系紧急专员', route:'紧急人工', risk:'L3', planTitle:'立即安排今晚的替代住宿', planCopy:'已找到 1 家附近可住房源，由紧急专员优先协助入住。', impact:'先保障今晚入住', riskNote:'退款与责任认定会在你安顿后继续处理。', resultTitle:'紧急住宿请求已提交', afterTitle:'专员正在联系你', resultCopy:'预计 3 分钟内首次响应，请保持电话畅通。', trace:[['安全分类器','识别用户已到店'],['状态机','目标切换为恢复住宿'],['房源 Tool','找到附近可住房源'],['人工协同','紧急专员接管']] },
  { id:'H', group:'履约与住宿', name:'描述不符或服务问题', goal:'验证证据与人工', query:'房间和图片完全不一样，还很脏，我要退款。', conclusion:'先处理当前入住问题，再核实退款责任', money:['已收材料','2 项'], fee:['赔付结果','待核实'], status:'人工审核', update:'今天 18:30 前', action:'查看服务争议工单', route:'服务争议', risk:'L3', planTitle:'继续服务争议审核', planCopy:'已继承照片与沟通记录，无需重复提交材料。', impact:'赔付金额待核实', riskNote:'审核完成前不承诺具体退款或赔付金额。', resultTitle:'服务争议工单已刷新', afterTitle:'等待审核结果', resultCopy:'预计今天 18:30 前更新处理方案。', trace:[['LLM','识别描述与卫生争议'],['证据 Tool','收集最少必要材料'],['规则引擎','优先解决当前入住'],['人工协同','创建服务争议工单']] },
  { id:'G', group:'特殊审核', name:'疾病、灾害或交通中断', goal:'验证特殊审核', query:'航班取消了，能不能凭证明免费退？', conclusion:'材料可以触发特殊审核，但不保证全额退款', money:['订单金额','¥520'], fee:['自动退款','未授权'], status:'等待审核', update:'明天 18:00 前', action:'查看审核进度', route:'特殊审核', risk:'L2', planTitle:'提交特殊事件审核', planCopy:'航班取消证明符合送审条件，将申请例外退款方案。', impact:'订单暂不自动退款', riskNote:'材料可触发审核，但不代表一定全额退款。', resultTitle:'特殊审核状态已刷新', afterTitle:'等待资格与退款方案', resultCopy:'预计明天 18:00 前更新审核结论。', trace:[['LLM','识别交通中断'],['证据 Tool','提取最少必要字段'],['规则引擎','禁止自动承诺全退'],['协同 Tool','创建特殊审核']] },
  { id:'K', group:'特殊审核', name:'跨境多供应商订单', goal:'验证责任链', query:'海外酒店说找代理，代理又让我找平台，到底谁负责？', conclusion:'平台受理并跟踪，海外供应商负责退款执行', money:['交易币种','USD'], fee:['供应商链路','2 层'], status:'跨境专席处理', update:'明天 09:00 前', action:'查看跨境工单', route:'跨境专席', risk:'L3', planTitle:'由平台继续跟进跨境退款', planCopy:'平台统一受理，跨境专席将联系海外供应商执行退款。', impact:'按原交易币种处理', riskNote:'人民币金额仅为估算，最终以原币种退款和入账汇率为准。', resultTitle:'跨境工单状态已刷新', afterTitle:'等待海外供应商回复', resultCopy:'预计明天 09:00 前更新责任确认结果。', trace:[['LLM','识别责任方争议'],['责任链 Tool','读取两层供应商'],['规则引擎','限定原币种与当地时间'],['人工协同','转跨境专席']] },
  { id:'L', group:'特殊审核', name:'企业多房部分取消', goal:'验证复杂订单阻断', query:'公司订了 8 间房，只取消其中 3 间，发票怎么处理？', conclusion:'已生成 3 间房的取消预览，需要团体专席确认', money:['预计退回','¥3,000'], fee:['预计扣费','¥300'], status:'自动写入已阻断', update:'明天 10:00 前', action:'提交团体专席确认', route:'企业专席', risk:'L3', planTitle:'提交 3 间房部分取消审核', planCopy:'预计退回 ¥3,000、扣费 ¥300，并同步核对发票影响。', impact:'其余 5 间保持不变', riskNote:'当前为预览，专席确认前不会修改订单。', resultTitle:'团体专席申请已提交', afterTitle:'等待最终取消预览', resultCopy:'预计明天 10:00 前更新退款与发票方案。', trace:[['LLM','识别部分取消与发票影响'],['拆分 Tool','读取 8 间房明细'],['权限规则','允许预览，阻断自动写入'],['人工协同','转企业团体专席']] },
]

export const scenarioGroups = [...new Set(scenarios.map((scenario) => scenario.group))]

export const metrics: Metric[] = [
  {group:'业务结果',name:'正确解决率',value:'94.8%',target:'≥96.0%',trend:'+0.7pp',status:'关注',note:'52 件与政策或权限不一致'},
  {group:'业务结果',name:'实际到账闭环率',value:'92.5%',target:'≥95.0%',trend:'+1.1pp',status:'关注',note:'支付渠道缺少终态回传'},
  {group:'效率',name:'首次有效决定时间 P50',value:'42 秒',target:'≤45 秒',trend:'−6 秒',status:'正常',note:'订单匹配提速贡献最大'},
  {group:'效率',name:'最终到账时间 P50',value:'2.1 天',target:'≤2.0 天',trend:'+0.2 天',status:'关注',note:'微信渠道处理时长上升'},
  {group:'自动化',name:'自动完成率',value:'58.7%',target:'≥60.0%',trend:'+2.4pp',status:'关注',note:'例外场景仍依赖协同'},
  {group:'体验',name:'一次解决率',value:'81.3%',target:'≥85.0%',trend:'−0.9pp',status:'风险',note:'退款进度重复进线增加'},
  {group:'体验',name:'用户操作次数',value:'1.6 次',target:'≤1.5 次',trend:'−0.1 次',status:'关注',note:'特殊审核仍有重复补材料'},
  {group:'协作',name:'供应商首次响应 P50',value:'18 分钟',target:'≤20 分钟',trend:'−3 分钟',status:'正常',note:'国内代理响应改善'},
  {group:'协作',name:'供应商 SLA 达成率',value:'87.6%',target:'≥90.0%',trend:'+1.6pp',status:'关注',note:'海外供应商拖累整体'},
  {group:'质量',name:'人工改判率',value:'4.2%',target:'≤3.0%',trend:'+0.5pp',status:'风险',note:'不可取消例外金额改判集中'},
  {group:'风险',name:'承诺失真率',value:'0.36%',target:'≤0.20%',trend:'−0.08pp',status:'风险',note:'14 件把已发起表述为已到账'},
  {group:'风险',name:'错误退款 / 重复赔付率',value:'0.03%',target:'≤0.02%',trend:'持平',status:'风险',note:'3 件与幂等或版本冲突相关'},
  {group:'风险',name:'该转人工未转率',value:'0.8%',target:'≤0.5%',trend:'−0.2pp',status:'风险',note:'支付异常与服务争议漏转'},
]

export const funnel = [
  ['有效退款案件','10,000','100%','统计起点'],
  ['首次有效决定','9,210','92.1%','−790 订单或事实不足'],
  ['方案确认 / 明确替代方案','8,420','84.2%','−790 扣费未接受或材料未补'],
  ['业务状态完成','7,110','71.1%','−1,310 协同未完成'],
  ['到账 / 结果确认','6,580','65.8%','−530 渠道处理中'],
  ['正确退款任务闭环','6,240','62.4%','−340 事实不一致或重复进线'],
]

export const badcases = [
  {type:'声称退款到账但支付状态不支持',count:14,risk:'高',stage:'回归验证',owner:'Agent 质量',sla:'剩余 6 小时'},
  {type:'L3 服务争议未及时转人工',count:8,risk:'高',stage:'修复中',owner:'Workflow',sla:'已逾期 1 天'},
  {type:'供应商协商超过首次响应 SLA',count:126,risk:'中',stage:'上线观察',owner:'供应商运营',sla:'剩余 3 天'},
  {type:'退款进度重复进线',count:204,risk:'中',stage:'归因完成',owner:'体验策略',sla:'剩余 2 天'},
  {type:'重复赔付写入',count:3,risk:'严重',stage:'关闭待审',owner:'Tool 平台',sla:'今日到期'},
]

const messageSignals: Record<string, string[]> = {
  A:['免费取消','明天','取消酒店'], B:['扣多少','扣费','取消费','退多少','首晚','今天不去'], C:['没到账','没有到账','还没收到','退款进度','退款已经提交','退了'],
  D:['通知没房','临时加价','加价换房'], E:['前台','已经到店','到店无房','没有房间'], F:['不能退','不可取消','争取','协商','临时有事'],
  G:['航班取消','疾病','灾害','证明'], H:['很脏','图片不一样','描述不符'], I:['日期订错','房型订错','改日期','改房型','改名'],
  J:['扣了两次','重复扣款','押金','预授权'], K:['海外酒店','代理','跨境','谁负责'], L:['公司订','间房','部分取消','发票','团体'],
}

export function matchScenario(message: string): Scenario {
  const normalized = message.replace(/\s/g, '').toLowerCase()
  const ranked = Object.entries(messageSignals).map(([id, signals]) => ({
    id,
    score: signals.filter((signal) => normalized.includes(signal.replace(/\s/g, '').toLowerCase())).length,
  })).sort((a, b) => b.score - a.score)
  return scenarios.find((scenario) => scenario.id === (ranked[0]?.score ? ranked[0].id : 'F')) ?? scenarios[0]
}
