from fastapi.testclient import TestClient
import server

c=TestClient(server.app)

def test_unsupported_material_qualitative_without_upload(monkeypatch):
    monkeypatch.setattr(server,'deepseek_configured',lambda:False)
    r=c.post('/api/agent/message',data={'message':'分析一下红薯在中国的上游水风险'})
    assert r.status_code==200
    d=r.json(); assert '红薯' in d['message']
    assert '上传 ESG' not in d['message'] or '不需要先上传' in d['message']
    assert all(x.get('action') not in {'focus_upload','download_template'} for x in d.get('actions',[]))
    assert d['reference_scope']['material']=='红薯'

def test_followup_region_keeps_material_context(monkeypatch):
    monkeypatch.setattr(server,'deepseek_configured',lambda:False)
    r1=c.post('/api/agent/message',data={'message':'分析一下红薯在中国的上游水风险'}).json()
    sid=r1['session_id']
    r2=c.post('/api/agent/message',data={'session_id':sid,'message':'供应地区在长江中下游地区'})
    assert r2.status_code==200
    d=r2.json(); assert '红薯' in d['message']; assert '长江中下游' in d['message']
    assert '定性' in d['message'] or '风险' in d['message']

def test_third_turn_is_direct_analysis(monkeypatch):
    monkeypatch.setattr(server,'deepseek_configured',lambda:False)
    r1=c.post('/api/agent/message',data={'message':'分析一下红薯在中国的上游水风险'}).json(); sid=r1['session_id']
    c.post('/api/agent/message',data={'session_id':sid,'message':'供应地区在长江中下游地区'})
    d=c.post('/api/agent/message',data={'session_id':sid,'message':'那你先分析红薯的上游水风险机制和管理重点'}).json()
    assert '红薯' in d['message']
    assert any(k in d['message'] for k in ['长期水资源','干旱','季节','采购'])

def test_guess_material_not_greedy():
    assert server._guess_material('分析一下红薯在中国的上游水风险')=='红薯'
    assert server._guess_material('那你先分析红薯的上游水风险机制和管理重点')=='红薯'

def test_guess_location_freeform():
    assert '长江中下游' in server._guess_location('供应地区在长江中下游地区','红薯')
