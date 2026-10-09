from __future__ import annotations
import re
import string
from pathlib import Path,PurePosixPath
from typing import Literal
from pydantic import Field
from orion.models import Record,MediaItem,Kind

class NamingProfile(Record):
    id: str = Field(default='default',min_length=1,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')
    label: str = Field(default='Default',min_length=1,max_length=100)
    version: int = Field(default=1,ge=1)
    kind: Literal['auto'] | Kind = 'auto'
    movie_template: str = '{title}{year_suffix}/{title}{year_suffix}{quality}{ext}'
    folder_template: str = '{title}{year_suffix}'
    episode_template: str = '{title}/Season {season:02d}/{title} - S{season:02d}E{episode:02d}{episode_title_suffix}{quality}{ext}'
    music_template: str = '{artist}/{album}{year_suffix}/{track_prefix}{title}{ext}'
    book_template: str = '{author}/{series_path}{title}{ext}'
    nfo_enabled: bool = False
    artwork_enabled: bool = False
    episode_nfo_enabled: bool = False
    quality_keys: list[str] = Field(default_factory=lambda:['screen_size'])

class RelativeLayout(Record):
    path: str

FIELDS = {'title','year','year_suffix','ext','quality','season','episode','episode_title','episode_title_suffix','artist','album','track_prefix','author','series','series_path'}

RESERVED_NAMES = {'CON','PRN','AUX','NUL',*[f'{p}{n}' for p in ('COM','LPT') for n in range(1,10)]}

def reserved_name(value):
    return value.upper().split('.')[0] in RESERVED_NAMES

def clean(value):
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]','-',str(value)).strip(' .')
    if reserved_name(text):
        text = '_' + text
    return text or 'Untitled'

def valid_relative(path):
    if re.search(r'[<>:"\\|?*\x00-\x1f]',path):
        raise ValueError('Use a portable relative path')
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or '..' in parsed.parts or not parsed.parts:
        raise ValueError('Naming cannot escape its selected root')
    if any(part in ('.','') or part.endswith((' ','.')) or reserved_name(part) for part in parsed.parts):
        raise ValueError('Invalid path component')
    return parsed.as_posix()

class Naming:
    @staticmethod
    def render(item: MediaItem, profile: NamingProfile) -> RelativeLayout:
        if not item.decision:
            raise ValueError('Confirm metadata before planning')
        metadata = {**item.metadata, **item.decision.metadata}
        values = {field:'' for field in FIELDS}
        title = clean(metadata.get('title',''))
        year = str(metadata.get('year','')).strip()
        try:
            season,episode = int(metadata.get('season',1)),int(metadata.get('episode',1))
        except (TypeError,ValueError):
            raise ValueError('Season and episode must be integers') from None
        track = str(metadata.get('track_number','')).split('/')[0]
        try:
            track_prefix = f'{int(track):02d} - ' if track else ''
        except ValueError:
            track_prefix = clean(track) + ' - '
        quality = metadata.get('quality') or {}
        values.update(title=title,year=clean(year) if year else '',year_suffix=f' ({clean(year)})' if year else '',
                      ext=Path(item.path).suffix if item.signature.get('type') != 'directory' else '',
                      quality=''.join(' [' + clean(quality[key]) + ']' for key in profile.quality_keys if quality.get(key)),
                      season=season,episode=episode,episode_title=clean(metadata.get('episode_title','')) if metadata.get('episode_title') else '',
                      episode_title_suffix=' - ' + clean(metadata['episode_title']) if metadata.get('episode_title') else '',
                      artist=clean(metadata.get('artist') or 'Unknown artist'),album=clean(metadata.get('album') or 'Unknown album'),track_prefix=track_prefix,
                      author=clean(metadata.get('author') or 'Unknown author'),series=clean(metadata['series']) if metadata.get('series') else '',
                      series_path=clean(metadata['series']) + '/' if metadata.get('series') else '')
        template = profile.music_template if item.kind=='music' else profile.book_template if item.kind=='books' else profile.folder_template if item.signature.get('type')=='directory' else profile.episode_template if item.kind in ('series','anime','web_series') and metadata.get('episode') else profile.movie_template
        for literal,field,format_spec,conversion in string.Formatter().parse(template):
            if field is not None and (field not in FIELDS or conversion or format_spec not in ('','02d','03d')):
                raise ValueError('Unsupported naming placeholder or format')
        try:
            result = template.format_map(values)
        except (ValueError,TypeError) as exc:
            raise ValueError('Naming template is incompatible with its fields') from exc
        explicit = item.decision.metadata.get('filename')
        if explicit and item.signature.get('type') != 'directory':
            explicit = str(explicit)
            if len(PurePosixPath(valid_relative(explicit)).parts) != 1 or clean(explicit) != explicit:
                raise ValueError('An explicit filename must be one portable name')
            if Path(explicit).suffix.casefold() != Path(item.path).suffix.casefold():
                raise ValueError('An explicit filename must keep the original media extension')
            result = str(PurePosixPath(result).with_name(explicit))
        if item.signature.get('type') != 'directory' and Path(result).suffix.casefold() != Path(item.path).suffix.casefold():
            raise ValueError('A naming template must keep the original media extension')
        return RelativeLayout(path=valid_relative(result))
