"""Search AniDB's public title catalogue without unsupported search parameters."""
from __future__ import annotations
import gzip
import io
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
import requests
from orion.discovery import Cancelled

_LOCK = threading.Lock()
_CACHE = {}

def search_titles(query,config,context):
    cache = config.app_data_dir / 'anidb-titles.xml.gz'
    with _LOCK:
        if context.cancelled(): raise Cancelled()
        if not cache.exists() or time.time()-cache.stat().st_mtime > 86400:
            temp = cache.with_suffix('.gz.tmp')
            try:
                with requests.get('https://anidb.net/api/anime-titles.xml.gz',stream=True,timeout=(3,10),
                                  headers={'User-Agent':'Orion/0.2 (https://github.com/Varun-SV/Orion)'}) as response:
                    response.raise_for_status()
                    size = 0
                    with temp.open('wb') as file:
                        for block in response.iter_content(65536):
                            if context.cancelled(): raise Cancelled()
                            size += len(block)
                            if size > 16*1024*1024:
                                raise ValueError('Catalogue exceeds download limit')
                            file.write(block)
                # Validate before replacing the last usable catalogue.
                _parse(temp,context)
                os.replace(temp,cache)
            finally:
                temp.unlink(missing_ok=True)
        stamp = cache.stat().st_mtime_ns
        key = str(cache)
        if key not in _CACHE or _CACHE[key][0] != stamp:
            _CACHE[key] = (stamp,_parse(cache,context))
        catalogue = _CACHE[key][1]
    def norm(value): return re.sub(r'[^\w]','',value.casefold())
    needle = norm(query)
    if not needle:
        return []
    found = {}
    for aid,title in catalogue:
        if context.cancelled(): raise Cancelled()
        if needle in norm(title):
            rank = 0 if needle == norm(title) else 1
            if aid not in found or rank < found[aid][0]:
                found[aid] = (rank,title)
    return [{'id':aid,'title':title} for aid,(_,title) in sorted(found.items(),key=lambda row:(row[1][0],row[1][1]))[:12]]

def _parse(path,context):
    with gzip.open(path,'rb') as file:
        data = file.read(64*1024*1024+1)
    if len(data) > 64*1024*1024:
        raise ValueError('Catalogue exceeds unpacked limit')
    rows = []
    try:
        for event,node in ET.iterparse(io.BytesIO(data),events=('end',)):
            if context.cancelled(): raise Cancelled()
            if node.tag == 'anime':
                aid = node.get('aid')
                for title in node.findall('title'):
                    if aid and title.text:
                        rows.append((aid,title.text))
                node.clear()
    except ET.ParseError as exc:
        raise ValueError('Invalid AniDB title catalogue') from exc
    return rows
