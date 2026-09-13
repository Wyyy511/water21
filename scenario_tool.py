from __future__ import annotations
import copy, importlib.util
import numpy as np
import pandas as pd
from core.paths import ENGINE_DIR, DATA_DIR

spec=importlib.util.spec_from_file_location('scenario_v2', ENGINE_DIR/'scenario_engine.py')
se=importlib.util.module_from_spec(spec); spec.loader.exec_module(se)

def _resources():
    return se.load_master_data(str(DATA_DIR))

def run_scenario(baseline_result: dict, scenario_type: str, material: str,
                 year: int=2050, path: str='BAU', failure_fraction: float=1.0,
                 inventory: float=0.10) -> dict:
    if not baseline_result or baseline_result.get('data') is None:
        return {'status':'insufficient','data':None,'warnings':[],'data_gaps':['必须先运行 Baseline'],'model_version':'scenario_v2.0'}
    base=baseline_result['data']['nodes'].copy()
    if base.empty or material not in set(base['material']):
        return {'status':'insufficient','data':None,'warnings':[],'data_gaps':[f'Baseline 中没有材料 {material}'],'model_version':'scenario_v2.0'}
    # Keep the selected material and the user's weights; never substitute the
    # demo procurement structure when switching stress tests.
    base=base[base['material']==material].copy()
    warnings=[]; sources=[]
    try:
        d=_resources(); params=copy.deepcopy(d['params']); th=params['theta']
        required_ids=set(base.loc[base['weight']>0,'node_id'])

        def checked_rows(frame, columns, label, ranges):
            selected=frame[frame['node_id'].isin(set(base['node_id']))].copy()
            if selected.duplicated('node_id').any():
                raise ValueError(label+'存在重复节点记录，请核对后再运行')
            missing=sorted(required_ids-set(selected['node_id']))
            if missing:
                raise ValueError(label+'缺少供应节点：'+'、'.join(map(str,missing)))
            for col in columns:
                values=pd.to_numeric(selected[col],errors='coerce')
                lo,hi=ranges[col]
                invalid=selected['node_id'].isin(required_ids) & (~np.isfinite(values) | (values<lo) | (values>hi))
                if invalid.any():
                    raise ValueError(label+'字段 '+col+' 缺失或超出范围：'+'、'.join(map(str,selected.loc[invalid,'node_id'])))
                selected[col]=values
            for _,row in selected.iterrows():
                sources.append({'node_id':row['node_id'],'source_ref':row.get('source_ref'),
                                'data_type':row.get('data_type'),'fields':columns})
            return selected

        if scenario_type=='PeakSeason':
            columns=[f'm{i:02d}' for i in range(1,13)]
            monthly=checked_rows(d['monthly_ws'],columns,'月度水压力数据',{c:(0,5) for c in columns})
            out=se.scenario_peak_season(base,monthly,th)
            g=out[out.material==material].copy()
            pb=float(base[base.material==material]['C'].sum()); ps=float(g['C_peak'].sum())
            data={'scenario_type':'PeakSeason','material':material,'PRWI_baseline':pb,'PRWI_scenario':ps,'PRWI_delta':ps-pb,
                  'node_table':g[['node_id','node_name','R','R_peak','R_delta','C','C_peak','rank_peak']].copy()}
            warnings.append('当前按月度水压力最高的三个月均值进行比较，未使用已核验作物关键期；这是季节压力测试的备选规则。')
        elif scenario_type=='AqueductFuture':
            future_sub=d['future'][(d['future']['year']==int(year)) & (d['future']['path']==path)].copy()
            if future_sub.empty:
                raise ValueError('没有 '+str(year)+' 年 '+str(path)+' 路径的未来水环境数据')
            future_sub=checked_rows(future_sub,['ws_future','sv_future'],'未来水环境数据',{'ws_future':(0,5),'sv_future':(0,5)})
            _,combo=se.scenario_future(base,future_sub,th)
            row=combo[(combo.material==material)&(combo.year==int(year))&(combo.path==path)]
            if row.empty: raise ValueError('指定未来组合不存在')
            data=row.iloc[0].to_dict(); data['scenario_type']='AqueductFuture'; data['demo']=1
            warnings.append('未来 WS/SV 当前为 S 类演示数据（demo=1），只能用于流程/敏感性演示，不能写成真实未来预测。')
        elif scenario_type=='ExtremeDrought':
            extreme=checked_rows(d['extreme_drought'],['dr_ed','n_extreme_months'],'历史极端干旱数据',{'dr_ed':(0,1),'n_extreme_months':(0,float('inf'))})
            no_event=extreme['node_id'].isin(required_ids) & (extreme['n_extreme_months']<=0)
            if no_event.any():
                raise ValueError('以下供应节点未识别到历史极端干旱事件，不能汇总完整组合风险：'+'、'.join(map(str,extreme.loc[no_event,'node_id'])))
            out=se.scenario_extreme_drought(base,extreme,params,th)
            g=out[out.material==material].copy()
            pb=float(base[base.material==material]['C'].sum()); ps=float(g['C_ed'].sum())
            data={'scenario_type':'ExtremeDrought','material':material,'PRWI_baseline':pb,'PRWI_scenario':ps,'PRWI_delta':ps-pb,
                  'node_table':g[['node_id','node_name','dr','dr_ed','event_status','R','R_ed','R_delta_ed','gross_supply_loss','lambda_source']].copy()}
            warnings.append('供应损失使用 λ=30% 文献参考值，仅示范 Supply-side 机制，不是逐作物真实减产预测。')
        elif scenario_type=='NodeFailure':
            if not 0<=float(failure_fraction)<=1 or not 0<=float(inventory)<=1:
                raise ValueError('中断比例和库存缓冲比例必须在0到1之间')
            params['node_failure']['failure_fraction_f']=float(failure_fraction)
            params['node_failure']['inventory_I']=float(inventory)
            allres=se.scenario_node_failure(base,params)
            if material not in allres: raise ValueError('材料无节点失效结果')
            r=allres[material]
            data={k:v for k,v in r.items() if k not in ['node_table','replacement_table']}
            data['scenario_type']='NodeFailure'; data['material']=material
            data['node_table']=r['node_table']; data['replacement_table']=r['replacement_table']
            warnings.append('库存与替代容量为 S 类/参考情景参数；真实企业应用需替换为企业实际数据。')
            sources.append({'source_ref':'scenario_params.json / node_failure',
                            'data_type':params['node_failure'].get('assumption_type'),
                            'fields':['failure_fraction_f','inventory_I','replacement_cap_by_material']})
        else:
            return {'status':'insufficient','data':None,'warnings':[],'data_gaps':[f'未知情景 {scenario_type}'],'model_version':'scenario_v2.0'}
        return {'status':'success','data':data,'warnings':warnings,'data_gaps':[],
                'source_details':sources,'assumptions':warnings,
                'baseline_input_hash':baseline_result.get('input_hash'),
                'data_version':'2026-09-06-integrated-mvp','model_version':'scenario_v2.0'}
    except Exception as e:
        return {'status':'insufficient','data':None,'warnings':warnings,'data_gaps':[str(e)],'model_version':'scenario_v2.0'}
