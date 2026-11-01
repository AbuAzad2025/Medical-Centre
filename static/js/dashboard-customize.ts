/* Dashboard customize - TypeScript */
interface WidgetConfig {
  id: string;
  visible: boolean;
  order: number;
}

function loadWidgetConfig(): WidgetConfig[] {
  try {
    const stored = localStorage.getItem('dashboard-widgets');
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function saveWidgetConfig(config: WidgetConfig[]): void {
  localStorage.setItem('dashboard-widgets', JSON.stringify(config));
}

function toggleWidget(id: string): void {
  const config = loadWidgetConfig();
  const widget = config.find((w) => w.id === id);
  if (widget) {
    widget.visible = !widget.visible;
    saveWidgetConfig(config);
    const el = document.getElementById(id);
    if (el) el.style.display = widget.visible ? 'block' : 'none';
  }
}

(window as any).loadWidgetConfig = loadWidgetConfig;
(window as any).saveWidgetConfig = saveWidgetConfig;
(window as any).toggleWidget = toggleWidget;