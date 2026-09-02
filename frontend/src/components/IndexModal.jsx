import { useEffect, useRef, useState } from 'react';

import { IndexingProgress } from './OnboardingScreen';

export default function IndexModal({ open, onClose, onIndex, loading, error }) {
  const [repositoryUrl, setRepositoryUrl] = useState('');
  const inputRef = useRef(null);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    inputRef.current?.focus();

    const handleKeyDown = (event) => {
      if (event.key === 'Escape' && !loading) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [loading, onClose, open]);

  useEffect(() => {
    if (!open) {
      setRepositoryUrl('');
    }
  }, [open]);

  if (!open) {
    return null;
  }

  const handleSubmit = (event) => {
    event.preventDefault();
    const value = repositoryUrl.trim();
    if (!value || loading) {
      return;
    }
    onIndex(value);
  };

  const handleOverlayClick = () => {
    if (!loading) {
      onClose();
    }
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="index-modal-title" onClick={handleOverlayClick}>
      <section className="modal-panel panel panel-accent" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <p className="eyebrow" id="index-modal-title">
            Index New Repository
          </p>
          <button className="modal-close" type="button" aria-label="Close" onClick={onClose} disabled={loading}>
            x
          </button>
        </div>

        <form className="stack-md" onSubmit={handleSubmit}>
          <label className="field-label" htmlFor="modal-repo-url">
            Repository URL or <span className="mono">owner/repo</span>
          </label>
          <div className="field-row">
            <input
              id="modal-repo-url"
              ref={inputRef}
              className="text-input"
              type="text"
              value={repositoryUrl}
              onChange={(event) => setRepositoryUrl(event.target.value)}
              placeholder="octocat/Hello-World"
              disabled={loading}
              autoComplete="off"
            />
            <button className="primary-button" type="submit" disabled={loading || !repositoryUrl.trim()}>
              {loading ? 'Indexing...' : 'Index'}
            </button>
          </div>
          {loading && <IndexingProgress />}
          {error && (
            <p className="onboarding-error" role="alert">
              {error}
            </p>
          )}
        </form>
      </section>
    </div>
  );
}
