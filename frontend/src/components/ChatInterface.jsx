import ChatHeader from './ChatHeader';
import ChatInput from './ChatInput';
import ChatThread from './ChatThread';

export default function ChatInterface({
  repositories,
  selectedRepositoryId,
  onSelectRepository,
  thread,
  querying,
  onQuery,
  onIndexNew,
}) {
  return (
    <main className="chat-shell">
      <ChatHeader
        repositories={repositories}
        selectedRepositoryId={selectedRepositoryId}
        onSelect={onSelectRepository}
        onIndexNew={onIndexNew}
      />
      <ChatThread thread={thread} />
      <ChatInput onSubmit={onQuery} disabled={querying || !selectedRepositoryId} />
    </main>
  );
}
