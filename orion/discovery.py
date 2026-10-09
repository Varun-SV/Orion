from __future__ import annotations
import os
import stat
from pathlib import Path
from typing import Any
from pydantic import Field
from orion.models import Record, MediaItem, JobContext
from orion.store import item_id

VIDEO = {'.mkv','.mp4','.avi','.mov','.wmv','.m4v','.ts','.webm','.mpg','.mpeg'}
AUDIO = {'.mp3','.flac','.m4a','.ogg','.wav','.aac','.opus','.wma','.alac','.aiff'}
BOOKS = {'.epub','.pdf'}
CATEGORY_HINTS = {'movies':'movies','films':'movies','movie':'movies','series':'series','tv':'series','shows':'series','anime':'anime','anime films':'anime_films','anime movies':'anime_films','web series':'web_series','webseries':'web_series','music':'music','books':'books'}

class ScanSummary(Record):
    processed: int = 0
    unchanged: int = 0
    unavailable_sources: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    cancelled: bool = False

class Cancelled(Exception):
    pass

def linked(path: Path):
    if path.is_symlink():
        return True
    try:
        # Path.is_junction is unavailable on Python 3.11. Inspect the tag
        # without following the link; other reparse points are ordinary files.
        return getattr(path.lstat(),'st_reparse_tag',0) == getattr(stat,'IO_REPARSE_TAG_MOUNT_POINT',0xA0000003)
    except OSError:
        return False

def signature(path: Path, context: JobContext | None = None) -> dict[str, Any]:
    if linked(path):
        raise ValueError('Symbolic links and junctions are excluded')
    stat = path.stat()
    if path.is_file():
        return {'type':'file','size':stat.st_size,'mtime_ns':stat.st_mtime_ns,'device':stat.st_dev,'inode':stat.st_ino}
    if not path.is_dir():
        raise ValueError('Only regular files and folders are supported')
    children = {}
    for directory, dirs, files in os.walk(path, followlinks=False):
        if context and context.cancelled():
            raise Cancelled()
        dirs[:] = sorted(d for d in dirs if not linked(Path(directory)/d))
        for name in sorted(files):
            child = Path(directory)/name
            if linked(child):
                continue
            if child.is_file():
                children[child.relative_to(path).as_posix()] = signature(child)
    return {'type':'directory','children':children,'device':stat.st_dev,'inode':stat.st_ino}

def audio_metadata(path):
    from mutagen import File
    file = File(path, easy=True)
    if file is None:
        return {}
    tags = file.tags or {}
    if any(k in tags for k in ('TIT2','TPE1','TALB')):
        def get(key, frame):
            found = tags.get(frame)
            return str(found.text[0]) if found and found.text else ''
        metadata = {key:get(key,frame) for key,frame in [('title','TIT2'),('artist','TPE1'),('album','TALB'),('year','TDRC'),('track_number','TRCK'),('disc_number','TPOS')]}
    else:
        metadata = {key:str((tags.get(tag) or [''])[0]) for key,tag in [('title','title'),('artist','artist'),('album','album'),('year','date'),('track_number','tracknumber'),('disc_number','discnumber'),('release_mbid','musicbrainz_albumid')]}
    metadata['duration'] = getattr(getattr(file,'info',None),'length',0)
    metadata['year'] = metadata.get('year','')[:4]
    return {k:v for k,v in metadata.items() if v != ''}

def book_metadata(path):
    if path.suffix.lower() == '.epub':
        from ebooklib import epub
        book = epub.read_epub(str(path), options={'ignore_ncx':True})
        data = book.metadata.get('http://purl.org/dc/elements/1.1/',{})
        def first(key):
            values = data.get(key, [])
            return str(values[0][0]) if values else ''
        return {'title':first('title'),'author':first('creator'),'year':first('date')[:4],'isbn':first('identifier')}
    from pypdf import PdfReader
    info = PdfReader(path, strict=False).metadata or {}
    date = str(info.get('/CreationDate',''))
    return {'title':str(info.get('/Title','')),'author':str(info.get('/Author','')),'year':date[2:6] if date.startswith('D:') else date[:4]}

def parsed_metadata(path, kind):
    metadata = {'title':path.stem if path.is_file() else path.name,'format':path.suffix.lstrip('.').lower()}
    try:
        if kind == 'music':
            parsed = audio_metadata(path)
        elif kind == 'books':
            parsed = book_metadata(path)
        else:
            from guessit import guessit
            data = guessit(path.name)
            parsed = {key:data[key] for key in ('title','year','season','episode') if key in data}
            parsed['quality'] = {key:str(data[key]) for key in ('screen_size','video_codec','audio_codec','source') if key in data}
            for key in ('season','episode'):
                if isinstance(parsed.get(key), list):
                    parsed[key] = parsed[key][0]
        metadata.update({k:v for k,v in parsed.items() if v not in ('',None)})
        metadata['embedded'] = kind in ('music','books') and bool(parsed.get('title'))
    except Exception as exc:
        metadata['metadata_warning'] = 'Embedded metadata could not be read; review filename metadata.'
    return metadata

class Discovery:
    def __init__(self, library):
        self.library = library

    def scan(self, source_ids: list[str], deep: bool, context: JobContext) -> ScanSummary:
        report = ScanSummary()
        sources = {r['id']:r for r in self.library.sources()}
        for sid in source_ids:
            if context.cancelled():
                report.cancelled = True
                break
            if sid not in sources:
                raise KeyError('Source not found')
            source = sources[sid]
            with self.library.store.transaction() as conn:
                archived=conn.execute('SELECT value FROM orion_settings WHERE key=?',('source_archived_'+sid,)).fetchone()
            if archived and archived[0]=='true':
                report.skipped.append('Paused source: '+sid)
                continue
            root = Path(source['path'])
            if not root.is_dir() or any(linked(parent) for parent in (root,*root.parents)):
                report.unavailable_sources.append(sid)
                continue
            seen, candidates, walk_errors = set(), {}, []
            for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_errors.append):
                if context.cancelled():
                    report.cancelled = True
                    break
                safe_dirs = []
                for name in dirs:
                    child = Path(directory)/name
                    if linked(child):
                        report.skipped.append(str(child))
                    else:
                        safe_dirs.append(name)
                dirs[:] = sorted(safe_dirs)
                for name in sorted(files):
                    if context.cancelled():
                        report.cancelled = True
                        break
                    path = Path(directory)/name
                    if linked(path):
                        report.skipped.append(str(path))
                        continue
                    ext = path.suffix.lower()
                    if ext not in VIDEO | AUDIO | BOOKS:
                        continue
                    if ext in VIDEO and source['kind'] in ('music','books'):
                        continue
                    kind = 'music' if ext in AUDIO else 'books' if ext in BOOKS else source['kind']
                    parts = path.relative_to(root).parts
                    container = False
                    if kind == 'auto':
                        hint = CATEGORY_HINTS.get(parts[0].lower().replace('_',' '))
                        container = bool(hint and len(parts)>1)
                        kind = hint or CATEGORY_HINTS.get(root.name.lower().replace('_',' ')) or ('series' if parsed_metadata(path,'movies').get('episode') else 'movies')
                    if source['kind'] != 'auto' and kind != source['kind']:
                        continue
                    group_depth = 2 if container else 1
                    item_path = root.joinpath(*parts[:group_depth]) if kind not in ('music','books') and len(parts)>group_depth else path
                    candidates[str(item_path)] = kind
            if report.cancelled:
                break
            # Directory-backed video items own every member, including audio
            # and books. Publish only the outer candidate for each subtree.
            candidates = {path:kind for path,kind in candidates.items()
                if not any(str(parent) in candidates for parent in Path(path).parents)}
            for path_text, kind in sorted(candidates.items()):
                if context.cancelled():
                    report.cancelled = True
                    break
                path = Path(path_text)
                iid = item_id(sid,path)
                try:
                    sig = signature(path,context)
                    try:
                        old = self.library.at_path(sid,path_text)
                    except KeyError:
                        old = None
                    if old:
                        iid = old.id
                    if old and old.signature == sig and not deep:
                        seen.add(iid)
                        if old.status == 'unavailable':
                            self.library.status(iid, 'approved' if old.decision else 'pending')
                        report.unchanged += 1
                        continue
                    preserved = old and (old.signature == sig or not old.signature)
                    item = MediaItem(id=iid,source_id=sid,path=path_text,kind=kind,signature=sig,
                                     metadata=parsed_metadata(path,kind),decision=old.decision if preserved else None,
                                     status=old.status if preserved and old.status != 'unavailable' else 'pending')
                    observed = self.library.discovered(item)
                    seen.add(observed.id)
                    report.processed += 1
                    context.progress('Scanning',report.processed+report.unchanged,len(candidates))
                except Cancelled:
                    report.cancelled = True
                    break
                except (OSError,ValueError):
                    report.skipped.append(path_text)
            if walk_errors:
                report.unavailable_sources.append(sid)
            if not report.cancelled and not walk_errors:
                with self.library.store.transaction() as conn:
                    rows = conn.execute('SELECT id,path FROM orion_items WHERE source_id=?',(sid,)).fetchall()
                    for row in rows:
                        if row['id'] not in seen and Path(row['path']).absolute().is_relative_to(root.absolute()) and not self.library._has_unfinished_operations(conn,row['id']):
                            conn.execute("UPDATE orion_items SET status='unavailable' WHERE id=?",(row['id'],))
        return report
