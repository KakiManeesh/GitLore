import { useEffect, useRef } from 'react';

import MessageBubble from './MessageBubble';

export default function ChatThread({ thread }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' });
  }, [thread]);

  return (
    <div className="chat-thread" aria-live="polite">
      {thread.map((entry) => (
        <MessageBubble key={entry.id} entry={entry} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
