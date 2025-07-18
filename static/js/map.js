// Initialize the map
var map = L.map('mapid').setView([14.5995, 120.9842], 12); // Manila coordinates

// Add OpenStreetMap tile layer
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

// Helper to get marker color by status
function getMarkerColor(status) {
    switch (status) {
        case 'Safe': return 'green';
        case 'Alert': return 'orange';
        case 'Flooded': return 'red';
        default: return 'blue';
    }
}

// Fetch reports and add markers
fetch('/api/reports')
    .then(res => res.json())
    .then(reports => {
        const tableBody = document.querySelector('#status-table tbody');
        tableBody.innerHTML = '';
        reports.forEach(report => {
            // Marker
            const marker = L.circleMarker([report.lat, report.lng], {
                color: getMarkerColor(report.status),
                radius: 10,
                fillOpacity: 0.8
            }).addTo(map);
            marker.bindPopup(`
                <b>${report.area}</b><br>
                Status: <span style='color:${getMarkerColor(report.status)}'>${report.status}</span><br>
                Rainfall: ${report.rainfall !== null ? report.rainfall + ' mm' : 'N/A'}<br>
                Time: ${new Date(report.timestamp).toLocaleString()}<br>
                ${report.description ? '<hr>' + report.description : ''}
            `);
            // Table row
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${report.area}</td>
                <td style="color:${getMarkerColor(report.status)}">${report.status}</td>
                <td>Flood Report</td>
                <td>${report.rainfall !== null ? report.rainfall : 'N/A'}</td>
                <td>${new Date(report.timestamp).toLocaleString()}</td>
            `;
            tableBody.appendChild(row);
        });
    });

// Fetch cyclone impacts and add blue markers and to status table
fetch('/api/cyclone-impacts')
    .then(res => res.json())
    .then(impacts => {
        const tableBody = document.querySelector('#status-table tbody');
        impacts.forEach(impact => {
            const marker = L.circleMarker([impact.lat, impact.lng], {
                color: 'blue',
                radius: 10,
                fillOpacity: 0.7
            }).addTo(map);
            marker.bindPopup(`
                <b>${impact.area}</b><br>
                <span style='color:blue'>${impact.status}</span><br>
                ${impact.description}<br>
                Time: ${new Date(impact.timestamp).toLocaleString()}
            `);
            // Table row
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${impact.area}</td>
                <td style="color:blue">${impact.status}</td>
                <td>Cyclone Impact</td>
                <td>N/A</td>
                <td>${new Date(impact.timestamp).toLocaleString()}</td>
            `;
            tableBody.appendChild(row);
        });
    }); 