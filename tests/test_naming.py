from pathlib import Path
import pytest
from orion.naming import Naming, NamingProfile
from orion.models import MediaItem,MatchDecision

def approved(kind='movies',path='original.mkv',**metadata):
    return MediaItem(id='item',source_id='source',path=path,kind=kind,metadata={'title':'Arrival',**metadata},
                     decision=MatchDecision(item_id='item',metadata={'title':'Arrival',**metadata}))

def test_movie_layout_keeps_only_selected_quality():
    item = approved(year='2016',quality={'screen_size':'1080p','video_codec':'x265'})
    assert Naming.render(item,NamingProfile()).path == 'Arrival (2016)/Arrival (2016) [1080p].mkv'

def test_episode_layout_has_season_and_episode():
    item = approved(kind='series',season=2,episode=3,episode_title='Home')
    assert Naming.render(item,NamingProfile()).path == 'Arrival/Season 02/Arrival - S02E03 - Home.mkv'

@pytest.mark.parametrize('template', ['../{title}{ext}','/{title}{ext}','{unknown}{ext}','{title.__class__}{ext}','{title!r}{ext}'])
def test_unsafe_templates_rejected(template):
    with pytest.raises(ValueError):
        Naming.render(approved(),NamingProfile(movie_template=template))

def test_portable_titles_cannot_create_path_components():
    item = approved(title='bad/title:next')
    path = Naming.render(item,NamingProfile()).path
    assert 'bad-title-next' in path
    assert len(Path(path).parts) == 2

def test_music_and_books_layout():
    music = approved(kind='music',path='track.flac',artist='Artist',album='Album',year='2020',track_number='3/10')
    assert Naming.render(music,NamingProfile()).path == 'Artist/Album (2020)/03 - Arrival.flac'
    book = approved(kind='books',path='book.epub',author='Author',series='Series')
    assert Naming.render(book,NamingProfile()).path == 'Author/Series/Arrival.epub'

def test_path_specific_filename_is_respected():
    item = approved(filename='Arrival - theatrical.mkv')
    assert Naming.render(item,NamingProfile()).path == 'Arrival/Arrival - theatrical.mkv'

@pytest.mark.parametrize('name',['../outside.mkv','nested/outside.mkv','C:\\outside.mkv'])
def test_path_specific_filename_cannot_escape(name):
    with pytest.raises(ValueError):
        Naming.render(approved(filename=name),NamingProfile())
