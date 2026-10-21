import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen } from '@testing-library/react';

interface Pending {
  signal: AbortSignal;
  url: string;
  resolve: (value: unknown) => void;
  reject: (reason: unknown) => void;
}

const pending: Pending[] = [];

vi.mock('../../services/api', () => ({
  apiClient: {
    get: vi.fn((url: string, config: { signal: AbortSignal }) =>
      new Promise((resolve, reject) => {
        const p: Pending = { signal: config.signal, url, resolve, reject };
        pending.push(p);
        config.signal.addEventListener('abort', () => {
          reject(Object.assign(new Error('canceled'), { code: 'ERR_CANCELED', name: 'CanceledError' }));
        });
      })
    ),
  },
}));

import { apiClient } from '../../services/api';
import { DocumentViewerModal } from './DocumentViewerModal';

const NETWORK_MSG = 'לא ניתן לטעון את המסמך. בדוק את החיבור לשרת ונסה שוב.';

const ok = (type: string) => ({ data: new Blob(['x']), headers: { 'content-type': type } });
const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });

const props = { isOpen: true, batchId: 'b1', documentId: 'd1', onClose: () => {} };

let created = 0;
let createSpy: ReturnType<typeof vi.fn<[], string>>;
let revokeSpy: ReturnType<typeof vi.fn<[string], void>>;

beforeEach(() => {
  pending.length = 0;
  created = 0;
  createSpy = vi.fn<[], string>(() => `blob:mock-${++created}`);
  revokeSpy = vi.fn<[string], void>();
  (URL as any).createObjectURL = createSpy;
  (URL as any).revokeObjectURL = revokeSpy;
  vi.mocked(apiClient.get).mockClear();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('DocumentViewerModal request lifecycle', () => {
  it('passes a signal and aborts it when the modal closes', () => {
    const { rerender } = render(<DocumentViewerModal {...props} />);
    expect(pending).toHaveLength(1);
    expect(pending[0].signal.aborted).toBe(false);
    rerender(<DocumentViewerModal {...props} isOpen={false} />);
    expect(pending[0].signal.aborted).toBe(true);
  });

  it('aborts on document change and issues a fresh live request', () => {
    const { rerender } = render(<DocumentViewerModal {...props} />);
    rerender(<DocumentViewerModal {...props} documentId="d2" />);
    expect(pending).toHaveLength(2);
    expect(pending[0].signal.aborted).toBe(true);
    expect(pending[1].signal.aborted).toBe(false);
    expect(pending[1].url).toContain('/documents/d2');
  });

  it('aborts on unmount', () => {
    const { unmount } = render(<DocumentViewerModal {...props} />);
    unmount();
    expect(pending[0].signal.aborted).toBe(true);
  });

  it('does not refetch when only unrelated props/pageIndex change', () => {
    const { rerender } = render(<DocumentViewerModal {...props} />);
    rerender(<DocumentViewerModal {...props} pageIndex={2} onClose={() => {}} />);
    expect(apiClient.get).toHaveBeenCalledTimes(1);
  });

  it('ignores cancellation errors (no error UI, no console.error)', async () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { rerender } = render(<DocumentViewerModal {...props} />);
    rerender(<DocumentViewerModal {...props} isOpen={false} />);
    await flush();
    expect(errSpy).not.toHaveBeenCalled();
    // AbortError thrown by a non-aborted signal path is also ignored
    rerender(<DocumentViewerModal {...props} />);
    act(() => pending[1].reject(Object.assign(new Error('x'), { name: 'AbortError' })));
    await flush();
    expect(errSpy).not.toHaveBeenCalled();
    expect(screen.queryByText('טעינת המסמך נכשלה')).toBeNull();
  });

  it('outdated response does not overwrite current state or create a URL', async () => {
    const { rerender } = render(<DocumentViewerModal {...props} />);
    rerender(<DocumentViewerModal {...props} documentId="d2" />);
    // stale response for d1 arrives late
    await act(async () => { pending[0].resolve(ok('image/png')); });
    expect(createSpy).not.toHaveBeenCalled();
    expect(screen.queryByRole('img')).toBeNull();
    await act(async () => { pending[1].resolve(ok('image/png')); });
    expect(createSpy).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('img').getAttribute('src')).toBe('blob:mock-1');
  });

  it('revokes the created URL on unmount, document change and close; not while in use', async () => {
    const { rerender, unmount } = render(<DocumentViewerModal {...props} />);
    await act(async () => { pending[0].resolve(ok('image/png')); });
    expect(revokeSpy).not.toHaveBeenCalled();

    rerender(<DocumentViewerModal {...props} documentId="d2" />);
    expect(revokeSpy).toHaveBeenCalledTimes(1);
    expect(revokeSpy).toHaveBeenLastCalledWith('blob:mock-1');

    await act(async () => { pending[1].resolve(ok('image/png')); });
    expect(revokeSpy).toHaveBeenCalledTimes(1); // blob:mock-2 still in use

    rerender(<DocumentViewerModal {...props} documentId="d2" isOpen={false} />);
    expect(revokeSpy).toHaveBeenCalledTimes(2);
    expect(revokeSpy).toHaveBeenLastCalledWith('blob:mock-2');

    rerender(<DocumentViewerModal {...props} documentId="d2" />);
    await act(async () => { pending[2].resolve(ok('image/png')); });
    unmount();
    expect(revokeSpy).toHaveBeenCalledTimes(3);
    expect(revokeSpy).toHaveBeenLastCalledWith('blob:mock-3');
  });

  it('shows the Hebrew network error for a genuine network failure', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    render(<DocumentViewerModal {...props} />);
    await act(async () => { pending[0].reject({ code: 'ERR_NETWORK', message: 'Network Error' }); });
    expect(screen.getByText(NETWORK_MSG)).toBeTruthy();
    expect(screen.getByText('טעינת המסמך נכשלה')).toBeTruthy();
  });

  it('keeps the 404 and generic HTTP error messages', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const { unmount } = render(<DocumentViewerModal {...props} />);
    await act(async () => { pending[0].reject({ response: { status: 404 }, message: 'm' }); });
    expect(screen.getByText('המסמך לא נמצא.')).toBeTruthy();
    unmount();
    render(<DocumentViewerModal {...props} />);
    await act(async () => { pending[1].reject({ response: { status: 500 }, message: 'm' }); });
    expect(screen.getByText('לא ניתן היה לטעון את המסמך. נסו שוב מאוחר יותר.')).toBeTruthy();
  });

  it('StrictMode mount/cleanup/mount: first request aborted, one URL, revoked once', async () => {
    const { unmount } = render(
      <React.StrictMode>
        <DocumentViewerModal {...props} />
      </React.StrictMode>
    );
    expect(pending).toHaveLength(2);
    expect(pending[0].signal.aborted).toBe(true);
    expect(pending[1].signal.aborted).toBe(false);
    await act(async () => { pending[0].resolve(ok('image/png')); pending[1].resolve(ok('image/png')); });
    expect(createSpy).toHaveBeenCalledTimes(1);
    expect(revokeSpy).not.toHaveBeenCalled();
    unmount();
    expect(revokeSpy).toHaveBeenCalledTimes(1);
    expect(revokeSpy).toHaveBeenCalledWith('blob:mock-1');
  });
});

describe('DocumentViewerModal existing behavior', () => {
  it('renders a PDF iframe with the page fragment', async () => {
    const { container } = render(<DocumentViewerModal {...props} pageIndex={2} />);
    await act(async () => { pending[0].resolve(ok('application/pdf')); });
    const frame = container.querySelector('iframe');
    expect(frame?.getAttribute('src')).toBe('blob:mock-1#page=3');
  });

  it('renders an image for image content', async () => {
    render(<DocumentViewerModal {...props} />);
    await act(async () => { pending[0].resolve(ok('image/jpeg')); });
    expect(screen.getByRole('img')).toBeTruthy();
  });

  it('close button calls onClose', () => {
    const onClose = vi.fn();
    render(<DocumentViewerModal {...props} onClose={onClose} />);
    act(() => screen.getByLabelText('סגירה').click());
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
