import json
import re
from datetime import date, timedelta

LABEL={'todo':'未完成','in_progress':'进行中','done':'已完成'}

def snapshot_of(result):
    if isinstance(result,str): result=json.loads(result)
    if isinstance(result,list): result=result[0] if result else {}
    if result.get('status')!='success':raise ValueError('数据库查询失败')
    return json.loads(result['data'][0]['snapshot'])

def show_list(snap,lid):
    ls=next((x for x in snap['lists'] if x['id']==lid),None)
    if not ls:return '当前没有可用清单。可以说“新建明天待办：任务A、任务B”。'
    rows=[t for t in snap['tasks'] if t['list_id']==lid]
    done=sum(t['status']=='done' for t in rows)
    text='**'+ls['name']+'** · 已完成 '+str(done)+'/'+str(len(rows))+' 项\n\n'
    return text+('\n'.join(str(i+1)+'. '+t['title']+' — '+LABEL.get(t['status'],t['status'])+'（编号 '+str(t['id'])+'）' for i,t in enumerate(rows)) if rows else '这份清单目前没有事项。')

def plan(intent,snap,current_list,request_id,query):
    lists=snap['lists'];tasks=snap['tasks']
    current=next((x for x in lists if str(x['id'])==str(current_list)),None)
    if current is None:current=next((x for x in lists if x['id']==1),lists[0] if lists else None)
    result={'route':'reply','reply':'','preview':'','command':'','receipt_sql':'SELECT 1;', 'current_list':str(current['id']) if current else '', 'proposal_list':'', 'snapshot':json.dumps(snap,ensure_ascii=False)}
    def stop(msg):result['reply']=msg;return result
    action=intent.get('action','clarify')
    if action=='chat':result['route']='chat';return result
    if action=='clarify':return stop(intent.get('question') or '请说明要查看、添加或修改哪些事项；例如“明天做任务A、任务B”。')
    if action=='lists':return stop('已有清单：\n'+('\n'.join('- '+x['name']+'（编号 '+str(x['id'])+'）' for x in lists) or '暂无清单。可以直接说“明天要做……”来新建。'))
    name=str(intent.get('list_name') or '').strip()
    day=str(intent.get('day') or '').strip()
    today=date.fromisoformat(snap['today'])
    relative={'today':0,'tomorrow':1,'day_after_tomorrow':2,'今天':0,'明天':1,'明早':1,'明天早上':1,'后天':2,'今日待办':0,'明天待办':1}
    if day in relative or name in relative:
        name=(today+timedelta(days=relative.get(day,relative.get(name,0)))).isoformat()+' 待办'
    elif re.fullmatch(r'\d{4}-\d{2}-\d{2}',day):
        try:name=date.fromisoformat(day).isoformat()+' 待办'
        except ValueError:return stop('日期无法识别，请使用明确的年月日。')
    if name in ('当前清单','当前','这个清单','本清单'):name=''
    candidates=[x for x in lists if x['name']==name] if name else ([current] if current else [])
    if not candidates and name and action not in ('add','create'):
        candidates=[x for x in lists if name in x['name']]
    if len(candidates)>1:return stop('有多份清单符合，请指定完整名称：'+ '、'.join(x['name'] for x in candidates))
    target=candidates[0] if candidates else None
    if action in ('view','switch'):
        if not target:return stop('没有找到这份清单：'+(name or '当前清单')+'。可以先说“我有哪些清单”。')
        result['current_list']=str(target['id']);return stop(show_list(snap,target['id']))
    if action not in ('add','create','update','delete_tasks','delete_list'):return stop('这次操作没有识别清楚，请再描述一次。')
    items=intent.get('items') or []
    if not isinstance(items,list) or any(not isinstance(i,str) for i in items):return stop('事项内容无法识别，请逐条列出要添加的事情。')
    items=list(dict.fromkeys(i.strip() for i in items if i.strip()))
    if len(items)>100 or any(len(i)>500 for i in items):return stop('每次最多添加100项，每项最多500字，请分批提交。')
    if action in ('add','create'):
        if action=='add' and not items:return stop('请告诉我要添加哪些事项。')
        if action=='create' and not items and re.search(r'[:：]\s*\S',query):
            return stop('我没有完整识别出冒号后面的事项，本次没有保存。请改成“在清单'+(name or '待办')+'里添加：事项一、事项二”再发一次。')
        if not target:
            name=name or today.isoformat()+' 待办'
            if len(name)>100:return stop('清单名称最多100字，请缩短名称。')
            op='create'
        else:
            name=target['name'];op='append'
            if not items:return stop('这份清单已经存在。\n\n'+show_list(snap,target['id']))
            existing={t['title'] for t in tasks if t['list_id']==target['id']}
            duplicate=[i for i in items if i in existing]
            if duplicate:return stop('这些事项已在“'+name+'”中：'+ '、'.join(duplicate)+'。本次尚未添加，请去掉重复项后重试。')
        preview=('新建清单' if op=='create' else '追加事项')+'：**'+name+'**\n\n'+('\n'.join(str(i+1)+'. '+t+' — 未完成' for i,t in enumerate(items)) or '建立一份空清单。')
        ids=[];status='todo'
    else:
        if not target:return stop('没有找到要操作的清单，请明确清单名称。')
        name=target['name'];op=action;status=str(intent.get('status') or '')
        rows=[t for t in tasks if t['list_id']==target['id']]
        ids=[]
        if action!='delete_list':
            targets=intent.get('targets') or []
            if not isinstance(targets,list) or not targets:return stop('请说明要操作的事项名称或数据库编号。')
            for ref in targets:
                ref=str(ref).strip()
                found=[t for t in rows if t['title']==ref]
                if not found and ref:found=[t for t in rows if re.sub(r'\s+','',t['title'])==re.sub(r'\s+','',ref)]
                if not found and ref.isdigit():found=[t for t in rows if t['id']==int(ref)]
                if not found and ref and not ref.isdigit():found=[t for t in rows if ref in t['title']]
                if len(found)!=1:return stop('在“'+name+'”中无法唯一确定“'+ref+'”，请用完整事项名称。\n\n'+show_list(snap,target['id']))
                if found[0]['id'] not in ids:ids.append(found[0]['id'])
        if action=='update':
            if status not in LABEL:return stop('请说明要改成未完成、进行中还是已完成。')
            selected=[t for t in rows if t['id'] in ids]
            ids=[t['id'] for t in selected if t['status']!=status]
            if not ids:return stop('这些事项已经是“'+LABEL[status]+'”，无需重复修改。')
            preview='更新 **'+name+'** 中的事项：\n\n'+'\n'.join('- '+t['title']+'：'+LABEL[t['status']]+' → '+LABEL[status] for t in selected if t['id'] in ids)
        elif action=='delete_tasks':preview='从 **'+name+'** 删除以下事项：\n\n'+'\n'.join('- '+t['title'] for t in rows if t['id'] in ids)
        else:preview='删除整份清单 **'+name+'** 及其中 '+str(len(rows))+' 项事项：\n\n'+('\n'.join('- '+t['title']+' — '+LABEL[t['status']] for t in rows) or '（空清单）')+'\n\n其他清单不受影响。'
        items=[]
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',request_id):return stop('本次请求编号无效，请重新发起操作。')
    payload={'list_id':target['id'] if target else 0,'list_name':name,'items':items,'task_ids':ids,'status':status}
    cmd={'id':request_id,'action':op,'payload':json.dumps(payload,ensure_ascii=False),'expected_revision':snap['revision']}
    result.update(route='confirm',preview=preview+'\n\n**尚未保存。确认后执行以上整批操作，取消则不修改。**',command=json.dumps(cmd,ensure_ascii=False),proposal_list=name,receipt_sql="SELECT id, action, payload, result_list_id FROM task_commands WHERE id='"+request_id+"';")
    return result

def main(intent,snapshot,current_list,request_id,query):
    try:
        raw=re.sub(r'<think>.*?</think>','',intent,flags=re.S).strip()
        if raw.startswith('```'):raw=raw.split('\n',1)[1].rsplit('```',1)[0].strip()
        obj=json.loads(raw)
        if not isinstance(obj,dict):raise ValueError('invalid intent')
        return plan(obj,snapshot_of(snapshot),current_list,request_id,query)
    except (ValueError,KeyError,TypeError,IndexError):
        return {'route':'reply','reply':'本次没有修改数据。请求或数据库结果未能准确识别，请重新描述需要操作的清单和事项。','preview':'','command':'','receipt_sql':'SELECT 1;','current_list':str(current_list or ''),'proposal_list':'','snapshot':'{}'}
