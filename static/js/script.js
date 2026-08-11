let chartInstance = null;

document.getElementById('cdr-form').addEventListener('submit', async function(e) {
    e.preventDefault();

    const btnSubmit = document.getElementById('btn-submit');
    btnSubmit.innerText = "PROCESSING CDR DATA...";
    btnSubmit.disabled = true;

    const formData = new FormData(this);

    try {
        const response = await fetch('/process', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            renderDashboard(data);
        } else {
            alert("Error processing CDR: " + (data.error || "Unknown error"));
        }
    } catch (err) {
        alert("Failed to connect to server. Ensure Flask app is running.");
        console.error(err);
    } finally {
        btnSubmit.innerText = "RUN FORENSIC ANALYSIS";
        btnSubmit.disabled = false;
    }
});

function renderDashboard(data) {
    document.getElementById('results-section').style.display = 'block';
    document.getElementById('total-count-badge').innerText = `${data.total_records} Records Processed`;

    // 1. Render IMEIs
    const imeiListElem = document.getElementById('imei-list');
    imeiListElem.innerHTML = '';
    if (data.imei_list && data.imei_list.length > 0) {
        data.imei_list.forEach(imei => {
            const li = document.createElement('li');
            li.innerHTML = `<strong>${imei}</strong> (Verify on imei.info)`;
            imeiListElem.appendChild(li);
        });
    } else {
        imeiListElem.innerHTML = '<li>No Outgoing IMEI Captured</li>';
    }

    // 2. Render Top 10 Table
    const topTableBody = document.querySelector('#top-calls-table tbody');
    topTableBody.innerHTML = '';
    const labels = [];
    const counts = [];

    data.top_contacts.forEach(item => {
        labels.push(item['Opposite Number']);
        counts.push(item['Call Count']);

        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${item['Opposite Number']}</td><td><strong>${item['Call Count']}</strong></td>`;
        topTableBody.appendChild(tr);
    });

    // 3. Render Chart.js Chart
    renderChart(labels, counts);

    // 4. Render Preview Sheet Table
    renderPreviewTable(data.sample_records);
}

function renderChart(labels, counts) {
    const ctx = document.getElementById('freqChart').getContext('2d');

    if (chartInstance) {
        chartInstance.destroy();
    }

    chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Call / Interaction Frequency',
                data: counts,
                backgroundColor: '#0056b3',
                borderColor: '#112233',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
}

function renderPreviewTable(records) {
    if (!records || records.length === 0) return;

    const thead = document.querySelector('#preview-table thead');
    const tbody = document.querySelector('#preview-table tbody');
    thead.innerHTML = '';
    tbody.innerHTML = '';

    // Headers
    const headers = Object.keys(records[0]);
    const headerTr = document.createElement('tr');
    headers.forEach(h => {
        const th = document.createElement('th');
        th.innerText = h;
        headerTr.appendChild(th);
    });
    thead.appendChild(headerTr);

    // Rows
    records.forEach(row => {
        const tr = document.createElement('tr');
        headers.forEach(h => {
            const td = document.createElement('td');
            td.innerText = row[h] !== null ? row[h] : '';
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
}
