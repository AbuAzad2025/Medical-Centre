/* Dashboard live updates - TypeScript */
interface DashboardStats {
  patients: number;
  appointments: number;
  revenue: number;
  pending: number;
}

function updateDashboard(stats: DashboardStats): void {
  const patientsEl = document.getElementById('stat-patients');
  const appointmentsEl = document.getElementById('stat-appointments');
  const revenueEl = document.getElementById('stat-revenue');
  const pendingEl = document.getElementById('stat-pending');

  if (patientsEl) patientsEl.textContent = String(stats.patients);
  if (appointmentsEl) appointmentsEl.textContent = String(stats.appointments);
  if (revenueEl) revenueEl.textContent = String(stats.revenue);
  if (pendingEl) pendingEl.textContent = String(stats.pending);
}

// Poll for updates every 30 seconds
setInterval(async () => {
  try {
    const response = await fetch('/api/dashboard/stats');
    if (response.ok) {
      const stats = await response.json();
      updateDashboard(stats);
    }
  } catch {
    // Silently fail
  }
}, 30000);

(window as any).updateDashboard = updateDashboard;