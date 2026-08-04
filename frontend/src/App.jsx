import { useEffect, useState } from 'react';

import AnswerDisplay from './components/AnswerDisplay';
import QueryInput from './components/QueryInput';
import RepositoryForm from './components/RepositoryForm';
import RepositoryList from './components/RepositoryList';
import { fetchRepositories, indexRepository, queryRepository } from './lib/api';
import './App.css';

function App() {
  const [repositories, setRepositories] = useState([]);
  const [selectedRepositoryId, setSelectedRepositoryId] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loadingRepositories, setLoadingRepositories] = useState(true);
  const [indexing, setIndexing] = useState(false);
  const [querying, setQuerying] = useState(false);

  useEffect(() => {
    let active = true;

    async function loadRepositories() {
      try {
        const payload = await fetchRepositories();
        if (!active) {
          return;
        }
        const items = payload.repositories ?? [];
        setRepositories(items);
        if (items.length > 0) {
          setSelectedRepositoryId((current) => current || items[0].repository_id);
        }
      } catch (requestError) {
        if (active) {
          setError(requestError.message);
        }
      } finally {
        if (active) {
          setLoadingRepositories(false);
        }
      }
    }

    loadRepositories();
    return () => {
      active = false;
    };
  }, []);

  const selectedRepository = repositories.find(
    (repository) => repository.repository_id === selectedRepositoryId,
  );

  const handleIndexRepository = async (repositoryUrl) => {
    setIndexing(true);
    setError('');
    setResult(null);

    try {
      const manifest = await indexRepository(repositoryUrl);
      setRepositories((current) => {
        const filtered = current.filter(
          (repository) => repository.repository_id !== manifest.repository_id,
        );
        return [manifest, ...filtered];
      });
      setSelectedRepositoryId(manifest.repository_id);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIndexing(false);
    }
  };

  const handleQuery = async (query) => {
    if (!selectedRepositoryId) {
      setError('Select a repository before running a query.');
      return;
    }

    setQuerying(true);
    setError('');
    setResult(null);

    try {
      const response = await queryRepository(selectedRepositoryId, query);
      setResult(response);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setQuerying(false);
    }
  };

  return (
    <div className="app-shell">
      <div className="backdrop-grid" aria-hidden="true" />
      <main className="workspace">
        <header className="hero">
          <p className="eyebrow">GitLore</p>
          <h1>Repository intelligence grounded in the original RAG pipeline.</h1>
          <p className="hero-copy">
            Index a public GitHub repository, preserve the original agentic workflow, and query the codebase
            through a backend-driven web application.
          </p>
        </header>

        {error && (
          <div className="error-banner" role="alert">
            {error}
          </div>
        )}

        <section className="workspace-grid">
          <div className="stack-lg">
            <RepositoryForm onIndex={handleIndexRepository} loading={indexing} />
            <RepositoryList
              repositories={repositories}
              selectedRepositoryId={selectedRepositoryId}
              onSelect={setSelectedRepositoryId}
            />
          </div>

          <div className="stack-lg">
            <QueryInput
              repositoryLabel={
                selectedRepository
                  ? `${selectedRepository.owner}/${selectedRepository.repo}`
                  : ''
              }
              disabled={loadingRepositories || indexing || !selectedRepositoryId}
              loading={querying}
              onSubmit={handleQuery}
            />
            <AnswerDisplay result={result} loading={querying} />
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
