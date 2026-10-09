import pytest
from pathlib import Path
from orion.models import MediaItem,MatchDecision
from orion.discovery import signature,Cancelled
from orion.duplicates import Duplicates

def examples(library,tmp_path):
    root=tmp_path/'comparison';root.mkdir()
    source=library.add_source(root)['id']
    items=[]
    for index,content in enumerate([b'same content',b'same content',b'alternate encoding']):
        path=root/f'{index}.mkv';path.write_bytes(content)
        item=MediaItem(id=str(index),source_id=source,path=str(path),kind='movies',signature=signature(path),metadata={'quality':{'screen_size':'1080p' if index<2 else '2160p'}},decision=MatchDecision(item_id=str(index),provider='tmdb',provider_id='329865',metadata={'title':'Arrival','year':'2016'}))
        library.upsert(item);items.append(item)
    return items

def test_exact_content_is_separate_from_versions_and_never_deletes(library,tmp_path,context):
    items=examples(library,tmp_path)
    result=Duplicates(library).compare([i.id for i in items],True,context)
    assert result.exact_groups==[['0','1']]
    assert result.version_groups[0].item_ids==['0','1','2']
    assert result.items[2].quality['screen_size']=='2160p'
    assert all(Path(i.path).exists() for i in items)

def test_metadata_comparison_does_not_compute_content_hashes(library,tmp_path,context,monkeypatch):
    items=examples(library,tmp_path)
    def forbidden(*a,**k):raise AssertionError('Metadata-only comparison must not read content')
    from orion.filesystem import Filesystem
    monkeypatch.setattr(Filesystem,'hash',forbidden)
    result=Duplicates(library).compare([i.id for i in items],False,context)
    assert result.exact_groups==[] and result.version_groups

def test_unavailable_copy_does_not_destroy_available_versions(library,tmp_path,context):
    items=examples(library,tmp_path);Path(items[1].path).unlink()
    result=Duplicates(library).compare([i.id for i in items],True,context)
    assert result.errors[0]['item_id']=='1'
    assert result.errors[0]['code']=='source_unavailable'
    assert Path(items[0].path).read_bytes()==b'same content'

def test_hashing_changed_source_is_not_declared_exact(library,tmp_path,context,monkeypatch):
    items=examples(library,tmp_path)
    from orion.filesystem import Filesystem
    original=Filesystem.hash
    def changing(self,path,context=None):
        value=original(self,path,context)
        if Path(path)==Path(items[0].path):Path(path).write_bytes(b'changed')
        return value
    monkeypatch.setattr(Filesystem,'hash',changing)
    result=Duplicates(library).compare([i.id for i in items],True,context)
    assert not result.exact_groups
    assert any(e['code']=='source_changed' for e in result.errors)
