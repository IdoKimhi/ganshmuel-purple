const API_BASE = 'http://localhost:8086';

// Form submission
document.getElementById('weightForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const data = {
        direction: document.getElementById('direction').value,
        truck: document.getElementById('truck').value,
        containers: document.getElementById('containers').value,
        weight: parseInt(document.getElementById('weight').value),
        unit: document.getElementById('unit').value,
        produce: document.getElementById('produce').value,
        force: document.getElementById('force').checked
    };

    try {
        const response = await fetch(`${API_BASE}/weight`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();
        const messageDiv = document.getElementById('formMessage');

        if (response.ok) {
            messageDiv.className = 'message success';
            messageDiv.textContent = `✓ Success! ID: ${result.id}`;
            document.getElementById('weightForm').reset();
            refreshTransactions();
        } else {
            messageDiv.className = 'message error';
            messageDiv.textContent = `✗ Error: ${result.error || 'Unknown error'}`;
        }

        setTimeout(() => messageDiv.textContent = '', 5000);
    } catch (error) {
        document.getElementById('formMessage').className = 'message error';
        document.getElementById('formMessage').textContent = `✗ Network error: ${error.message}`;
    }
});

// Get unknown containers
async function getUnknownContainers() {
    try {
        const response = await fetch(`${API_BASE}/unknown`);
        const containers = await response.json();

        const div = document.getElementById('unknownContainers');
        if (containers.length === 0) {
            div.innerHTML = '<p class="message success">✓ All containers are registered!</p>';
        } else {
            div.innerHTML = `<p class="message warning">⚠ Unknown containers: <strong>${containers.join(', ')}</strong></p>`;
        }

        setTimeout(() => div.innerHTML = '', 10000);
    } catch (error) {
        console.error('Error fetching unknown containers:', error);
    }
}

// Refresh transactions
async function refreshTransactions() {
    const filters = [];
    if (document.getElementById('filterIn').checked) filters.push('in');
    if (document.getElementById('filterOut').checked) filters.push('out');
    if (document.getElementById('filterNone').checked) filters.push('none');

    try {
        const response = await fetch(`${API_BASE}/weight?filter=${filters.join(',')}`);
        const transactions = await response.json();

        const tbody = document.getElementById('transactionsBody');

        if (transactions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty">No transactions found</td></tr>';
            return;
        }

        tbody.innerHTML = transactions.map(t => `
            <tr>
                <td>${t.id}</td>
                <td><span class="badge badge-${t.direction}">${t.direction.toUpperCase()}</span></td>
                <td>${t.truck || 'N/A'}</td>
                <td>${t.bruto}</td>
                <td>${t.neto === 'na' ? '<span class="na">N/A</span>' : t.neto}</td>
                <td>${t.produce}</td>
                <td>${t.containers.length > 0 ? t.containers.join(', ') : '-'}</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error fetching transactions:', error);
        document.getElementById('transactionsBody').innerHTML =
            '<tr><td colspan="7" class="error">Error loading transactions</td></tr>';
    }
}


// Load transactions on page load
window.addEventListener('load', refreshTransactions);
