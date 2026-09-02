import { useEffect, useState } from 'react';

import ChatInterface from './components/ChatInterface';
import IndexModal from './components/IndexModal';
import OnboardingScreen from './components/OnboardingScreen';
import { fetchRepositories, indexRepository, queryRepository } from './lib/api';
import './App.css';

function createEntryId() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function replaceThreadEntry(thread, entryId, replacement) {
  return thread.map((entry) => (entry.id === entryId ? replacement : entry));
}

function App() {
  const [phase, setPhase] = useState('onboarding');
  const [repositories, setRepositories] = useState([]);
  const [selectedRepositoryId, setSelectedRepositoryId] = useState('');
  const [thread, setThread] = useState([]);
  const [loadingRepositories, setLoadingRepositories] = useState(true);
  const [indexing, setIndexing] = useState(false);
  const [querying, setQuerying] = useState(false);
  const [indexError, setIndexError] = useState('');
  const [modalOpen, setModalOpen] = useState(false);

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
          setPhase('chat');
        } else {
          setPhase('onboarding');
        }
      } catch (requestError) {
        if (!active) {
          return;
        }
        setIndexError(requestError.message);
        setPhase('onboarding');
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

  const handleIndexRepository = async (repositoryUrl) => {
    setIndexing(true);
    setIndexError('');

    try {
      const manifest = await indexRepository(repositoryUrl);
      setRepositories((current) => {
        const filtered = current.filter(
          (repository) => repository.repository_id !== manifest.repository_id,
        );
        return [manifest, ...filtered];
      });
      setSelectedRepositoryId(manifest.repository_id);
      setPhase('chat');
      setModalOpen(false);
    } catch (requestError) {
      setIndexError(requestError.message);
    } finally {
      setIndexing(false);
    }
  };

  const handleQuery = async (query) => {
    if (!selectedRepositoryId || querying) {
      return;
    }

    const userEntry = { id: createEntryId(), type: 'user', query };
    const loadingId = createEntryId();
    const loadingEntry = { id: loadingId, type: 'loading' };

    setThread((current) => [...current, userEntry, loadingEntry]);
    setQuerying(true);

    try {
      const response = await queryRepository(selectedRepositoryId, query);
      setThread((current) =>
        replaceThreadEntry(current, loadingId, {
          id: loadingId,
          type: 'assistant',
          result: response,
        }),
      );
    } catch (requestError) {
      setThread((current) =>
        replaceThreadEntry(current, loadingId, {
          id: loadingId,
          type: 'error',
          message: requestError.message,
        }),
      );
    } finally {
      setQuerying(false);
    }
  };

  let content;
  if (loadingRepositories) {
    content = (
      <main className="onboarding-shell">
        <div className="onboarding-card panel" role="status" aria-busy="true">
          <div className="loading-block">
            <div className="loading-line wide" />
            <div className="loading-line medium" />
            <div className="loading-box" />
          </div>
        </div>
      </main>
    );
  } else if (phase === 'chat') {
    content = (
      <>
        <ChatInterface
          repositories={repositories}
          selectedRepositoryId={selectedRepositoryId}
          onSelectRepository={setSelectedRepositoryId}
          thread={thread}
          querying={querying}
          onQuery={handleQuery}
          onIndexNew={() => {
            setIndexError('');
            setModalOpen(true);
          }}
        />
        <IndexModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          onIndex={handleIndexRepository}
          loading={indexing}
          error={indexError}
        />
      </>
    );
  } else {
    content = <OnboardingScreen onIndex={handleIndexRepository} loading={indexing} error={indexError} />;
  }

  return (
    <div className="app-shell">
      <div className="backdrop-grid" aria-hidden="true" />
      {content}
    </div>
  );
}

export default App;
