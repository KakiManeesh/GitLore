function LoadingState() {
  return (
    <section className="panel">
      <div className="panel-header">
        <p className="eyebrow">Result</p>
        <h2>Working through the repository</h2>
      </div>
      <div className="loading-block" aria-busy="true" aria-label="Loading answer">
        <div className="loading-line wide" />
        <div className="loading-line medium" />
        <div className="loading-box" />
      </div>
    </section>
  );
}

export default function AnswerDisplay({ result, loading }) {
  if (loading) {
    return <LoadingState />;
  }

  if (!result) {
    return (
      <section className="panel">
        <div className="panel-header">
          <p className="eyebrow">Result</p>
          <h2>Answer output</h2>
        </div>
        <div className="empty-state" role="status">
          <p>No answer yet.</p>
          <span>Index a repository, select it, then run a query.</span>
        </div>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <p className="eyebrow">Answer Output</p>
        <h2>{result.clarified_question}</h2>
      </div>

      <div className="answer-text">{result.answer}</div>

      <div className="result-grid">
        <div className="result-card">
          <p className="card-label">Repository</p>
          <p className="mono">{result.repository_id}</p>
        </div>
        <div className="result-card">
          <p className="card-label">Documents retrieved</p>
          <p className="result-number">{result.documents_retrieved}</p>
        </div>
        <div className="result-card">
          <p className="card-label">Covered aspects</p>
          <ul className="compact-list">
            {result.aspects?.map((aspect) => (
              <li key={aspect}>{aspect}</li>
            ))}
          </ul>
        </div>
        <div className="result-card">
          <p className="card-label">Subqueries</p>
          <ul className="compact-list">
            {result.subqueries?.map((subquery) => (
              <li key={subquery}>{subquery}</li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
