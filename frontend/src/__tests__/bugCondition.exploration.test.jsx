/**
 * Bug Condition Exploration Tests — Task 1
 *
 * These tests MUST FAIL on the UNFIXED App.jsx code.
 * Failure of these tests proves the bugs exist.
 * They will PASS after the fix is applied (Task 12).
 *
 * COUNTEREXAMPLES DOCUMENTED (filled in after first run):
 *
 * Test 1 — Static layout on empty state:
 *   FAILS because: App.jsx renders <QueryInput> and <AnswerDisplay> unconditionally
 *   regardless of repository count. The textarea#repository-query and "No answer yet."
 *   text are present in the DOM even when fetchRepositories returns [].
 *
 * Test 2 — No thread append:
 *   FAILS because: App.jsx stores result as scalar useState(null). The second query
 *   call overwrites the first result. There is no thread array — thread.length check
 *   via aria roles/data finds < 4 entries after two queries.
 *
 * Test 3 — Page-level error on query failure:
 *   FAILS because: App.jsx has `const [error, setError] = useState('')` rendered as
 *   a top-level <div className="error-banner"> on the page. No .bubble--error class
 *   exists in the unfixed code; errors surface at the page root, not inline.
 *
 * Test 4 — No inline loading bubble:
 *   FAILS because: App.jsx shows no .bubble--loading or .chat-thread element.
 *   Loading state is handled by <AnswerDisplay loading={querying}> which renders a
 *   top-level <LoadingState> panel, not an inline thread entry.
 */

import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import App from '../App';

// ── Mock the entire API module ───────────────────────────────────────────────
vi.mock('../lib/api', () => ({
  fetchRepositories: vi.fn(),
  indexRepository: vi.fn(),
  queryRepository: vi.fn(),
}));

import { fetchRepositories, queryRepository } from '../lib/api';

const MOCK_REPO = {
  repository_id: 'repo-abc-123',
  owner: 'testowner',
  repo: 'testrepo',
  url: 'https://github.com/testowner/testrepo',
};

const MOCK_QUERY_RESULT = {
  answer: 'This is the answer text.',
  clarified_question: 'What is the architecture?',
  subqueries: ['sub1', 'sub2'],
  aspects: ['aspect1'],
  documents_retrieved: 5,
  repository_id: 'repo-abc-123',
};

beforeEach(() => {
  vi.resetAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── Test 1: Static layout on empty state ─────────────────────────────────────
describe('Bug 1.1 — Static layout on empty state', () => {
  it('should NOT render chat input or answer panel when there are no repositories', async () => {
    // fetchRepositories returns empty list
    fetchRepositories.mockResolvedValue({ repositories: [] });

    render(<App />);

    // Wait for the async mount effect to complete
    await waitFor(() => {
      expect(fetchRepositories).toHaveBeenCalled();
    });

    // On the FIXED code:
    //   - Only the onboarding screen renders (no chat input, no answer panel)
    // On the UNFIXED code:
    //   - QueryInput renders with textarea#repository-query
    //   - AnswerDisplay renders with "No answer yet."
    //   → Test FAILS because these elements ARE present in unfixed code

    const queryTextarea = document.querySelector('textarea#repository-query');
    expect(queryTextarea).not.toBeInTheDocument();

    const answerPanel = screen.queryByText('No answer yet.');
    expect(answerPanel).not.toBeInTheDocument();
  });
});

// ── Test 2: No thread append ─────────────────────────────────────────────────
describe('Bug 1.3 — No thread append (scalar result replaces rather than appends)', () => {
  it('should have at least 4 thread entries after two sequential queries', async () => {
    fetchRepositories.mockResolvedValue({ repositories: [MOCK_REPO] });
    queryRepository.mockResolvedValue(MOCK_QUERY_RESULT);

    render(<App />);

    // Wait for repositories to load
    await waitFor(() => {
      expect(fetchRepositories).toHaveBeenCalled();
    });

    // Submit first query via the textarea and "Run Query" button
    // In the FIXED app these will be chat-textarea + Send button
    // In the UNFIXED app these are textarea#repository-query + "Run Query" button
    // We target whichever textarea is present to send the query.
    const textarea = document.querySelector('textarea');
    expect(textarea).not.toBeNull(); // one must exist to submit

    // First query
    await act(async () => {
      fireEvent.change(textarea, { target: { value: 'First query' } });
      fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    });

    // If enter doesn't work (unfixed uses form submit), try clicking the submit button
    const submitButton =
      screen.queryByRole('button', { name: /send/i }) ||
      screen.queryByRole('button', { name: /run query/i });
    if (submitButton) {
      await act(async () => {
        fireEvent.click(submitButton);
      });
    }

    await waitFor(() => {
      expect(queryRepository).toHaveBeenCalledTimes(1);
    });

    // Second query
    await act(async () => {
      const ta = document.querySelector('textarea');
      fireEvent.change(ta, { target: { value: 'Second query' } });
      fireEvent.keyDown(ta, { key: 'Enter', shiftKey: false });
    });

    const submitButton2 =
      screen.queryByRole('button', { name: /send/i }) ||
      screen.queryByRole('button', { name: /run query/i });
    if (submitButton2) {
      await act(async () => {
        fireEvent.click(submitButton2);
      });
    }

    await waitFor(() => {
      expect(queryRepository).toHaveBeenCalledTimes(2);
    });

    // On the FIXED code: thread has ≥ 4 entries (2 user + 2 assistant bubbles)
    // On the UNFIXED code: thread concept doesn't exist → < 4 bubble elements
    // → Test FAILS because .bubble-row elements don't exist in unfixed code

    await waitFor(() => {
      const bubbles = document.querySelectorAll('.bubble-row');
      expect(bubbles.length).toBeGreaterThanOrEqual(4);
    });
  });
});

// ── Test 3: Page-level error on query failure ─────────────────────────────────
describe('Bug 1.5 — Page-level error on query failure (should be inline)', () => {
  it('should show error inline in chat thread, NOT as a top-level error banner', async () => {
    fetchRepositories.mockResolvedValue({ repositories: [MOCK_REPO] });
    queryRepository.mockRejectedValue(new Error('Internal Server Error'));

    render(<App />);

    await waitFor(() => {
      expect(fetchRepositories).toHaveBeenCalled();
    });

    // Submit a query that will fail
    const textarea = document.querySelector('textarea');
    await act(async () => {
      fireEvent.change(textarea, { target: { value: 'Failing query' } });
    });

    const submitButton =
      screen.queryByRole('button', { name: /send/i }) ||
      screen.queryByRole('button', { name: /run query/i });
    if (submitButton) {
      await act(async () => {
        fireEvent.click(submitButton);
      });
    } else {
      await act(async () => {
        fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
      });
    }

    await waitFor(() => {
      expect(queryRepository).toHaveBeenCalledTimes(1);
    });

    // Wait briefly for error to appear
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    // On the FIXED code:
    //   - A .bubble--error inside .chat-thread appears
    //   - NO top-level .error-banner outside the thread
    // On the UNFIXED code:
    //   - A top-level .error-banner IS present (fails assertion 1)
    //   - No .bubble--error exists at all (fails assertion 2)

    // Assert 1: No top-level error banner outside the chat thread
    const topLevelBanner = document.querySelector('.error-banner');
    expect(topLevelBanner).not.toBeInTheDocument();

    // Assert 2: An inline error bubble IS present in the thread
    const inlineBubble = document.querySelector('.bubble--error');
    expect(inlineBubble).toBeInTheDocument();
  });
});

// ── Test 4: No inline loading bubble ─────────────────────────────────────────
describe('Bug 1.4 — No inline loading bubble (loading shown at page level, not inline)', () => {
  it('should show a .bubble--loading entry inside a .chat-thread during query in-flight', async () => {
    fetchRepositories.mockResolvedValue({ repositories: [MOCK_REPO] });

    // Never-resolving promise: query stays in-flight so we can inspect loading state
    let resolveQuery;
    const pendingQuery = new Promise((resolve) => {
      resolveQuery = resolve;
    });
    queryRepository.mockReturnValue(pendingQuery);

    render(<App />);

    await waitFor(() => {
      expect(fetchRepositories).toHaveBeenCalled();
    });

    // Submit a query
    const textarea = document.querySelector('textarea');
    await act(async () => {
      fireEvent.change(textarea, { target: { value: 'What is the architecture?' } });
    });

    const submitButton =
      screen.queryByRole('button', { name: /send/i }) ||
      screen.queryByRole('button', { name: /run query/i });

    await act(async () => {
      if (submitButton) {
        fireEvent.click(submitButton);
      } else {
        fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
      }
    });

    await waitFor(() => {
      expect(queryRepository).toHaveBeenCalledTimes(1);
    });

    // On the FIXED code:
    //   - A .bubble--loading entry appears inside .chat-thread
    // On the UNFIXED code:
    //   - No .chat-thread exists; AnswerDisplay shows a top-level LoadingState panel
    //   → Test FAILS because .bubble--loading is absent in unfixed code

    const chatThread = document.querySelector('.chat-thread');
    expect(chatThread).toBeInTheDocument();

    const loadingBubble = document.querySelector('.bubble--loading');
    expect(loadingBubble).toBeInTheDocument();

    // Clean up the pending promise
    resolveQuery(MOCK_QUERY_RESULT);
  });
});
