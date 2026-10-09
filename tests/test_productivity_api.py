from test_api import client, wait_job

def test_profiles_watch_and_comparison_routes_are_strict_and_persist(client,tmp_path):
    profiles=client.get('/api/v1/profiles')
    assert profiles.status_code==200 and len(profiles.json())==7
    profile=profiles.json()[0]
    profile['id']='custom';profile['label']='My preset'
    assert client.post('/api/v1/profiles/preview',json=profile).status_code==200
    assert client.put('/api/v1/profiles/custom',json=profile).status_code==200
    assert client.put('/api/v1/profiles/other',json=profile).status_code==400
    invalid={**profile,'movie_template':'../{title}{ext}'}
    assert client.put('/api/v1/profiles/custom',json=invalid).status_code==400
    root=tmp_path/'watched';root.mkdir();(root/'a.mkv').write_bytes(b'fixture');(root/'b.mkv').write_bytes(b'other fixture')
    sid=client.post('/api/v1/sources',json={'path':str(root),'kind':'movies'}).json()['id']
    assert client.get('/api/v1/sources/'+sid+'/watch').json()['enabled'] is False
    assert client.put('/api/v1/sources/'+sid+'/watch',json={'enabled':True,'stability_seconds':10,'auto_organise':True}).status_code==422
    assert client.put('/api/v1/sources/'+sid+'/watch',json={'enabled':True,'stability_seconds':10}).status_code==200
    assert client.get('/api/v1/sources').json()[0]['watch']==1
    scan=client.post('/api/v1/jobs',json={'kind':'scan','payload':{'source_ids':[sid]}}).json()
    assert wait_job(client,scan['id'])['state']=='completed'
    items=client.get('/api/v1/items').json()['items'];item=items[0];ids=[i['id'] for i in items]
    comparison=client.post('/api/v1/comparisons',json={'item_ids':ids,'exact':True})
    assert comparison.status_code==202
    result=wait_job(client,comparison.json()['id'])
    assert result['state']=='completed' and result['result']['exact_groups']==[]
    assert (root/'a.mkv').read_bytes()==b'fixture'
    assert client.post('/api/v1/comparisons',json={'item_ids':ids,'delete':True}).status_code==422
    report=client.get('/api/v1/jobs/'+comparison.json()['id']+'/report?format=json')
    assert report.status_code==200 and 'attachment' in report.headers['content-disposition']
    assert report.json()['job']['result']['items'][0]['item_id']==item['id']
    assert client.get('/api/v1/jobs/no-such-job/report').status_code==404
    assert client.get('/api/v1/jobs/'+comparison.json()['id']+'/report?format=html').status_code==422
