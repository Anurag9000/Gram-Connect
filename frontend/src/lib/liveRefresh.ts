const REFRESH_KEY = 'gram_connect_live_refresh';
const REFRESH_EVENT = 'gram-connect:live-refresh';

export function signalLiveRefresh(): void {
  const token = String(Date.now());
  try {
    localStorage.setItem(REFRESH_KEY, token);
  } catch {
    // Ignore storage failures in private/incognito contexts.
  }
  window.dispatchEvent(new Event(REFRESH_EVENT));
}

export function subscribeLiveRefresh(callback: () => void): () => void {
  const handleStorage = (event: StorageEvent) => {
    if (event.key === REFRESH_KEY) {
      callback();
    }
  };

  const handleCustomEvent = () => {
    callback();
  };

  window.addEventListener('storage', handleStorage);
  window.addEventListener(REFRESH_EVENT, handleCustomEvent);

  return () => {
    window.removeEventListener('storage', handleStorage);
    window.removeEventListener(REFRESH_EVENT, handleCustomEvent);
  };
}
