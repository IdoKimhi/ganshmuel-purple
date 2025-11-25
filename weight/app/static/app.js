//const API_BASE = 'http://localhost:8086';
const API_BASE='http://15.206.113.164:8086';
// ========================================
// TOAST NOTIFICATION SYSTEM
// ========================================
function showToast(title, message, type = 'success') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icon = type === 'success' ? '✓' : type === 'error' ? '✗' : '⚠';

    toast.innerHTML = `
        <div class="toast-icon">${icon}</div>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-message">${message}</div>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// ========================================
// LOADING OVERLAY
// ========================================
function showLoading() {
    document.getElementById('loadingOverlay').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
}

// ========================================
// STATISTICS DASHBOARD
// ========================================
async function updateStatistics() {
    // Transactions
    try {
        const response = await fetch(`${API_BASE}/weight`);
        if (response.ok) {
            const data = await response.json();
            // Show total transactions count
            document.getElementById('statEntries').textContent = data.length || '0';
        }
    } catch (error) {
        document.getElementById('statEntries').textContent = '--';
    }

    // Unknown Containers
    try {
        const unknownResponse = await fetch(`${API_BASE}/unknown`);
        const containers = await unknownResponse.json();
        document.getElementById('statUnknown').textContent = containers.length;
        document.getElementById('statUnknown').style.color = containers.length > 0 ? 'var(--warning)' : 'var(--success)';
    } catch (error) {
        document.getElementById('statUnknown').textContent = '--';
    }
}

// ========================================
// FORM VALIDATION
// ========================================
function validateField(fieldId, errorId, validator) {
    const field = document.getElementById(fieldId);
    const error = document.getElementById(errorId);

    if (!validator(field.value)) {
        error.textContent = 'This field is required';
        field.style.borderColor = 'var(--error)';
        return false;
    } else {
        error.textContent = '';
        field.style.borderColor = '';
        return true;
    }
}

// ========================================
// FORM SUBMISSION
// ========================================
document.getElementById('weightForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    // Validate required fields
    const isDirectionValid = validateField('direction', 'directionError', val => val !== '');
    const isTruckValid = validateField('truck', 'truckError', val => val.trim() !== '');
    const isProduceValid = validateField('produce', 'produceError', val => val.trim() !== '');
    const isWeightValid = validateField('weight', 'weightError', val => val > 0);

    if (!isDirectionValid || !isTruckValid || !isProduceValid || !isWeightValid) {
        showToast('Validation Error', 'Please fill in all required fields', 'error');
        return;
    }

    const data = {
        direction: document.getElementById('direction').value,
        truck: document.getElementById('truck').value,
        containers: document.getElementById('containers').value,
        weight: parseInt(document.getElementById('weight').value),
        unit: document.getElementById('unit').value,
        produce: document.getElementById('produce').value,
        force: document.getElementById('force').checked
    };

    const submitBtn = e.target.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    showLoading();

    try {
        const response = await fetch(`${API_BASE}/weight`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (response.ok) {
            showToast('Success!', 'Weight entry submitted successfully', 'success');
            document.getElementById('weightForm').reset();
            updateStatistics(); // Refresh stats after new entry
        } else {
            showToast('Error', result.error || 'Unknown error occurred', 'error');
        }
    } catch (error) {
        showToast('Network Error', error.message, 'error');
    } finally {
        submitBtn.disabled = false;
        hideLoading();
    }
});

// ========================================
// UNKNOWN CONTAINERS CHECK
// ========================================
async function getUnknownContainers() {
    try {
        const response = await fetch(`${API_BASE}/unknown`);
        const containers = await response.json();

        const div = document.getElementById('unknownContainers');
        if (containers.length === 0) {
            div.innerHTML = '<p class="message success">✓ All containers are registered</p>';
        } else {
            div.innerHTML = `<p class="message warning">⚠ Unregistered containers detected: <strong>${containers.join(', ')}</strong></p>`;
        }

        setTimeout(() => div.innerHTML = '', 10000);
        updateStatistics(); // Refresh stats after check
    } catch (error) {
        const div = document.getElementById('unknownContainers');
        div.innerHTML = '<p class="message error">✗ Unable to validate containers</p>';
        setTimeout(() => div.innerHTML = '', 5000);
    }
}

// ========================================
// SYSTEM HEALTH CHECK
// ========================================
async function checkSystemStatus() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        const div = document.getElementById('systemStatus');

        if (response.ok) {
            div.innerHTML = '<p class="message success">✓ System operational - Database connected</p>';
        } else {
            div.innerHTML = '<p class="message error">✗ System health check failed</p>';
        }

        setTimeout(() => div.innerHTML = '', 5000);
    } catch (error) {
        const div = document.getElementById('systemStatus');
        div.innerHTML = '<p class="message error">✗ System unavailable</p>';
        setTimeout(() => div.innerHTML = '', 5000);
    }
}

// ========================================
// INITIALIZATION
// ========================================
window.addEventListener('load', () => {
    updateStatistics();
});

// Real-time validation on blur
['direction', 'truck', 'produce', 'weight'].forEach(fieldId => {
    const field = document.getElementById(fieldId);
    const errorId = fieldId + 'Error';

    field.addEventListener('blur', () => {
        if (field.value) {
            validateField(fieldId, errorId, val => val.trim() !== '' && (fieldId !== 'weight' || val > 0));
        }
    });

    field.addEventListener('input', () => {
        const error = document.getElementById(errorId);
        if (error.textContent) {
            error.textContent = '';
            field.style.borderColor = '';
        }
    });
});
