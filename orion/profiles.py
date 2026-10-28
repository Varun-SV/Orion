"""Versioned naming presets using the same renderer as immutable plans."""
import string
from orion.naming import NamingProfile,Naming,FIELDS
from orion.models import KINDS,KIND_NAMES,MediaItem,MatchDecision

QUALITY_KEYS={'screen_size','video_codec','audio_codec','audio_channels','source','release_group','edition'}

class Profiles:
    def __init__(self,library):
        self.library,self.store=library,library.store

    @staticmethod
    def defaults():
        return [NamingProfile(id='default-'+kind,label=KIND_NAMES[kind],kind=kind) for kind in KINDS]

    def list(self):
        records={profile.id:profile for profile in self.defaults()}
        with self.store.transaction() as conn:
            for row in conn.execute('SELECT data FROM orion_profiles ORDER BY id'):
                profile=NamingProfile.model_validate_json(row['data'])
                records[profile.id]=profile
        return list(records.values())

    def get(self,profile_id):
        result=next((profile for profile in self.list() if profile.id==profile_id),None)
        if result is None:raise KeyError('Profile not found')
        return result

    @staticmethod
    def example(kind,profile):
        metadata={'title':'Arrival' if kind in ('movies','anime_films') else 'Example series' if kind in ('series','anime','web_series') else 'Example track' if kind=='music' else 'Example book',
                  'year':'2016','artist':'Example artist','album':'Example album','author':'Example author','season':1,'episode':3,'track_number':'3'}
        ext='.flac' if kind=='music' else '.epub' if kind=='books' else '.mkv'
        return MediaItem(id='example',source_id='example',path='example'+ext,kind=kind,signature={'type':'file'},decision=MatchDecision(item_id='example',metadata=metadata))

    @classmethod
    def validate(cls,profile):
        if not set(profile.quality_keys)<=QUALITY_KEYS:raise ValueError('Unsupported quality tag')
        for field in ('movie_template','folder_template','episode_template','music_template','book_template'):
            template=getattr(profile,field)
            if len(template)>500:raise ValueError('Naming template is too long')
            for literal,name,format_spec,conversion in string.Formatter().parse(template):
                if name is not None and (name not in FIELDS or conversion or format_spec not in ('','02d','03d')):
                    raise ValueError('Unsupported naming placeholder or format')
        for kind in KINDS:
            Naming.render(cls.example(kind,profile),profile)
        directory=cls.example('movies',profile).model_copy(update={'signature':{'type':'directory'}})
        Naming.render(directory,profile)
        return profile

    def save(self,profile):
        self.validate(profile)
        with self.store.transaction() as conn:
            row=conn.execute('SELECT data FROM orion_profiles WHERE id=?',(profile.id,)).fetchone()
            current=NamingProfile.model_validate_json(row['data']) if row else next((p for p in self.defaults() if p.id==profile.id),None)
            if profile.version != (current.version if current else 1):raise ValueError('Profile version changed; reload before saving')
            saved=profile.model_copy(update={'version':current.version+1 if current else 1})
            conn.execute('INSERT INTO orion_profiles VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET kind=excluded.kind,data=excluded.data',
                         (saved.id,saved.kind,saved.model_dump_json()))
        return saved

    def preview(self,profile_id):
        profile=self.get(profile_id)
        return self.examples(profile)

    @classmethod
    def examples(cls,profile):
        cls.validate(profile)
        return {kind:Naming.render(cls.example(kind,profile),profile).path for kind in KINDS}
