from pathlib import Path
import os
import shutil
import wave
import pytest
from orion.discovery import Discovery
from orion.models import MatchDecision, KINDS

@pytest.mark.parametrize('kind,ext', [(k,'.wav' if k=='music' else '.epub' if k=='books' else '.mkv') for k in KINDS])
def test_every_collection_is_discovered(library, tmp_path, context, kind, ext):
    root = tmp_path / kind
    root.mkdir()
    (root / ('Arrival.2016' + ext)).write_bytes(b'media fixture')
    source = library.add_source(root, kind=kind)
    summary = Discovery(library).scan([source['id']], False, context)
    assert summary.processed == 1
    assert library.query(kind=kind).total == 1

def test_incremental_scan_preserves_decisions_then_invalidates_changed_file(library, tmp_path, context):
    root = tmp_path / 'source'
    root.mkdir()
    media = root / 'Arrival.2016.mkv'
    media.write_bytes(b'first')
    source = library.add_source(root)
    scanner = Discovery(library)
    scanner.scan([source['id']], False, context)
    item = library.query().items[0]
    decision = MatchDecision(item_id=item.id, metadata={'title':'Arrival','year':'2016'})
    library.decide(item.id, decision)
    assert scanner.scan([source['id']], False, context).processed == 0
    assert library.get(item.id).decision == decision
    media.write_bytes(b'changed content')
    assert scanner.scan([source['id']], False, context).processed == 1
    assert library.get(item.id).decision is None
    assert library.get(item.id).status == 'pending'

def test_offline_source_retains_index_and_decision(library, tmp_path, context):
    root = tmp_path / 'drive'
    root.mkdir()
    (root / 'Arrival.mkv').write_bytes(b'film')
    source = library.add_source(root)
    scanner = Discovery(library)
    scanner.scan([source['id']], False, context)
    item = library.query().items[0]
    decision = MatchDecision(item_id=item.id, metadata={'title':'Arrival'})
    library.decide(item.id, decision)
    root.rename(tmp_path / 'offline')
    report = scanner.scan([source['id']], False, context)
    assert report.unavailable_sources == [source['id']]
    assert library.get(item.id).decision == decision
    assert library.query().total == 1

def test_directory_identity_includes_subtitles_and_changes(library, tmp_path, context):
    root = tmp_path / 'movies'
    movie = root / 'Arrival'
    movie.mkdir(parents=True)
    (movie / 'film.mkv').write_bytes(b'film')
    sub = movie / 'film.en.srt'
    sub.write_text('subtitle')
    source = library.add_source(root, kind='movies')
    scanner = Discovery(library)
    scanner.scan([source['id']], False, context)
    item = library.query().items[0]
    assert item.path == str(movie)
    assert set(item.signature['children']) == {'film.mkv','film.en.srt'}
    sub.write_text('updated subtitle')
    assert scanner.scan([source['id']], False, context).processed == 1

def test_cancelled_scan_does_not_mark_unvisited_items_missing(library, tmp_path, context):
    root = tmp_path / 'source'
    root.mkdir()
    (root / 'Arrival.mkv').write_bytes(b'film')
    source = library.add_source(root)
    scanner = Discovery(library)
    scanner.scan([source['id']], False, context)
    item = library.query().items[0]
    class Cancelled:
        def cancelled(self): return True
        def progress(self,*a): pass
    assert scanner.scan([source['id']], False, Cancelled()).cancelled
    assert library.get(item.id).status == 'pending'

def test_symlink_sources_are_skipped(library, tmp_path, context):
    root = tmp_path / 'source'
    root.mkdir()
    outside = tmp_path / 'outside.mkv'
    outside.write_bytes(b'private')
    try:
        (root / 'linked.mkv').symlink_to(outside)
    except OSError:
        pytest.skip('OS account cannot create symlinks')
    source = library.add_source(root)
    report = Discovery(library).scan([source['id']], False, context)
    assert library.query().total == 0
    assert report.skipped

def test_embedded_audio_tags_are_extracted_without_qt(library, tmp_path, context):
    from mutagen.wave import WAVE
    from mutagen.id3 import TIT2, TPE1, TALB
    root = tmp_path / 'audio'
    root.mkdir()
    path = root / 'track.wav'
    with wave.open(str(path), 'wb') as audio:
        audio.setparams((1,2,8000,0,'NONE','not compressed'))
        audio.writeframes(b'\0\0'*8000)
    tags = WAVE(path)
    tags.add_tags()
    tags.tags.add(TIT2(encoding=3,text=['Real title']))
    tags.tags.add(TPE1(encoding=3,text=['Real artist']))
    tags.tags.add(TALB(encoding=3,text=['Real album']))
    tags.save()
    source = library.add_source(root,kind='music')
    Discovery(library).scan([source['id']],False,context)
    item = library.query(kind='music').items[0]
    assert item.metadata['title'] == 'Real title'
    assert item.metadata['artist'] == 'Real artist'
    assert item.status == 'pending'

def test_embedded_book_metadata_is_extracted(library, tmp_path, context):
    from pypdf import PdfWriter
    root = tmp_path / 'books'
    root.mkdir()
    writer = PdfWriter()
    writer.add_blank_page(width=100,height=100)
    writer.add_metadata({'/Title':'Actual book','/Author':'Actual author'})
    writer.write(root / 'book.pdf')
    source = library.add_source(root,kind='books')
    Discovery(library).scan([source['id']],False,context)
    item = library.query(kind='books').items[0]
    assert item.metadata['title'] == 'Actual book'
    assert item.metadata['author'] == 'Actual author'

def test_decision_rejects_wrong_item_and_blank_title(library, tmp_path, context):
    root = tmp_path / 'source'
    root.mkdir()
    (root/'film.mkv').write_bytes(b'film')
    source = library.add_source(root)
    Discovery(library).scan([source['id']],False,context)
    item = library.query().items[0]
    with pytest.raises(ValueError):
        library.decide(item.id, MatchDecision(item_id='wrong',metadata={'title':'Film'}))
    with pytest.raises(ValueError):
        library.decide(item.id, MatchDecision(item_id=item.id,metadata={'title':' '}))
    assert library.get(item.id).decision is None

def test_search_pagination_and_literal_wildcards(library,tmp_path,context):
    root = tmp_path / 'search'
    root.mkdir()
    for name in ('Arrival.2016.mkv','50%_Cut.mkv'):
        (root/name).write_bytes(b'film')
    source = library.add_source(root)
    Discovery(library).scan([source['id']],False,context)
    assert library.query(query='Arrival').total == 1
    assert library.query(query='%_').total == 1
    assert library.query(limit=1).total == 2
    assert len(library.query(limit=1).items) == 1
    with pytest.raises(ValueError):
        library.query(offset=-1)
