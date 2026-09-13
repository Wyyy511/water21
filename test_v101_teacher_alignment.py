from pathlib import Path
from fastapi.testclient import TestClient
from server import app

def test_health_101():
    assert TestClient(app).get('/api/health').json()['version']=='10.2'

def test_final_ui_has_five_inputs_and_no_esg_report():
    h=Path('index.html').read_text(encoding='utf-8')
    assert '上传数据' in h
    assert 'Excel 模板' in h
    assert 'id="micBtn"' in h
    assert 'id="exampleBtn"' in h
    assert '体验示例' in h
    assert '甘蔗采购组合演示' in h
    assert 'ESG 报告' not in h
    assert 'PDF/Word' not in h
    assert 'accept=".xlsx,.xls,.csv"' in h

def test_backend_rejects_pdf_docx_for_final_demo():
    c=TestClient(app)
    r=c.post('/api/agent/message',data={'message':'分析这个数据'},files={'file':('x.pdf',b'fake','application/pdf')})
    d=r.json()
    assert d['status']=='error'
    assert 'Excel/CSV' in d['message']

def test_sample_is_sent_automatically():
    h=Path('index.html').read_text(encoding='utf-8')
    assert 'async function runExperienceSample' in h
    assert 'await send();' in h
    assert '案例性质：虚拟案例，不对应任何真实企业' in h
    assert '采购比例来源：研究团队设定，仅用于方法演示' in h
