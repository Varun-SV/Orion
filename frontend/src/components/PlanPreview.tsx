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
