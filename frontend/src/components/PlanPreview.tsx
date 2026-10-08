import { type Plan, bytes } from '../types';
export function PlanPreview({ plan }: { plan: Plan }) {
  const size = plan.operations.reduce(
    (sum, op) => sum + Number(op.expected_signature.size ?? 0),
    0,
  );
  return (
    <section>
      <div className="section-head">
        <h2>Path preview</h2>
        <span className="muted">
          Revision {plan.revision} · {plan.operations.length} operations · {bytes(size)}
        </span>
      </div>
      {plan.issues.length > 0 && (
        <div className="issues" role="alert">
          <strong>Review required</strong>
          {plan.issues.map((issue, i) => (
            <p key={i}>
              {issue.detail}
              <small>{issue.code.replaceAll('_', ' ')}</small>
            </p>
          ))}
        </div>
      )}
      {!!plan.warnings?.length && (
        <div className="notice">
          <strong>Optional output notes</strong>
          {plan.warnings.map((warning, i) => (
            <p key={i}>{warning.detail}</p>
          ))}
        </div>
      )}
      {plan.operations.length === 0 && <p className="notice">This preview has no file changes.</p>}
      {plan.operations.map((op) => (
        <article className="preview-item" key={op.id}>
          <div className="operation-head">
            <strong>{op.kind === 'move' ? 'Move file' : op.kind.replaceAll('_', ' ')}</strong>
            <span className="muted">
              {op.verification.transfer_mode === 'copy'
                ? 'Cross-volume copy → verify → finalise → remove source'
                : op.verification.transfer_mode === 'rename'
                  ? 'Same-volume rename → verify'
                  : op.kind.startsWith('create_')
                    ? 'Create temporary output → verify → publish without overwrite'
                    : op.kind === 'remove_created'
                      ? 'Remove only unchanged output created by this batch'
                      : 'Transfer verified before source removal'}
            </span>
          </div>
          <div className="path-preview">
            <span>FROM</span>
            <code>{op.source}</code>
            <span className="destination">TO</span>
            <code>{op.destination}</code>
          </div>
        </article>
      ))}
    </section>
  );
}
