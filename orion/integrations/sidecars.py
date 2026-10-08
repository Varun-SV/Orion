"""Opt-in metadata projections and bounded, credential-free artwork downloads."""
from __future__ import annotations
import io
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit, urljoin
import requests
from pydantic import Field
from orion.models import Record
from orion.naming import Naming
from orion.discovery import Cancelled

class SidecarSpec(Record):
    kind: str
    path: str = ''
    content: str = ''
    artwork_url: str = ''
    warning: str = ''


def xml_text(value):
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff]', '', str(value or ''))


def nfo(root_name, metadata, provider='', provider_id=''):
    root = ET.Element(root_name)
    fields = {'title':'title', 'year':'year', 'plot':'plot', 'artist':'artist', 'album':'album',
              'season':'season', 'episode':'episode', 'showtitle':'showtitle', 'aired':'air_date'}
    for tag, key in fields.items():
        if metadata.get(key) not in (None, ''):
            ET.SubElement(root, tag).text = xml_text(metadata[key])
    if provider_id:
        ET.SubElement(root, 'uniqueid', {'type':provider, 'default':'true'}).text = xml_text(provider_id)
    if metadata.get('release_mbid') and root_name == 'album':
        ET.SubElement(root, 'musicbrainzalbumid').text = xml_text(metadata['release_mbid'])
    return ET.tostring(root, encoding='unicode', xml_declaration=True)


class Sidecars:
    @staticmethod
    def plan(item, profile):
        if not item.decision:
            return []
        metadata = {**item.metadata, **item.decision.metadata}
        layout = Path(Naming.render(item, profile).path)
        directory = item.signature.get('type') == 'directory'
        folder = layout if directory else layout.parent
        result = []
        provider, pid = item.decision.provider, item.decision.provider_id
        episodic = item.kind in ('series', 'anime', 'web_series')
        shared = not directory and len(layout.parts) < 2
        if episodic and not directory and len(layout.parts) >= 3:
            folder = Path(layout.parts[0])
        if profile.nfo_enabled:
            if item.kind in ('movies', 'anime_films'):
                result.append(SidecarSpec(kind='create_nfo', path=str(layout.with_suffix('.nfo') if shared else folder/'movie.nfo'), content=nfo('movie',metadata,provider,pid)))
            elif episodic:
                if shared:
                    result.append(SidecarSpec(kind='warning',warning='Series NFO needs a separate series folder'))
                else:
                    result.append(SidecarSpec(kind='create_nfo', path=str(folder/'tvshow.nfo'),content=nfo('tvshow',metadata,provider,pid)))
            elif item.kind == 'music':
                album = {**metadata, 'title':metadata.get('album','Unknown album')}
                result.append(SidecarSpec(kind='create_nfo', path=str(folder/'album.nfo'), content=nfo('album',album,'musicbrainz',metadata.get('release_mbid',''))))
                result.append(SidecarSpec(kind='create_nfo', path=str(folder.parent/'artist.nfo'), content=nfo('artist',{'title':metadata.get('artist','Unknown artist')})))
        if profile.artwork_enabled:
            url = metadata.get('poster_url') or metadata.get('cover_url') or metadata.get('artwork_url') or ''
            if item.kind == 'music' and not url:
                mbid = str(metadata.get('release_mbid',''))
                if re.fullmatch(r'[0-9a-fA-F-]{36}',mbid):
                    url = 'https://coverartarchive.org/release/'+mbid+'/front-500'
                else:
                    result.append(SidecarSpec(kind='warning', warning='release_id_unavailable: tag-only audio has no cover release ID'))
            elif not url:
                result.append(SidecarSpec(kind='warning',warning='artwork_unavailable: no confirmed cover URL'))
            if url:
                path = layout.with_suffix('.jpg') if shared or item.kind=='books' else folder/('cover.jpg' if item.kind=='music' else 'poster.jpg')
                result.append(SidecarSpec(kind='create_artwork',path=str(path),artwork_url=str(url)))
        return result

    @staticmethod
    def episode(item, relative_video, metadata):
        data = {**metadata, 'showtitle':item.decision.metadata.get('title', item.metadata.get('title',''))}
        data['title'] = metadata.get('episode_title') or metadata.get('title') or f"Episode {metadata.get('episode','')}"
        # Only an episode's ID belongs in episodedetails, never the series ID.
        return SidecarSpec(kind='create_nfo',path=str(Path(relative_video).with_suffix('.nfo')),
            content=nfo('episodedetails',data,'tmdb',metadata.get('episode_provider_id','')))

    @staticmethod
    def valid_artwork_url(url):
        parsed = urlsplit(url)
        host = (parsed.hostname or '').lower()
        allowed = host in ('image.tmdb.org','s4.anilist.co','s.anilist.co','covers.openlibrary.org','coverartarchive.org','archive.org') or host.endswith('.archive.org')
        if parsed.scheme != 'https' or not allowed or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.port not in (None,443) or any(c in url for c in ('\\','\r','\n')):
            raise ValueError('Artwork origin is not a supported credential-free HTTPS provider')
        return url

    @staticmethod
    def artwork(url, context):
        from PIL import Image
        deadline = time.monotonic()+30
        session = requests.Session()
        session.trust_env = False
        session.headers.clear()
        session.headers['User-Agent'] = 'Orion/0.2 (optional media artwork)'
        try:
            for redirect in range(4):
                if time.monotonic()>deadline:raise OSError('Artwork deadline exceeded')
                Sidecars.valid_artwork_url(url)
                if context.cancelled(): raise Cancelled()
                with session.get(url, stream=True, timeout=(3,10), allow_redirects=False) as response:
                    if response.status_code in (301,302,303,307,308):
                        if redirect==3: raise ValueError('Artwork redirect limit')
                        url = urljoin(url,response.headers.get('Location',''))
                        continue
                    if response.status_code != 200: raise OSError('Artwork unavailable')
                    if int(response.headers.get('Content-Length','0'))>10*1024*1024: raise ValueError('Artwork exceeds byte limit')
                    data = bytearray()
                    for block in response.iter_content(65536):
                        if context.cancelled(): raise Cancelled()
                        if time.monotonic()>deadline: raise OSError('Artwork deadline exceeded')
                        data.extend(block)
                        if len(data)>10*1024*1024: raise ValueError('Artwork exceeds byte limit')
                with Image.open(io.BytesIO(data),formats=['JPEG','PNG','WEBP']) as image:
                    if image.width*image.height>16_000_000: raise ValueError('Artwork exceeds pixel limit')
                    image.load()
                    converted = image.convert('RGB')
                    output = io.BytesIO()
                    converted.save(output,format='JPEG',quality=90)
                    if output.tell()>10*1024*1024:raise ValueError('Converted artwork exceeds byte limit')
                    return output.getvalue()
            raise OSError('Artwork unavailable')
        finally:
            session.close()