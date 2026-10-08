import { useState } from 'react';
import { api, json } from '../api/client';
import { useResource } from '../api/useResource';
import { useWorkspace } from '../state/WorkspaceProvider';
import { collections, type NamingProfile } from '../types';
const templates = [
  ['movie_template', 'Movie template'],
  ['folder_template', 'Folder template'],
  ['episode_template', 'Episode template'],
  ['music_template', 'Music template'],
  ['book_template', 'Book template'],
] as const;
const qualityKeys = [
  'screen_size',
  'video_codec',
  'audio_codec',
  'audio_channels',
  'source',
  'release_group',
  'edition',
];
export function Profiles() {
  const { refresh } = useWorkspace();
  const { data: profiles, error: listError } = useResource<NamingProfile[]>('/profiles');
  const [draft, setDraft] = useState<NamingProfile | null>(null),
    [examples, setExamples] = useState<Record<string, string> | null>(null),
    [error, setError] = useState(''),
    [message, setMessage] = useState(''),
    [busy, setBusy] = useState(false);
  async function action(save: boolean) {
    if (!draft) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      if (save) {
        setDraft(await api<NamingProfile>('/profiles/' + draft.id, json('PUT', draft)));
        setMessage('Preset saved. Existing previews retain their recorded version.');
        refresh();
      } else {
        const preview = await api<{ examples: Record<string, string> }>(
          '/profiles/preview',
          json('POST', draft),
        );
        setExamples(preview.examples);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <p className="notice">
        Presets control naming for all seven collections. Saved previews keep the exact preset
        version they were created with.
      </p>
      {(error || listError) && <p role="alert">{error || listError}</p>}
      {message && (
        <p role="status" className="banner">
          {message}
        </p>
      )}
      <section className="panel">
        <div className="form-grid">
          <label className="field">
            Naming preset
            <select
              disabled={!profiles}
              value={draft?.id ?? ''}
              onChange={(e) => {
                setDraft(profiles?.find((p) => p.id === e.target.value) ?? null);
                setExamples(null);
                setError('');
              }}
            >
              <option value="">Choose a preset</option>
              {profiles?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label} · v{p.version}
                </option>
              ))}
              {draft && !profiles?.some((p) => p.id === draft.id) && (
                <option value={draft.id}>{draft.label}</option>
              )}
            </select>
          </label>
          <button
            className="secondary"
            disabled={!profiles?.length || busy}
            onClick={() => {
              if (profiles?.[0]) {
                setDraft({
                  ...profiles[0],
                  id: crypto.randomUUID(),
                  label: 'My preset',
                  version: 1,
                  kind: 'auto',
                });
                setExamples(null);
              }
            }}
          >
            New preset
          </button>
        </div>
        {draft && (
          <>
            <label className="field">
              Preset label
              <input
                value={draft.label}
                maxLength={100}
                onChange={(e) => setDraft({ ...draft, label: e.target.value })}
              />
            </label>
            <label className="field">
              Preset collection
              <select
                value={draft.kind}
                onChange={(e) =>
                  setDraft({ ...draft, kind: e.target.value as NamingProfile['kind'] })
                }
              >
                <option value="auto">All collections</option>
                {Object.entries(collections).map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            {templates.map(([key, label]) => (
              <label className="field" key={key}>
                {label}
                <input
                  value={draft[key]}
                  maxLength={500}
                  onChange={(e) => {
                    setDraft({ ...draft, [key]: e.target.value });
                    setExamples(null);
                  }}
                />
              </label>
            ))}
            <p className="notice">
              Placeholders: title, year, year_suffix, ext, quality, season, episode, episode_title,
              episode_title_suffix, artist, album, track_prefix, author, series, series_path. Use{' '}
              {'{season:02d}'} and {'{episode:02d}'} for padded episode numbers.
            </p>
            <fieldset>
              <legend>Quality tags in filename</legend>
              <div className="actions">
                {qualityKeys.map((key) => (
                  <label className="check-field" key={key}>
                    <input
                      type="checkbox"
                      checked={draft.quality_keys.includes(key)}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          quality_keys: e.target.checked
                            ? [...draft.quality_keys, key]
                            : draft.quality_keys.filter((k) => k !== key),
                        })
                      }
                    />
                    {key.replaceAll('_', ' ')}
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="actions">
              <button className="secondary" disabled={busy} onClick={() => void action(false)}>
                Preview examples
              </button>
              <button
                className="primary"
                disabled={busy || !draft.label.trim()}
                onClick={() => void action(true)}
              >
                Save preset
              </button>
            </div>
          </>
        )}
      </section>
      {examples && (
        <section className="panel">
          <h2>Fictional examples</h2>
          <p className="subtitle">
            Illustrative metadata only. Your real execution preview uses your confirmed matches and
            file paths.
          </p>
          {Object.entries(examples).map(([kind, path]) => (
            <div className="preview-item" key={kind}>
              <strong>{collections[kind as keyof typeof collections]}</strong>
              <p className="path-text">{path}</p>
            </div>
          ))}
        </section>
      )}
    </>
  );
}
