import type { Database } from './database.types';

export type ProfileRecord = Database['public']['Tables']['profiles']['Row'];

const STORAGE_KEY = 'gram-connect:villager-profile';

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

export function loadStoredProfile(): ProfileRecord | null {
  if (!canUseStorage()) {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    return JSON.parse(raw) as ProfileRecord;
  } catch {
    return null;
  }
}

export function saveStoredProfile(profile: ProfileRecord) {
  if (!canUseStorage()) {
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
}

export function clearStoredProfile() {
  if (!canUseStorage()) {
    return;
  }
  window.localStorage.removeItem(STORAGE_KEY);
}
