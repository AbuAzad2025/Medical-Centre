/* UI Preferences - TypeScript */
interface UIPreferences {
  theme: 'light' | 'dark';
  language: 'ar' | 'en';
  sidebarCollapsed: boolean;
  fontSize: 'sm' | 'md' | 'lg';
}

const DEFAULT_PREFS: UIPreferences = {
  theme: 'light',
  language: 'ar',
  sidebarCollapsed: false,
  fontSize: 'md',
};

function getPrefs(): UIPreferences {
  try {
    const stored = localStorage.getItem('azad-ui-prefs');
    return stored ? {...DEFAULT_PREFS, ...JSON.parse(stored)} : DEFAULT_PREFS;
  } catch {
    return DEFAULT_PREFS;
  }
}

function setPrefs(prefs: Partial<UIPreferences>): void {
  const current = getPrefs();
  const updated = {...current, ...prefs};
  localStorage.setItem('azad-ui-prefs', JSON.stringify(updated));
}

(window as any).getPrefs = getPrefs;
(window as any).setPrefs = setPrefs;