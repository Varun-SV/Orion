import csv,io,json
from orion.executor import Executor
from orion.jobs import JobManager
from orion.reports import Reports
from tests_support import make_plan

def test_reports_export_stored_paths_decisions_outcomes_and_no_credentials(library,tmp_path,context):
    planner,plan,source,target=make_plan(library,tmp_path,context)
    result=Executor(library,planner).execute(plan.id,1,context)
    with library.store.transaction() as conn:
        conn.execute("INSERT INTO orion_jobs(id,kind,state,payload,result,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",('report','organise','completed',json.dumps({'plan_id':plan.id,'api_key':'never-export'}),json.dumps({**result.model_dump(),'token':'never-export'}),'2026-10-09','2026-10-09'))
    reports=Reports(library.store)
    document=reports.export('report','json').decode()
    assert 'never-export' not in document and 'api_key' not in document
    decoded=json.loads(document)
    assert decoded['operations'][0]['source']==str(source)
    assert decoded['operations'][0]['destination']==str(target)
    assert decoded['operations'][0]['state']=='completed'
    assert decoded['operations'][0]['title']=='Arrival'
    rows=list(csv.DictReader(io.StringIO(reports.export('report','csv').decode())))
    assert rows[0]['source']==str(source) and rows[0]['state']=='completed'

def test_csv_escapes_formula_titles_and_multiline_quotes(library,tmp_path,context):
    planner,plan,source,target=make_plan(library,tmp_path,context)
    op=plan.operations[0];op.verification['item_decision']['metadata']['title']='=SUM(1,2)\n"quoted"'
    with library.store.transaction() as conn:
        conn.execute('UPDATE orion_operations SET data=? WHERE id=?',(op.model_dump_json(),op.id))
        conn.execute("INSERT INTO orion_jobs(id,kind,state,payload,created_at,updated_at) VALUES(?,?,?,?,?,?)",('report','organise','failed',json.dumps({'plan_id':plan.id}),'2026-10-09','2026-10-09'))
    rows=list(csv.DictReader(io.StringIO(Reports(library.store).export('report','csv').decode())))
    assert rows[0]['title']=='\'=SUM(1,2)\n"quoted"'
