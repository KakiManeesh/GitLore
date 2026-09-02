import { useRef, useState } from 'react';

export default function ChatInput({ onSubmit, disabled }) {
  const [value, setValue] = useState('');
  const textareaRef = useRef(null);

  const resetHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const growToContent = (element) => {
    element.style.height = 'auto';
    element.style.height = `${Math.min(element.scrollHeight, 160)}px`;
  };

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) {
      return;
    }
    onSubmit(trimmed);
    setValue('');
    requestAnimationFrame(resetHeight);
  };

  const handleChange = (event) => {
    setValue(event.target.value);
    growToContent(event.target);
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <form
      className="chat-input-bar"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <label className="sr-only" htmlFor="chat-query">
        Ask about the codebase
      </label>
      <textarea
        id="chat-query"
        ref={textareaRef}
        className="chat-textarea"
        rows={1}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder="Ask about the codebase..."
      />
      <button className="primary-button" type="submit" disabled={disabled || !value.trim()}>
        Send
      </button>
    </form>
  );
}
