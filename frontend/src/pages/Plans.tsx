import { useState } from 'react';
import { api, json } from '../api/client';
import { useResource } from '../api/useResource';
import { useWorkspace } from '../state/WorkspaceProvider';
import { navigate } from '../state/navigation';
import { type Plan, type Destination, type Job, type NamingProfile } from '../types';
import { PlanPreview } from '../components/PlanPreview';
export function Plans() {
  const { selected, setSelected, currentPlan, setCurrentPlan, settings, refresh } = useWorkspace();
  const { data: plans, error: listError } = useResource<Plan[]>('/plans'),
    { data: destinations } = useResource<Destination[]>('/destinations');
  const { data: profiles } = useResource<NamingProfile[]>('/profiles');
  const [profileId, setProfileId] = useState('');
  const [destination, setDestination] = useState(settings?.default_destination ?? ''),
    [inPlace, setInPlace] = useState(false),
    [conflict, setConflict] = useState('block'),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [validated, setValidated] = useState(''),
    [confirmed, setConfirmed] = useState(false);
  const identity = currentPlan ? currentPlan.id + ':' + currentPlan.revision : '';
  async function action(work: () => Promise<void>) {
    setBusy(true);
    setError('');
    try {
      await work();
    } catch (e) {
      setError((e as Error).message);
      setValidated('');
    } finally {
      setBusy(false);
    }
  }
  async function open(id: string) {
    await action(async () => {
      setCurrentPlan(await api<Plan>('/plans/' + id));
      setValidated('');
      setConfirmed(false);
    });
  }
  async function create() {
    await action(async () => {
      setCurrentPlan(
        await api<Plan>(
          '/plans',
          json('POST', {
            item_ids: selected,
            options: {
              destination_id: inPlace ? null : destination,
              in_place: inPlace,
              conflict,
              profile_id: profileId || null,
            },
          }),
        ),
      );
      setValidated('');
      setConfirmed(false);
      refresh();
    });
  }
  async function revalidate() {
    if (!currentPlan) return;
    await action(async () => {
      const checked = await api<Plan>(
        '/plans/' + currentPlan.id + '/revalidate',
        json('POST', { revision: currentPlan.revision }),
      );
      setCurrentPlan(checked);
      setValidated(checked.issues.length ? '' : checked.id + ':' + checked.revision);
      setConfirmed(false);
    });
  }
  async function execute() {
    if (!currentPlan) return;
    await action(async () => {
      await api<Job>(
        '/plans/' + currentPlan.id + '/execute',
        json('POST', { revision: currentPlan.revision }),
      );
      setSelected([]);
      setValidated('');
      setConfirmed(false);
      refresh();
      navigate('jobs');
    });
  }
  return (
    <>
      <p className="notice">
        A preview records exact paths and source identities. Creating it leaves files untouched.
        Existing files are never overwritten.
      </p>
      {!!selected.length && (
        <section className="panel">
          <h2>Create a preview</h2>
          <p className="subtitle">{selected.length} confirmed items selected</p>
          <label className="field">
            Naming preset
            <select value={profileId} onChange={(e) => setProfileId(e.target.value)}>
              <option value="">Default naming</option>
              {profiles?.map((p) => (
                <option value={p.id} key={p.id}>
                  {p.label} · v{p.version}
                </option>
              ))}
            </select>
          </label>
          <div className="form-grid">
            <label className="field">
              Destination
              <select
                value={destination}
                disabled={inPlace}
                onChange={(e) => setDestination(e.target.value)}
              >
                <option value="">Select a destination</option>
                {destinations?.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.label} · {d.path}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              When a path already exists
              <select value={conflict} onChange={(e) => setConflict(e.target.value)}>
                <option value="block">Stop for review</option>
                <option value="skip">Skip conflicting members</option>
                <option value="keep_both">Keep separate versions</option>
              </select>
            </label>
          </div>
          <label className="check-field">
            <input
              type="checkbox"
              checked={inPlace}
              onChange={(e) => setInPlace(e.target.checked)}
            />
            Rename in place (music and books)
          </label>
          <div className="actions">
            <button
              className="primary"
              disabled={busy || (!inPlace && !destination)}
              onClick={() => void create()}
            >
              Create preview
            </button>
            <button className="text-button" onClick={() => navigate('review')}>
              Change selection
            </button>
          </div>
        </section>
      )}
      {(error || listError) && <p role="alert">{error || listError}</p>}
      {currentPlan && (
        <section className="panel plan-detail">
          <PlanPreview plan={currentPlan} />
          <p className="notice">
            Revalidate to check current files, free space and destination access. Changed conditions
            require a new preview.
          </p>
          <label className="check-field">
            <input
              type="checkbox"
              checked={confirmed}
              disabled={busy || validated !== identity || !!currentPlan.issues.length}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            I reviewed these paths and approve the changes
          </label>
          <div className="actions">
            <button className="secondary" disabled={busy} onClick={() => void revalidate()}>
              Revalidate
            </button>
            <button
              className="primary"
              disabled={
                busy ||
                !confirmed ||
                validated !== identity ||
                !!currentPlan.issues.length ||
                !currentPlan.operations.length
              }
              onClick={() => void execute()}
            >
              Organise
            </button>
          </div>
        </section>
      )}
      <section className="panel">
        <h2>Saved previews</h2>
        {plans?.length ? (
          plans.map((plan) => (
            <div className="saved-plan" key={plan.id}>
              <div>
                <strong>Plan {plan.id.slice(0, 8)}</strong>
                <p>
                  {plan.operations.length} operations · {plan.issues.length} preflight issues
                </p>
              </div>
              <button
                className="secondary"
                aria-label={'Open plan ' + plan.id}
                onClick={() => void open(plan.id)}
                disabled={busy}
              >
                Open preview
              </button>
            </div>
          ))
        ) : (
          <p className="subtitle">
            Select confirmed items in a collection or match review to create your first preview.
          </p>
        )}
      </section>
    </>
  );
}
