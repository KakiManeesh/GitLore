export default function RepositoryList({ repositories, selectedRepositoryId, onSelect }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <p className="eyebrow">Indexed Repositories</p>
        <h2>Available knowledge bases</h2>
      </div>

      {repositories.length === 0 ? (
        <div className="empty-state" role="status">
          <p>No repositories indexed yet.</p>
          <span>Start by indexing a public GitHub repository above.</span>
        </div>
      ) : (
        <div className="repo-list" role="list">
          {repositories.map((repository) => {
            const isSelected = repository.repository_id === selectedRepositoryId;
            const language = repository.metadata?.primary_language || 'Unknown';
            const description = repository.metadata?.description || 'No description available.';

            return (
              <button
                key={repository.repository_id}
                type="button"
                className={`repo-card${isSelected ? ' is-selected' : ''}`}
                onClick={() => onSelect(repository.repository_id)}
              >
                <div className="repo-card-top">
                  <div>
                    <p className="repo-name">{repository.owner}/{repository.repo}</p>
                    <p className="repo-id mono">{repository.repository_id}</p>
                  </div>
                  <span className="repo-language">{language}</span>
                </div>
                <p className="repo-description">{description}</p>
                <div className="repo-stats mono">
                  <span>{repository.stats?.chunks ?? 0} chunks</span>
                  <span>{repository.stats?.commits ?? 0} commits</span>
                  <span>{repository.stats?.issues ?? 0} issues</span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
