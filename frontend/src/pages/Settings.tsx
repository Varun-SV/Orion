import { useState, type FormEvent } from 'react';
import { api, json } from '../api/client';
import { useResource } from '../api/useResource';
import { useWorkspace } from '../state/WorkspaceProvider';
import { type Kind, type Destination, type Theme, type Settings as Preferences } from '../types';
interface Category {
  id: string;
  kind: Kind;
  name: string;
  dest_subpath: string;
  api_pref: string;
}
const names = {
  tmdb: 'TMDb',
  anilist: 'AniList',
  anidb: 'AniDB',
  musicbrainz: 'MusicBrainz',
  acoustid: 'AcoustID',
  audd: 'AudD',
  openlibrary: 'Open Library',
};
function CategoryForm({ category }: { category: Category }) {
  const { refresh } = useWorkspace();
  const [path, setPath] = useState(category.dest_subpath),
    [provider, setProvider] = useState(category.api_pref),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api(
        '/categories/' + category.id,
        json('PUT', { dest_subpath: path, api_pref: provider }),
      );
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="category-form" onSubmit={(e) => void save(e)}>
      <h3>{category.name}</h3>
      <div className="form-grid">
        <label className="field">
          Collection subfolder
          <input value={path} onChange={(e) => setPath(e.target.value)} required />
        </label>
        <label className="field">
          Preferred provider
          <select value={provider} onChange={(e) => setProvider(e.target.value)}>
            {Object.entries(names).map(([id, name]) => (
              <option value={id} key={id}>
                {name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {error && <p role="alert">{error}</p>}
      <button className="secondary" disabled={busy} type="submit">
        Save {category.name}
      </button>
    </form>
  );
}
export function Settings() {
  const { settings, saveSettings } = useWorkspace();
  const { data: categories } = useResource<Category[]>('/categories'),
    { data: destinations } = useResource<Destination[]>('/destinations');
  const [error, setError] = useState(''),
    [message, setMessage] = useState('');
  async function save(update: Partial<Preferences>) {
    setError('');
    try {
      await saveSettings(update);
      setMessage('Preferences saved.');
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <>
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      <div className="settings-grid">
        <section className="panel">
          <h2>Make it yours.</h2>
          <p className="subtitle">A quiet workspace, in the light that suits you.</p>
          <div className="theme-options">
            {(['ivory', 'clay', 'night'] as Theme[]).map((theme) => (
              <button
                key={theme}
                data-theme={theme}
                aria-pressed={settings?.theme === theme}
                className="theme-option"
                onClick={() => void save({ theme })}
              >
                <span />
                {theme[0].toUpperCase() + theme.slice(1)}
              </button>
            ))}
          </div>
          <label className="field">
            Default destination
            <select
              value={settings?.default_destination ?? ''}
              onChange={(e) => void save({ default_destination: e.target.value })}
            >
              <option value="">Choose in each preview</option>
              {destinations?.map((d) => (
                <option value={d.id} key={d.id}>
                  {d.label}
                </option>
              ))}
            </select>
          </label>
        </section>
        <section className="panel">
          <h2>Identification choices</h2>
          <label className="check-field">
            <input
              type="checkbox"
              checked={settings?.fingerprint_enabled ?? false}
              onChange={(e) => void save({ fingerprint_enabled: e.target.checked })}
            />
            Enable AcoustID fingerprint identification
          </label>
          <p className="notice">
            Requires your AcoustID key and the optional fpcalc utility. Fingerprints are sent to
            AcoustID; the audio file stays here.
          </p>
          <label className="check-field">
            <input
              type="checkbox"
              checked={settings?.audd_enabled ?? false}
              onChange={(e) => void save({ audd_enabled: e.target.checked })}
            />
            Allow AudD audio sample uploads
          </label>
          <p className="notice">
            Explicit opt-in: up to 512 KB of a selected music file is sent to AudD when you request
            identification. Requires your AudD key.
          </p>
        </section>
      </div>
      <section className="panel collection-settings">
        <h2>Collection destinations & providers</h2>
        <p className="subtitle">
          Use relative subfolders, such as Movies or Music. Naming templates and quality options are
          managed in naming profiles.
        </p>
        {categories?.map((category) => (
          <CategoryForm key={category.id} category={category} />
        ))}
      </section>
    </>
  );
}
