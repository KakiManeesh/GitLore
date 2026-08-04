import { useState } from 'react';

export default function RepositoryForm({ onIndex, loading }) {
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
    <section className="panel panel-accent">
      <div className="panel-header">
        <p className="eyebrow">Repository Intake</p>
        <h2>Index a public GitHub repository</h2>
      </div>

      <form className="stack-md" onSubmit={handleSubmit}>
        <label className="field-label" htmlFor="repository-url">
          Repository URL or <span className="mono">owner/repo</span>
        </label>
        <div className="field-row">
          <input
            id="repository-url"
            className="text-input"
            type="text"
            value={repositoryUrl}
            onChange={(event) => setRepositoryUrl(event.target.value)}
            placeholder="https://github.com/vercel/next.js"
            disabled={loading}
          />
          <button className="primary-button" type="submit" disabled={loading || !repositoryUrl.trim()}>
            {loading ? 'Indexing…' : 'Index Repository'}
          </button>
        </div>
        <p className="helper-text">
          GitLore clones the repository, pulls GitHub context, chunks the codebase, and loads the result into Chroma.
        </p>
      </form>
    </section>
  );
}
