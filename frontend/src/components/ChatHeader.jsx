export default function ChatHeader({ repositories, selectedRepositoryId, onSelect, onIndexNew }) {
  return (
    <header className="chat-header">
      <div>
        <p className="eyebrow">GitLore</p>
        <p className="chat-header-title">Repository chat</p>
      </div>

      <div className="chat-header-controls">
        <label className="sr-only" htmlFor="repository-selector">
          Repository
        </label>
        <select
          id="repository-selector"
          className="repo-select mono"
          value={selectedRepositoryId}
          onChange={(event) => onSelect(event.target.value)}
        >
          {repositories.map((repository) => (
            <option key={repository.repository_id} value={repository.repository_id}>
              {repository.owner}/{repository.repo}
            </option>
          ))}
        </select>
        <button className="secondary-button" type="button" onClick={onIndexNew}>
          + Index New Repo
        </button>
      </div>
    </header>
  );
}
