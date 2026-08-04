import { useState } from 'react';

export default function QueryInput({ repositoryLabel, disabled, loading, onSubmit }) {
  const [query, setQuery] = useState('');

  const handleSubmit = (event) => {
    event.preventDefault();
    const value = query.trim();
    if (!value || disabled || loading) {
      return;
    }
    onSubmit(value);
  };

  return (
    <section className="panel">
      <div className="panel-header">
        <p className="eyebrow">Question Console</p>
        <h2>Ask about the indexed codebase</h2>
      </div>

      <form className="stack-md" onSubmit={handleSubmit}>
        <div className="query-meta">
          <span className="status-dot" aria-hidden="true" />
          <span className="mono">{repositoryLabel || 'No repository selected'}</span>
        </div>
        <label className="field-label" htmlFor="repository-query">
          Natural language query
        </label>
        <textarea
          id="repository-query"
          className="text-area"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          disabled={disabled || loading}
          placeholder="Explain the project architecture and how the ingestion pipeline interacts with retrieval."
          rows={5}
        />
        <div className="field-actions">
          <p className="helper-text">
            Ask about architecture, technologies, file responsibilities, data flow, or implementation details.
          </p>
          <button className="primary-button" type="submit" disabled={disabled || loading || !query.trim()}>
            {loading ? 'Analyzing…' : 'Run Query'}
          </button>
        </div>
      </form>
    </section>
  );
}
