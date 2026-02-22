type Props = {
  title: string;
  onConfirm: () => Promise<void> | void;
  onDismiss: () => void;
};

export function ClaimSubmissionModal({ title, onConfirm, onDismiss }: Props) {
  return (
    <div className="modal-backdrop">
      <div className="modal-card">
        <h3>Did you submit this claim?</h3>
        <p className="muted">
          We noticed you opened the claim form for <strong>{title}</strong>. This helps us improve matching quality.
        </p>
        <div className="toolbar">
          <button onClick={onConfirm}>Yes, I submitted</button>
          <button className="ghost-btn" onClick={onDismiss}>
            Not yet
          </button>
        </div>
      </div>
    </div>
  );
}
