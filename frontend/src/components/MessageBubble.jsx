function MetadataList({ items }) {
  if (!items?.length) {
    return <p className="helper-text">None reported.</p>;
  }

  return (
    <ul className="compact-list">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

export default function MessageBubble({ entry }) {
  if (entry.type === 'user') {
    return (
      <div className="bubble-row bubble-row--user">
        <div className="bubble bubble--user">{entry.query}</div>
      </div>
    );
  }

  if (entry.type === 'loading') {
    return (
      <div className="bubble-row bubble-row--assistant">
        <div className="bubble bubble--loading loading-block" aria-label="Loading answer" aria-busy="true">
          <div className="loading-line wide" />
          <div className="loading-line medium" />
        </div>
      </div>
    );
  }

  if (entry.type === 'error') {
    return (
      <div className="bubble-row bubble-row--assistant">
        <div className="bubble bubble--error" role="alert">
          {entry.message}
        </div>
      </div>
    );
  }

  if (entry.type === 'assistant') {
    const result = entry.result;

    return (
      <div className="bubble-row bubble-row--assistant">
        <article className="bubble bubble--assistant">
          <p className="reinterpreted-label mono">
            reinterpreted as: <em>{result.clarified_question}</em>
          </p>
          <div className="answer-text">{result.answer}</div>

          <details className="result-metadata">
            <summary className="eyebrow">Details</summary>
            <div className="result-grid">
              <div className="result-card">
                <p className="card-label">Documents retrieved</p>
                <p className="result-number">{result.documents_retrieved ?? 0}</p>
              </div>
              <div className="result-card">
                <p className="card-label">Covered aspects</p>
                <MetadataList items={result.aspects} />
              </div>
              <div className="result-card">
                <p className="card-label">Subqueries</p>
                <MetadataList items={result.subqueries} />
              </div>
              <div className="result-card">
                <p className="card-label">Repository</p>
                <p className="mono">{result.repository_id}</p>
              </div>
            </div>
          </details>
        </article>
      </div>
    );
  }

  return null;
}
