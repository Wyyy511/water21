"""Regression coverage for real upload -> four scenarios -> switch/failure paths."""
import copy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
import server
from tools import scenario_tool

TYPES={'NodeFailure','ExtremeDrought','PeakSeason','AqueductFuture'}
CSV=('enterprise,material,node_id,node_name,purchase_weight,year\n'
     '测试企业,甘蔗,SC01,广西崇左—江州—北海,0.8,2025\n'
     '测试企业,甘蔗,SC02,云南梁河,0.2,2025\n').encode('utf-8-sig')

@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    return TestClient(server.app)

def assert_choices(response):
    assert {a['scenario_type'] for a in response['actions'] if a.get('action')=='run_scenario'}==TYPES

def upload(client):
    d=client.post('/api/agent/message',files={'file':('my_procurement.csv',CSV,'text/csv')}).json()
    if d['status']=='needs_confirmation':
        d=client.post('/api/agent/message',data={'session_id':d['session_id'],'action':'confirm_mapping'}).json()
    assert d['status'] in {'success','partial'},d
    assert_choices(d)
    nodes=d['result_summary']['baseline']['data']['nodes']
    assert {n['node_id']:n['weight'] for n in nodes}=={'SC01':0.8,'SC02':0.2}
    return d

def test_menu_before_upload_and_from_natural_language(client):
    for data in [{'action':'scenario_menu'},{'message':'请让我选择四种情况的压力测试'}]:
        d=client.post('/api/agent/message',data=data).json()
        assert d['status']=='success'
        assert_choices(d)
        assert '演示' in d['message']

def test_custom_upload_can_run_all_four_and_switch_again(client):
    first=upload(client)
    baseline=first['result_summary']['baseline']
    for scenario in ['NodeFailure','ExtremeDrought','PeakSeason','AqueductFuture','NodeFailure']:
        d=client.post('/api/agent/message',data={'session_id':first['session_id'],'action':'run_scenario','scenario_type':scenario}).json()
        assert d['status'] in {'success','partial'},d
        assert_choices(d)
        assert d['result_summary']['baseline']==baseline
        result=d['result_summary']['scenario']
        assert result['status']=='success'
        assert result['data']['scenario_type']==scenario
        assert result['baseline_input_hash']==baseline['input_hash']
        assert result['source_details'] and result['warnings']
        assert result['data']['PRWI_baseline']==pytest.approx(sum(n['C'] for n in baseline['data']['nodes']),abs=1e-6)
        if scenario=='AqueductFuture':
            assert result['data']['demo']==1
            assert any('演示' in w for w in result['warnings'])
        else:
            assert {n['node_id'] for n in result['data']['node_table']}=={'SC01','SC02'}

def test_missing_month_does_not_become_zero_risk_and_other_test_still_works(client,monkeypatch):
    first=upload(client)
    resources=scenario_tool._resources()
    resources['monthly_ws']=resources['monthly_ws'].copy()
    resources['monthly_ws'].loc[resources['monthly_ws']['node_id']=='SC01','m07']=float('nan')
    monkeypatch.setattr(scenario_tool,'_resources',lambda:resources)
    d=client.post('/api/agent/message',data={'session_id':first['session_id'],'action':'run_scenario','scenario_type':'PeakSeason'}).json()
    assert d['status']=='insufficient'
    assert 'SC01' in d['message'] and 'm07' in d['message']
    assert d['result_summary']['scenario']['data'] is None
    assert d['result_summary']['baseline']==first['result_summary']['baseline']
    assert_choices(d)
    other=client.post('/api/agent/message',data={'session_id':first['session_id'],'action':'run_scenario','scenario_type':'NodeFailure'}).json()
    assert other['result_summary']['scenario']['status']=='success'
    assert_choices(other)

@pytest.mark.parametrize('scenario,key',[('ExtremeDrought','extreme_drought'),('AqueductFuture','future')])
def test_missing_node_stops_instead_of_summing_partial_rows(client,monkeypatch,scenario,key):
    first=upload(client)
    resources=scenario_tool._resources()
    resources[key]=resources[key][resources[key]['node_id']!='SC01'].copy()
    monkeypatch.setattr(scenario_tool,'_resources',lambda:resources)
    d=client.post('/api/agent/message',data={'session_id':first['session_id'],'action':'run_scenario','scenario_type':scenario}).json()
    assert d['status']=='insufficient' and 'SC01' in d['message']
    assert d['result_summary']['scenario']['data'] is None
    assert_choices(d)

def test_natural_language_scenario_failure_does_not_fall_back_to_baseline_success(client,monkeypatch):
    first=upload(client)
    resources=scenario_tool._resources()
    resources['extreme_drought']=resources['extreme_drought'][resources['extreme_drought']['node_id']!='SC01'].copy()
    monkeypatch.setattr(scenario_tool,'_resources',lambda:resources)
    d=client.post('/api/agent/message',data={'session_id':first['session_id'],'message':'请进行极端干旱压力测试'}).json()
    assert d['status']=='insufficient' and 'SC01' in d['message']
    assert d['result_summary']['scenario']['data'] is None
    assert_choices(d)

@pytest.mark.parametrize('name',['index.html','static/index.html'])
def test_stress_menu_entry_and_sources_are_in_both_page_variants(name):
    html=Path(name).read_text(encoding='utf-8')
    assert 'id="stressBtn"' in html
    assert "$('#stressBtn').onclick" in html
    assert '情景数据来源与假设' in html
