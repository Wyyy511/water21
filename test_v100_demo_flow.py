from pathlib import Path
import re
from fastapi.testclient import TestClient
from server import app

SAMPLE="""请分析以下模拟采购情景的上游水风险。

案例名称：甘蔗采购组合演示
案例性质：虚拟案例，不对应任何真实企业
采购比例口径：按采购数量计算
采购比例来源：研究团队设定，仅用于方法演示

采购来源及比例：
- 广西崇左—江州—北海：25%
- 云南梁河：10%
- 巴西中南部：45%
- 泰国东北部：12%
- 古巴中部：4%
- 澳大利亚昆士兰：4%

请分别说明各节点的水风险、对组合风险的贡献，以及可比较的调整情景。
请注明水风险指标的数据来源、参考期和空间尺度，并将采购比例标为“假设”。"""

def test_health_100():
    c=TestClient(app);d=c.get('/api/health').json();assert d['version']=='10.2'

def test_ui_has_final_demo_inputs():
    h=Path('index.html').read_text(encoding='utf-8')
    assert 'id="micBtn"' in h
    assert 'id="exampleBtn"' in h
    assert '体验示例' in h
    assert '上传数据' in h
    assert 'accept=".xlsx,.xls,.csv"' in h
    assert 'ESG 报告' not in h and 'PDF/Word' not in h
    assert '甘蔗采购组合演示' in h

def test_server_user_copy_does_not_request_esg_report():
    s=Path('server.py').read_text(encoding='utf-8')
    assert '上传 ESG 报告' not in s

def test_sample_enters_real_agent_flow(monkeypatch):
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    c=TestClient(app)
    d=c.post('/api/agent/message',data={'message':SAMPLE}).json()
    assert d['status'] in {'needs_confirmation','success','partial'},d
    # First pass should normally ask confirmation and preserve all 6 supply nodes.
    recs=d.get('candidate_records') or []
    if recs:
        ids={str(x.get('node_id') or '') for x in recs}
        assert {'SC01','SC02','SC03','SC04','SC05','SC06'}.issubset(ids)
        ws=sorted(round(float(x.get('purchase_weight')),2) for x in recs if x.get('purchase_weight') is not None)
        assert ws==[0.04,0.04,0.10,0.12,0.25,0.45]
        assert all(bool(x.get('is_simulation')) for x in recs)
