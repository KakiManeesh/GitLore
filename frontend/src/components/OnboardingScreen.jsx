import { useState } from 'react';

export function IndexingProgress() {
  return (
    <div className="indexing-progress loading-block" role="status" aria-live="polite">
      <p className="helper-text mono">Cloning and indexing repository...</p>
      <div className="loading-line wide" />
      <div className="loading-line medium" />
    </div>
  );
}

export default function OnboardingScreen({ onIndex, loading, error }) {
  const [repositoryUrl, setRepositoryUrl] = useState('');

  const handleSubmit = (event) => {
    event.preventDefault();
    const value = repositoryUrl.trim();
    if (!value || loading) {
      return;
    }
    onIndex(value);
  };

  return (
    <main className="onboarding-shell">
      <section className="onboarding-card panel panel-accent" aria-labelledby="onboarding-title">
        <header className="onboarding-header">
          <p className="eyebrow">GitLore</p>
          <h1 id="onboarding-title">Repository intelligence.</h1>
          <p className="hero-copy">Index a public GitHub repo to start querying.</p>
        </header>

        <form className="stack-md" onSubmit={handleSubmit}>
          <label className="field-label" htmlFor="onboarding-repository-url">
            Repository URL or <span className="mono">owner/repo</span>
          </label>
          <div className="field-row">
            <input
              id="onboarding-repository-url"
              className="text-input"
              type="text"
              value={repositoryUrl}
              onChange={(event) => setRepositoryUrl(event.target.value)}
              placeholder="https://github.com/fastapi/typer"
              disabled={loading}
              autoComplete="off"
            />
            <button className="primary-button" type="submit" disabled={loading || !repositoryUrl.trim()}>
              {loading ? 'Indexing...' : 'Index Repository'}
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
    </main>
  );
}
