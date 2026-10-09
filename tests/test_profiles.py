import pytest
from orion.naming import NamingProfile,Naming
from orion.models import MediaItem,MatchDecision
from orion.profiles import Profiles
from orion.planner import Planner,PlanOptions
from tests_support import make_plan

def test_profile_versions_persist_and_reject_lost_updates(library):
    profiles=Profiles(library)
    saved=profiles.save(NamingProfile(id='film-names',kind='movies',movie_template='{title}/{title}{ext}'))
    assert saved.version==1
    changed=profiles.save(saved.model_copy(update={'folder_template':'{title}'}))
    assert changed.version==2
    assert Profiles(library).get(saved.id)==changed
    with pytest.raises(ValueError,match='version'):profiles.save(saved)

@pytest.mark.parametrize('field,template',[('movie_template','../{title}{ext}'),('music_template','{unsupported}{ext}'),('book_template','/{title}{ext}'),('episode_template','{title.__class__}'),('folder_template','A\\B')])
def test_every_template_is_validated_before_save(library,field,template):
    with pytest.raises(ValueError):Profiles(library).save(NamingProfile(id='unsafe',**{field:template}))
    assert not any(p.id=='unsafe' for p in Profiles(library).list())

def test_selected_profile_renderer_and_plan_snapshot_agree(library,tmp_path,context):
    planner,original,source,target=make_plan(library,tmp_path,context)
    item=library.query().items[0]
    profile=Profiles(library).save(NamingProfile(id='flat-movies',kind='movies',movie_template='{title}{ext}'))
    with library.store.transaction() as conn:did=conn.execute('SELECT id FROM orion_destinations').fetchone()[0]
    plan=planner.create([item.id],PlanOptions(destination_id=did,profile_id=profile.id))
    assert plan.issues==[]
    assert plan.operations[0].destination.endswith('Arrival.mkv')
    assert plan.operations[0].verification['profile_version']==profile.version
    assert Profiles(library).preview(profile.id)['movies']==Naming.render(item,profile).path
