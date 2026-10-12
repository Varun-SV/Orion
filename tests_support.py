from pathlib import Path
from orion.discovery import Discovery
from orion.models import MatchDecision
from orion.planner import Planner,PlanOptions
from orion.store import item_id

def make_plan(library,tmp_path,context,directory=False):
    root = tmp_path/'incoming'
    root.mkdir()
    folder = root/'Arrival'
    if directory:
        folder.mkdir()
        source = folder/'original.mkv'
        (folder/'original.en.srt').write_bytes(b'subtitle')
    else:
        source = root/'original.mkv'
    source.write_bytes(b'original media bytes')
    sid = library.add_source(root,kind='movies')['id']
    Discovery(library).scan([sid],False,context)
    item = library.query().items[0]
    library.decide(item.id,MatchDecision(item_id=item.id,metadata={'title':'Arrival','year':'2016'}))
    destination = tmp_path/'library'
    destination.mkdir()
    did = item_id('destination',destination)
    with library.store.transaction() as conn:
        conn.execute('INSERT INTO orion_destinations VALUES(?,?,?)',(did,str(destination),'Library'))
    planner = Planner(library)
    plan = planner.create([item.id],PlanOptions(destination_id=did))
    target = next(Path(op.destination) for op in plan.operations if op.source == str(source))
    return planner,plan,source,target

class Crash(BaseException):
    pass
