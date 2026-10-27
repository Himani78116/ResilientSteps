let dashboardMap = null;
let markerLayerGroup = null;

// Report fields are user-submitted, so escape them before they reach any HTML
// sink. dashboard.js (loaded after this file) reuses this single definition.
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[ch]));
}

function initDashboardMap(containerId) {
  if (dashboardMap) return dashboardMap;

  // Center on Pune
  dashboardMap = L.map(containerId).setView([18.5204, 73.8567], 12);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap contributors'
  }).addTo(dashboardMap);

  markerLayerGroup = L.layerGroup().addTo(dashboardMap);
  return dashboardMap;
}

function clearMapMarkers() {
  if (markerLayerGroup) {
    markerLayerGroup.clearLayers();
  }
}

function getMarkerColor(reportType) {
  switch ((reportType || '').toLowerCase()) {
    case 'infrastructure': return '#f59e0b';
    case 'waste': return '#10b981';
    case 'safety': default: return '#0284c7';
  }
}

function renderMarkersOnMap(reports) {
  clearMapMarkers();
  if (!reports || !reports.length) return;

  const bounds = L.latLngBounds();

  reports.forEach(r => {
    const lat = parseFloat(r.latitude || r.lat);
    const lon = parseFloat(r.longitude || r.lon);
    if (!isNaN(lat) && !isNaN(lon)) {
      const color = getMarkerColor(r.report_type);
      const marker = L.circleMarker([lat, lon], {
        radius: 7,
        fillColor: color,
        color: '#ffffff',
        weight: 1.5,
        opacity: 1,
        fillOpacity: 0.8
      });

      marker.bindPopup(`
        <strong>${escapeHtml(r.category || 'Incident')}</strong><br/>
        Type: ${escapeHtml(r.report_type || 'safety')}<br/>
        Severity: ${escapeHtml(r.severity || 3)}<br/>
        Status: ${escapeHtml(r.status || 'pending')}<br/>
        <small>${escapeHtml(r.description || '')}</small>
      `);

      markerLayerGroup.addLayer(marker);
      bounds.extend([lat, lon]);
    }
  });

  if (bounds.isValid()) {
    dashboardMap.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
  }
}
