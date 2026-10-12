"""Export persisted outcomes; never re-run operations to generate a report."""
import csv
import io
import json
from orion.store import safe_metadata

class Reports:
    def __init__(self, store):
        self.store = store

    def export(self, job_id, format):
        if format not in ('csv','json'):
            raise ValueError('Choose CSV or JSON')
        with self.store.transaction() as conn:
            job = conn.execute('SELECT * FROM orion_jobs WHERE id=?',(job_id,)).fetchone()
            if not job:
                raise KeyError('Job not found')
            payload = json.loads(job['payload'])
            rows = conn.execute('SELECT data FROM orion_operations WHERE plan_id=? ORDER BY rowid',(payload.get('plan_id',''),)).fetchall()
        operations = []
        for row in rows:
            op = json.loads(row[0])
            v = op.get('verification',{})
            decision = v.get('item_decision') or {}
            operations.append({'id':op['id'],'item_id':op['item_id'],'kind':op['kind'],
                'source':op['source'],'destination':op['destination'],'state':op['state'],
                'title':str(decision.get('metadata',{}).get('title','')),
                'provider':decision.get('provider',''),'provider_id':decision.get('provider_id',''),
                'sha256':v.get('sha256',''),'bytes':op['expected_signature'].get('size',0),
                'error':v.get('error','')})
        result = safe_metadata(json.loads(job['result']) if job['result'] else None)
        if format=='json':
            document = {'job':{'id':job_id,'kind':job['kind'],'state':job['state'],'created_at':job['created_at'],
                'updated_at':job['updated_at'],'error':job['error'],'result':result},'operations':operations}
            return json.dumps(document,ensure_ascii=False,indent=2).encode('utf-8')
        fields = ['id','item_id','kind','source','destination','state','title','provider','provider_id','sha256','bytes','error']
        if not operations:
            fields = ['job_id','kind','state','error','result']
            operations = [{'job_id':job_id,'kind':job['kind'],'state':job['state'],'error':job['error'] or '', 'result':json.dumps(result,ensure_ascii=False)}]
        output = io.StringIO(newline='')
        writer = csv.DictWriter(output,fieldnames=fields)
        writer.writeheader()
        for row in operations:
            cells = {}
            for key,value in row.items():
                text = str(value if value is not None else '')
                cells[key] = "'"+text if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')) else text
            writer.writerow(cells)
        return output.getvalue().encode('utf-8')
