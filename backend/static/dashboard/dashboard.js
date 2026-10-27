document.addEventListener('DOMContentLoaded', () => {
  const adminKeyInput = document.getElementById('adminKey');
  const saveKeyBtn = document.getElementById('saveKeyBtn');
  const filterStatusSelect = document.getElementById('filterStatus');
  const filterReportTypeSelect = document.getElementById('filterReportType');
  const loadReportsBtn = document.getElementById('loadReportsBtn');
  const refreshViewBtn = document.getElementById('refreshViewBtn');

  // Restore saved key — never fall back to a default, the operator must paste one.
  adminKeyInput.value = localStorage.getItem('cityos_admin_key') || '';

  saveKeyBtn.addEventListener('click', () => {
    if (!adminKey()) {
      alert('Enter your admin key before saving.');
      return;
    }
    localStorage.setItem('cityos_admin_key', adminKey());
    alert('Admin key saved.');
    loadDashboardData();
  });

  function adminKey() {
    return adminKeyInput.value.trim();
  }

  // Report fields are user-submitted: escape them before injecting into HTML.
  // escapeHtml lives in map.js so the map popups and this table share one
  // implementation (map.js is loaded first by index.html).

  // Init map
  initDashboardMap('map');

  function getHeaders() {
    return {
      'X-Admin-Key': adminKey(),
      'Content-Type': 'application/json'
    };
  }

  async function loadDashboardSummary() {
    try {
      const res = await fetch('/dashboard/summary', { headers: getHeaders() });
      if (!res.ok) return;
      const data = await res.json();

      document.getElementById('statTotal').textContent = data.total_reports || 0;
      document.getElementById('statPending').textContent = data.pending_count || 0;
      document.getElementById('statVerified').textContent = data.verified_count || 0;
      document.getElementById('statRejected').textContent = data.rejected_count || 0;
      document.getElementById('statAvgHours').textContent = (data.average_verification_hours != null ? data.average_verification_hours + ' hrs' : 'N/A');

      const byType = data.by_type || {};
      document.getElementById('cntSafety').textContent = byType.safety || 0;
      document.getElementById('cntInfra').textContent = byType.infrastructure || 0;
      document.getElementById('cntWaste').textContent = byType.waste || 0;
    } catch (e) {
      console.warn('Failed to load city summary:', e);
    }
  }

  async function loadReportsTable() {
    const status = filterStatusSelect.value;
    const reportType = filterReportTypeSelect.value;
    const tbody = document.getElementById('reportsTableBody');

    let url = `/admin/reports?status=${encodeURIComponent(status)}`;
    if (reportType) {
      url += `&report_type=${encodeURIComponent(reportType)}`;
    }

    try {
      const res = await fetch(url, { headers: getHeaders() });
      if (!res.ok) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center text-danger">Error loading reports (${res.status})</td></tr>`;
        return;
      }
      const data = await res.json();
      const reports = data.reports || [];

      if (!reports.length) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center">No ${status} reports found.</td></tr>`;
        clearMapMarkers();
        return;
      }

      renderMarkersOnMap(reports);

      tbody.innerHTML = reports.map(r => `
        <tr>
          <td>${r.id}</td>
          <td><span class="badge badge-${escapeHtml(r.report_type || 'safety')}">${escapeHtml(r.report_type || 'safety')}</span></td>
          <td><strong>${escapeHtml(r.category || '')}</strong></td>
          <td>${escapeHtml(r.description || 'N/A')}</td>
          <td>${r.latitude ? r.latitude.toFixed(4) : ''}, ${r.longitude ? r.longitude.toFixed(4) : ''}</td>
          <td>${r.severity || 3}</td>
          <td>${r.submitted_at ? new Date(r.submitted_at).toLocaleString() : ''}</td>
          <td>${escapeHtml(r.status)}</td>
          <td>
            ${r.status === 'pending' ? `
              <button class="action-btn-sm btn-verify" onclick="moderateReport(${r.id}, 'verify')">Verify</button>
              <button class="action-btn-sm btn-reject" onclick="moderateReport(${r.id}, 'reject')">Reject</button>
            ` : '—'}
          </td>
        </tr>
      `).join('');

    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="9" class="text-center text-danger">Error fetching data</td></tr>`;
    }
  }

  window.moderateReport = async function(id, action) {
    if (!confirm(`Are you sure you want to ${action} report #${id}?`)) return;

    try {
      const res = await fetch(`/admin/reports/${id}/${action}`, {
        method: 'POST',
        headers: getHeaders()
      });
      if (res.ok) {
        loadDashboardData();
      } else {
        alert(`Action failed: ${res.statusText}`);
      }
    } catch (e) {
      alert(`Error performing action: ${e}`);
    }
  };

  async function refreshWardView() {
    try {
      const res = await fetch('/dashboard/refresh-summary', {
        method: 'POST',
        headers: getHeaders()
      });
      if (res.ok) {
        alert('Ward summary refreshed!');
        loadDashboardData();
      }
    } catch (e) {
      alert('Error refreshing view.');
    }
  }

  function loadDashboardData() {
    if (!adminKey()) {
      document.getElementById('reportsTableBody').innerHTML =
        '<tr><td colspan="9" class="text-center text-danger">Paste your admin key above to load reports.</td></tr>';
      return;
    }
    loadDashboardSummary();
    loadReportsTable();
  }

  loadReportsBtn.addEventListener('click', loadReportsTable);
  refreshViewBtn.addEventListener('click', refreshWardView);

  // Initial Load
  loadDashboardData();
});
