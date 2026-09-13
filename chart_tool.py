from __future__ import annotations
from pathlib import Path
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# Blue style requested by the research/report design.
BLUE1="#1F4E79"; BLUE2="#5B9BD5"; BLUE3="#A9D2F3"; GREY="#B7C3D0"; GREEN="#2A9D8F"

def _configure_font():
    common=[
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/arphic-gbsn00lp/gbsn00lp.ttf",
    ]
    for path in common:
        if Path(path).exists():
            try:
                prop=font_manager.FontProperties(fname=path)
                plt.rcParams["font.family"]=[prop.get_name()]
                plt.rcParams["axes.unicode_minus"]=False
                return True
            except Exception:
                pass
    plt.rcParams["font.family"]=["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"]=False
    return False

HAS_CJK=_configure_font()
def T(zh,en): return zh if HAS_CJK else en

def _save(fig,path):
    fig.tight_layout()
    fig.savefig(path,dpi=180,bbox_inches="tight")
    plt.close(fig)
    return str(path)

def generate_report_charts(facts:dict, output_dir:str|Path, prefix:str="waterpulse")->dict:
    outdir=Path(output_dir); outdir.mkdir(parents=True,exist_ok=True)
    result={}
    recs=((facts.get("confirmed_inputs") or {}).get("records") or [])
    if recs:
        labels=[]; vals=[]; colors=[]
        for r in recs:
            w=r.get("purchase_weight")
            if w is None: continue
            labels.append(str((r.get("node_name") if HAS_CJK else r.get("node_id")) or r.get("node_id") or "Unknown"))
            vals.append(float(w))
            colors.append(GREY if r.get("unknown_flag") else BLUE2)
        if labels:
            fig,ax=plt.subplots(figsize=(7.2,max(2.6,.45*len(labels)+1)))
            y=range(len(labels)); ax.barh(list(y),vals,color=colors)
            ax.set_yticks(list(y),labels); ax.invert_yaxis(); ax.set_xlabel(T("采购占比","Procurement share"))
            ax.set_title(T("图1 本次采购结构","Figure 1 Procurement structure"))
            for i,v in enumerate(vals): ax.text(v+0.008,i,f"{v*100:.1f}%",va="center",fontsize=9)
            ax.set_xlim(0,max(1.0,max(vals)*1.18))
            result["fig1_procurement"]=_save(fig,outdir/f"{prefix}_fig1_procurement.png")

    sums=((facts.get("baseline") or {}).get("summary") or [])
    if sums:
        s=sums[0]
        vals=[float(s.get("path_contrib_WS") or 0),float(s.get("path_contrib_DR") or 0),float(s.get("path_contrib_SV") or 0)]
        total=sum(vals)
        fig,ax=plt.subplots(figsize=(7.2,2.6))
        left=0
        for label,v,c in zip((["长期缺水","历史干旱","季节波动"] if HAS_CJK else ["Water stress","Drought","Seasonality"]),vals,[BLUE1,BLUE2,BLUE3]):
            ax.barh([0],[v],left=left,label=label,color=c)
            if v>0: ax.text(left+v/2,0,f"{v:.4f}\n{(v/total*100 if total else 0):.1f}%",ha="center",va="center",fontsize=8)
            left+=v
        ax.set_yticks([0],[T("风险来源","Risk drivers")]); ax.set_xlabel(T("对整体风险的贡献","Contribution to total risk"))
        ax.set_title(T("图2 主要水风险来源","Figure 2 Main water-risk drivers")); ax.legend(loc="upper center",bbox_to_anchor=(.5,-.25),ncol=3,frameon=False)
        if total==0: ax.text(.5,0,T("总风险=0；占比不适用","Total risk = 0; shares N/A"),transform=ax.transAxes,ha="center",va="center")
        result["fig2_paths"]=_save(fig,outdir/f"{prefix}_fig2_paths.png")

    nodes=facts.get("nodes") or []
    if nodes:
        rows=sorted([n for n in nodes if n.get("C") is not None],key=lambda n:float(n.get("C")),reverse=True)
        rows=rows[:8]
        labels=[str((n.get("node_name") if HAS_CJK else n.get("node_id")) or n.get("node_id")) for n in rows]
        vals=[float(n.get("C") or 0) for n in rows]
        fig,ax=plt.subplots(figsize=(7.2,max(2.8,.46*len(rows)+1)))
        y=list(range(len(rows))); ax.barh(y,vals,color=BLUE2); ax.set_yticks(y,labels); ax.invert_yaxis()
        ax.set_xlabel(T("对整体风险的贡献","Contribution to total risk")); ax.set_title(T("图3 供应地区管理优先级","Figure 3 Supplier-region priority"))
        for i,(n,v) in enumerate(zip(rows,vals)):
            share=n.get("contribution_share")
            extra=f"  {float(share)*100:.1f}%" if share is not None else ""
            ax.text(v+max(vals+[1])*0.01,i,f"{v:.4f}{extra}",va="center",fontsize=8)
        result["fig3_nodes"]=_save(fig,outdir/f"{prefix}_fig3_nodes.png")

    sc=facts.get("scenarios")
    if sc and sc.get("data"):
        d=sc["data"]; typ=d.get("scenario_type")
        if typ=="NodeFailure":
            labels=(["直接受影响采购","库存缓冲","替代供应","剩余缺口"] if HAS_CJK else ["Directly affected","Inventory buffer","Alternative supply","Remaining gap"])
            vals=[float(d.get("gross_loss") or 0),float(d.get("inventory_used") or 0),
                  float(d.get("replacement_allocated") or 0),float(d.get("unmet_demand") or 0)]
            fig,ax=plt.subplots(figsize=(7.2,3.5)); ax.bar(labels,vals,color=[BLUE1,BLUE2,GREEN,GREY])
            ax.set_ylabel(T("占本次需求的比例","Share of demand")); ax.set_title(T("图4 主要供应地区中断压力测试","Figure 4 Key supplier disruption stress test"))
            for i,v in enumerate(vals): ax.text(i,v,f"{v:.4f}",ha="center",va="bottom",fontsize=8)
        else:
            b=d.get("PRWI_baseline")
            s=d.get("PRWI_scenario") if d.get("PRWI_scenario") is not None else d.get("PRWI_future")
            fig,ax=plt.subplots(figsize=(6.0,3.5)); vals=[0 if b is None else float(b),0 if s is None else float(s)]
            ax.bar((["当前","压力测试"] if HAS_CJK else ["Current","Stress test"]),vals,color=[BLUE2,BLUE1]); ax.set_ylabel(T("同口径风险指数","Risk index")); ax.set_title(T("图4 当前与压力测试对比","Figure 4 Current vs stress test"))
            for i,v in enumerate(vals): ax.text(i,v,f"{v:.4f}",ha="center",va="bottom",fontsize=8)
        result["fig4_scenario"]=_save(fig,outdir/f"{prefix}_fig4_scenario.png")
    return result
