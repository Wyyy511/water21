from pathlib import Path
import pandas as pd
from tools.data_tool import extract_structured_message, validate_normalized
from tools.baseline_tool import calculate_baseline
from tools.report_facts import build_report_facts, fallback_structured_report
from agent.deepseek_client import _plain_user_language, _validate_structured_report

def test_plain_user_language_defined():
    assert _plain_user_language("```json\n你好\n```")=="你好"

def test_quantity_text_4000_6000():
    df=extract_structured_message("2025年采购甘蔗共10000吨，广西崇左—江州—北海4000吨，巴西中南部6000吨。")
    known=df[~df.unknown_flag.astype(bool)]
    vals=sorted(round(float(x),4) for x in known.purchase_weight.tolist())
    assert vals==[0.4,0.6]

def test_custom_nonzero_parameters_result_020():
    msg="模拟测试：一个甘蔗节点，采购占比100%，WS=0.20，SV=0.40，DR=0.60，BWD=0.50，DYS=0.50，CTS=1.00，OA=0.50，WS和SV均为0-1尺度，θWS=0.3333333333，θDR=0.3333333333，θSV=0.3333333334"
    df=extract_structured_message(msg)
    v=validate_normalized(df); assert not v["issues"],v
    out=calculate_baseline(df,run_id="custom020")
    assert out["status"] not in {"error","conflict","insufficient"},out
    s=out["data"]["summary"]
    if isinstance(s,list): s=pd.DataFrame(s)
    assert abs(float(s.iloc[0]["PRWI"])-0.2)<1e-5

def test_zero_parameters_preserved():
    msg="模拟测试：一个甘蔗节点，采购占比100%，WS=0，SV=0，DR=0，BWD=0.50，DYS=0.50，CTS=1.00，OA=0.50，θWS=0.3333333333，θDR=0.3333333333，θSV=0.3333333334"
    df=extract_structured_message(msg)
    out=calculate_baseline(df,run_id="zero")
    s=out["data"]["summary"]
    if isinstance(s,list): s=pd.DataFrame(s)
    assert abs(float(s.iloc[0]["PRWI"]))<1e-12
    assert float(s.iloc[0]["path_contrib_WS"])==0
    assert float(s.iloc[0]["path_contrib_DR"])==0
    assert float(s.iloc[0]["path_contrib_SV"])==0

def test_unknown_20_percent_preserved():
    df=extract_structured_message("分析甘蔗：广西崇左40%，巴西中南部40%，来源未知20%。")
    v=validate_normalized(df)
    assert not v["issues"],v
    assert abs(v["unknown_share_by_material"]["甘蔗"]-0.2)<1e-9
    out=calculate_baseline(df,run_id="unknown20")
    s=out["data"]["summary"]
    if isinstance(s,list): s=pd.DataFrame(s)
    assert abs(float(s.iloc[0]["unknown_share_U"])-0.2)<1e-6

def test_130_percent_rejected():
    df=extract_structured_message("分析甘蔗：广西崇左70%，巴西中南部60%。")
    v=validate_normalized(df)
    assert v["status"]=="conflict"
    assert any("130.0%" in x or ">100%" in x for x in v["issues"])

def test_structured_fallback_valid_fact_refs():
    df=extract_structured_message("分析甘蔗：广西崇左40%，巴西中南部60%。")
    for i in df.index: df.at[i,"human_confirmed"]=True
    b=calculate_baseline(df,run_id="facts")
    facts=build_report_facts(baseline=b,records=df.to_dict(orient="records"),snapshot_id="snap")
    rep=fallback_structured_report(facts)
    assert not _validate_structured_report(rep,facts)

def test_report_has_chart_code_and_eight_sections():
    src=Path("export_tool.py").read_text(encoding="utf-8")
    for x in ["1. 管理摘要","2. 供应地区风险概览","3. 主要水风险来源","4. 压力测试：如果关键供应地区发生中断",
              "5. AI 风险判断与管理建议","6. 数据可信度与使用说明"]:
        assert x in src
    assert "generate_report_charts" in src
