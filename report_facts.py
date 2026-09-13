from __future__ import annotations
from typing import Any
import math
import pandas as pd

def _missing(v):
    return v is None or (isinstance(v,float) and (math.isnan(v) or math.isinf(v)))

def _j(v):
    if isinstance(v,pd.DataFrame): return v.to_dict(orient="records")
    if isinstance(v,pd.Series): return v.to_dict()
    if isinstance(v,dict): return {str(k):_j(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [_j(x) for x in v]
    if isinstance(v,float) and (math.isnan(v) or math.isinf(v)): return None
    return v

def build_report_facts(*, baseline:dict, scenario:dict|None=None, validation:dict|None=None,
                       records:list[dict]|None=None, snapshot_id:str="", question:str="")->dict:
    bd=(baseline or {}).get("data") or {}
    summary=bd.get("summary")
    nodes=bd.get("nodes")
    if summary is None: summary=[]
    if nodes is None: nodes=[]
    if hasattr(summary,"to_dict"): summary=summary.to_dict(orient="records")
    if hasattr(nodes,"to_dict"): nodes=nodes.to_dict(orient="records")
    request=(baseline or {}).get("request") or {}
    fact_index={}
    def put(fid,value,unit=None,note=None):
        fact_index[fid]={"value":_j(value),"unit":unit,"note":note}
        return fid

    scope=[]
    for i,s in enumerate(summary):
        mat=str(s.get("material") or f"material_{i+1}")
        scope.append({"enterprise":s.get("enterprise"),"material":mat,
                      "year":next((r.get("year") for r in (records or []) if r.get("material")==mat and r.get("year")),None),
                      "question":question,"scope":"上游原材料供应链",
                      "data_identity":(baseline or {}).get("data_identity") or {}})
        put(f"baseline.{mat}.prwi",s.get("PRWI"))
        put(f"baseline.{mat}.known_risk",s.get("KnownRisk"))
        put(f"baseline.{mat}.coverage",s.get("Coverage"),"share")
        put(f"baseline.{mat}.scored_coverage",s.get("scored_coverage"),"share")
        put(f"baseline.{mat}.unknown_share",s.get("unknown_share_U"),"share")
        put(f"baseline.{mat}.path.ws",s.get("path_contrib_WS"))
        put(f"baseline.{mat}.path.dr",s.get("path_contrib_DR"))
        put(f"baseline.{mat}.path.sv",s.get("path_contrib_SV"))

    node_rows=[]
    for n in nodes:
        mat=str(n.get("material") or "material"); nid=str(n.get("node_id") or "node")
        row=dict(n)
        row["fact_ids"]={
            "risk":put(f"nodes.{mat}.{nid}.risk",n.get("R")),
            "contribution":put(f"nodes.{mat}.{nid}.contribution",n.get("C")),
            "contribution_share":put(f"nodes.{mat}.{nid}.contribution_share",n.get("contribution_share"),"share"),
            "weight":put(f"nodes.{mat}.{nid}.weight",n.get("weight"),"share"),
        }
        node_rows.append(row)

    confirmed=[]
    req_mats={m.get("material"):m for m in request.get("materials",[])}
    for r in records or []:
        mat=str(r.get("material") or "")
        unknown=bool(r.get("unknown_flag")) or str(r.get("node_name") or "").lower()=="unknown"
        item={k:r.get(k) for k in [
            "enterprise","material","node_id","node_name","purchase_weight","purchase_quantity","purchase_unit",
            "procurement_basis","year","WS","WS_unit","SV","SV_unit","DR","BWD","DYS","DYS_unit","CTS","OA",
            "theta_WS","theta_DR","theta_SV","source_type","confidence","data_origin","is_simulation",
            "human_confirmed","unknown_flag","evidence"
        ]}
        item["unknown_flag"]=unknown
        confirmed.append(item)
    adopted_parameters=[]
    for mat,m in req_mats.items():
        adopted_parameters.append({
            "material":mat,"theta":request.get("theta"),"material_params":m.get("material_params"),
            "unknown_share":m.get("U"),
            "nodes":[{k:n.get(k) for k in ["node_id","node_name","W","WS","WS_unit","SV","SV_unit","DR","BWD","DYS","DYS_unit","CTS","OA","reference_period"]} for n in m.get("nodes",[])]
        })

    scenario_fact=None
    if scenario and scenario.get("data") is not None:
        d=_j(scenario.get("data"))
        typ=d.get("scenario_type")
        scenario_fact={"status":scenario.get("status"),"scenario_type":typ,"data":d,"warnings":scenario.get("warnings") or [],
                       "sources":scenario.get("source_details") or [],"assumptions":scenario.get("assumptions") or [],
                       "baseline_input_hash":scenario.get("baseline_input_hash")}
        for k,v in d.items():
            if isinstance(v,(str,int,float)) or v is None:
                put(f"scenario.{typ}.{k}",v)

    quality={
        "proxy_fields":(baseline or {}).get("proxy_fields") or [],
        "assumptions":(baseline or {}).get("assumptions") or [],
        "data_identity":(baseline or {}).get("data_identity") or {},
        "validation":validation or {},
        "warnings":(baseline or {}).get("warnings") or [],
        "data_gaps":(baseline or {}).get("data_gaps") or [],
    }
    charts=[
        {"chart_id":"fig1_procurement","title":"本次采购结构图","condition":"always_if_records"},
        {"chart_id":"fig2_paths","title":"三路径风险贡献图","condition":"baseline_available"},
        {"chart_id":"fig3_nodes","title":"节点贡献与管理优先级图","condition":"baseline_available"},
        {"chart_id":"fig4_scenario","title":"基准与情景/供应缺口对比图","condition":"scenario_if_run"},
    ]
    return {
        "meta":{
            "run_id":baseline.get("run_id"),"snapshot_id":snapshot_id,"input_hash":baseline.get("input_hash"),
            "engine_version":baseline.get("engine_version"),"formula_version":baseline.get("formula_version"),
            "data_version":baseline.get("data_version"),
        },
        "scope":scope,
        "confirmed_inputs":{"records":confirmed,"adopted_parameters":adopted_parameters},
        "baseline":{"summary":_j(summary)},
        "nodes":_j(node_rows),
        "scenarios":scenario_fact,
        "sensitivity":{"status":"not_run","note":"当前第一阶段未完成独立敏感性分析时，不宣称结果稳健。"},
        "quality":_j(quality),
        "sources":_j((baseline or {}).get("source_details") or []),
        "charts":charts,
        "validation":{"integrity_checks":_j((baseline or {}).get("integrity_checks") or [])},
        "fact_index":fact_index,
    }

def _pct_text(v):
    try:
        if v is None: return "不可计算"
        return f"{float(v)*100:.1f}%"
    except Exception:
        return "不可计算"

def _num_text(v,n=3):
    try:
        if v is None: return "不可计算"
        return f"{float(v):.{n}f}"
    except Exception:
        return "不可计算"

def fallback_structured_report(facts:dict)->dict:
    """Enterprise-readable deterministic fallback.

    Fact ids are retained only for internal traceability; visible text never exposes backend field names.
    """
    scopes=facts.get("scope") or []
    summaries=(facts.get("baseline") or {}).get("summary") or []
    nodes=facts.get("nodes") or []
    actions=[]; executive=[]; baseline_findings=[]; node_findings=[]; limitations=[]
    for s in summaries:
        mat=str(s.get("material") or "原材料")
        total=s.get("PRWI")
        paths={"长期水资源紧张":s.get("path_contrib_WS") or 0,
               "历史干旱暴露":s.get("path_contrib_DR") or 0,
               "季节性供水波动":s.get("path_contrib_SV") or 0}
        path_sum=sum(float(v or 0) for v in paths.values())
        dom=max(paths,key=paths.get) if path_sum>0 else "暂无"
        dom_share=(float(paths[dom])/path_sum) if path_sum>0 else None
        mat_nodes=[n for n in nodes if n.get("material")==mat]
        top=max(mat_nodes,key=lambda n:(n.get("C") if n.get("C") is not None else -1),default=None)
        msg=f"{mat}当前综合相对水风险指数为 {_num_text(total)}。"
        if top:
            msg+=f" 对采购组合影响最大的供应地区是{top.get('node_name')}，约贡献{_pct_text(top.get('contribution_share'))}的整体风险。"
        if dom_share is not None:
            msg+=f" 首要风险因素是{dom}，约占{dom_share*100:.1f}%。"
        executive.append(msg)
        baseline_findings.append({
            "text":f"当前风险主要由{dom}驱动。企业在评估采购安全时，应优先关注这一风险因素与采购集中度的叠加影响。",
            "fact_ids":[f"baseline.{mat}.prwi",f"baseline.{mat}.path.ws",f"baseline.{mat}.path.dr",f"baseline.{mat}.path.sv"],
            "chart_ids":["fig2_paths"],"limitation":"该指数用于相对筛查，不等同于断供概率或财务损失。"})
        if top:
            nid=str(top.get("node_id"))
            top_share=_pct_text(top.get("contribution_share"))
            node_findings.append({
                "text":f"{top.get('node_name')}是当前最需要优先管理的供应地区，对整体风险的贡献约为{top_share}。应优先核实其真实采购量、供水条件和替代供应能力。",
                "fact_ids":[f"nodes.{mat}.{nid}.risk",f"nodes.{mat}.{nid}.contribution",f"nodes.{mat}.{nid}.contribution_share"],
                "chart_ids":["fig3_nodes"],"limitation":"风险贡献同时受到地区水风险与采购占比影响。"})
            actions.append({"object":f"{top.get('node_name')}","evidence_fact_ids":[f"nodes.{mat}.{nid}.contribution"],
                            "action":"优先核实该地区的真实采购占比、供水稳定性和替代供应来源，并建立持续监测。",
                            "preconditions":"在形成正式采购调整方案前，应以企业真实供应商和采购数据复核。","priority":"高",
                            "priority_reason":f"当前对整体风险贡献最高（约{top_share}）","department":"采购 / 供应链 / ESG",
                            "timing":"下一轮采购决策或供应商复核前"})
            highest_risk=max(mat_nodes,key=lambda n:(n.get("R") if n.get("R") is not None else -1),default=None)
            if highest_risk and highest_risk.get("node_id")!=top.get("node_id"):
                hrid=str(highest_risk.get("node_id"))
                actions.append({"object":f"{highest_risk.get('node_name')}","evidence_fact_ids":[f"nodes.{mat}.{hrid}.risk"],
                                "action":"开展专项水风险复核，确认当地水资源压力、干旱与季节波动是否会影响后续采购稳定性。",
                                "preconditions":"需要结合实际供应商产地与采购季节复核。","priority":"中",
                                "priority_reason":"该地区自身水风险较高，即使采购占比不是最大，也可能形成潜在脆弱点。",
                                "department":"ESG / 风控 / 采购","timing":"下一采购周期前"})
    q=facts.get("quality") or {}
    if q.get("proxy_fields") or q.get("assumptions"):
        limitations.append("本次结果包含参考数据或研究假设，适合用于风险筛查和方案比较；正式采购决策前应尽量替换为企业真实数据。")
    if any((s.get("unknown_share_U") or 0)>0 for s in summaries):
        limitations.append("仍有部分采购来源未能识别；未知部分没有被当作零风险处理。")
    scenario_findings=[]
    sc=facts.get("scenarios")
    if sc and sc.get("data"):
        d=sc.get("data") or {}; typ=d.get("scenario_type")
        if typ=="NodeFailure":
            target=d.get("target_node_name") or d.get("target_node_id") or "主要供应地区"
            ff=_pct_text(d.get("failure_fraction_f")); loss=_pct_text(d.get("gross_loss"))
            inv=_pct_text(d.get("inventory_used")); repl=_pct_text(d.get("replacement_allocated")); unmet=_pct_text(d.get("unmet_demand"))
            text=(f"在假设{target}发生{ff}供应中断的压力测试中，直接受影响的采购量约为{loss}。"
                  f"库存可缓冲约{inv}，替代供应可覆盖约{repl}，仍有约{unmet}的需求无法满足。"
                  "这说明企业需要提前准备库存和备选来源，而不能只依赖单一主供地区。")
        elif typ in {"PeakSeason","ExtremeDrought","AqueductFuture"}:
            title={"PeakSeason":"关键用水期压力升高","ExtremeDrought":"极端干旱","AqueductFuture":"未来水环境变化（演示）"}[typ]
            after=d.get("PRWI_future") if typ=="AqueductFuture" else d.get("PRWI_scenario")
            text=(f"{title}压力测试：基准综合风险为{_num_text(d.get('PRWI_baseline'))}，"
                  f"情景综合风险为{_num_text(after)}，变化量为{_num_text(d.get('PRWI_delta'))}。"
                  "这项比较沿用本次采购结构，不等于实际断供概率或减产预测。")
            if typ=="AqueductFuture":
                text+=f"采用{d.get('year')}年、{d.get('path')}路径的演示数据，不是已验证的未来预测。"
        else:
            text="本次压力测试显示，外部水压力变化会改变采购组合的整体风险，应结合供应地区和采购占比制定应对方案。"
        scenario_findings.append({"text":text,
                                  "fact_ids":[x for x in facts.get("fact_index",{}) if x.startswith("scenario.")][:8],
                                  "chart_ids":["fig4_scenario"],"limitation":"压力测试用于评估韧性，不是对未来事件的确定预测。"})
        limitations.extend(sc.get("warnings") or [])
    else:
        scenario_findings.append({"text":"本次尚未运行压力测试。","fact_ids":[],"chart_ids":[],"limitation":"未运行的情景不会生成结果。"})
    if sc and sc.get("data") and (sc.get("data") or {}).get("scenario_type")=="NodeFailure":
        d=sc.get("data") or {}; gap=_pct_text(d.get("unmet_demand"))
        actions.append({"object":"关键供应地区中断韧性","evidence_fact_ids":[x for x in facts.get("fact_index",{}) if x.startswith("scenario.")][:4],
                        "action":"明确关键供应地区中断时的库存缓冲、第二供应来源和替代采购额度，并把演练结果纳入采购预案。",
                        "preconditions":"需要用企业真实库存与替代供应能力替换示范参数。","priority":"高",
                        "priority_reason":f"当前压力测试仍存在约{gap}的需求缺口。","department":"供应链 / 采购 / 风控","timing":"尽快建立预案，并至少年度复核一次"})
    if q.get("proxy_fields") or q.get("assumptions"):
        actions.append({"object":"企业真实采购与供应商数据","evidence_fact_ids":[],
                        "action":"优先补充真实采购量、供应商产地、库存与替代供应能力，用于替换当前参考或示范数据。",
                        "preconditions":"由采购、供应链与ESG共同确认数据口径。","priority":"高",
                        "priority_reason":"当前结果含参考/代理数据，补齐企业真实数据可显著提高决策可信度。",
                        "department":"采购 / 供应链 / ESG","timing":"正式采购结构调整前"})
    return {
        "executive_summary":" ".join(executive),
        "baseline_findings":baseline_findings,
        "node_findings":node_findings,
        "scenario_findings":scenario_findings,
        "chart_comments":[],
        "actions":actions,
        "limitations":limitations or ["当前结果用于相对风险筛查，重大采购决策仍应结合供应商尽调、成本、质量和合同条件人工复核。"],
    }

def render_structured_report(report:dict)->str:
    parts=[]
    if report.get("executive_summary"):
        parts.append("**管理摘要**\n"+str(report["executive_summary"]))
    for title,key in [("当前风险重点","baseline_findings"),("重点供应地","node_findings"),("压力测试","scenario_findings")]:
        rows=report.get(key) or []
        if rows:
            parts.append("**"+title+"**\n"+"\n".join("• "+str(x.get("text") or "") for x in rows if x.get("text")))
    acts=report.get("actions") or []
    if acts:
        parts.append("**管理建议**\n"+"\n".join(
            f"• [{a.get('priority','')}] {a.get('object','')}: {a.get('action','')}（{a.get('priority_reason','')}）"
            for a in acts))
    lim=report.get("limitations") or []
    if lim:
        parts.append("**数据可信度与限制**\n"+"\n".join("• "+str(x) for x in lim))
    return "\n\n".join(parts)
