// VacationManager Web Portal JavaScript

// API base URL
const API_BASE = '/api';

// Current selected document
let currentDocument = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadPendingDocuments();

    // File input change handler
    const fileInput = document.getElementById('file-input');
    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelect);
    }
});

/**
 * Load pending documents from API
 */
async function loadPendingDocuments() {
    const listContainer = document.getElementById('pending-list');

    try {
        const response = await fetch(`${API_BASE}/documents/pending`);
        if (!response.ok) {
            throw new Error('Помилка завантаження документів');
        }

        const data = await response.json();

        if (data.items && data.items.length > 0) {
            listContainer.innerHTML = data.items.map(doc => `
                <div class="document-item">
                    <div class="document-info">
                        <div class="document-title">${doc.staff_name || 'Співробітник'}</div>
                        <div class="document-meta">
                            <span>${doc.doc_type === 'vacation_paid' ? 'Відпустка оплачувана' :
                                  doc.doc_type === 'vacation_unpaid' ? 'Відпустка без збереження' :
                                  'Продовження контракту'}</span>
                            <span>з ${formatDate(doc.date_start)} по ${formatDate(doc.date_end)}</span>
                            <span>${doc.days_count} днів</span>
                        </div>
                    </div>
                    <div class="document-actions">
                        <button class="btn btn-primary" onclick="openUpload(${doc.id})">
                            Завантажити скан
                        </button>
                    </div>
                </div>
            `).join('');
        } else {
            listContainer.innerHTML = `
                <div class="empty-state">
                    <p>Немає документів на підпис</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading documents:', error);
        listContainer.innerHTML = `
            <div class="empty-state">
                <p>Помилка завантаження документів</p>
            </div>
        `;
    }
}

/**
 * Open upload section for a document
 */
async function openUpload(documentId) {
    try {
        const response = await fetch(`${API_BASE}/documents/${documentId}`);
        if (!response.ok) {
            throw new Error('Помилка отримання документа');
        }

        const doc = await response.json();
        currentDocument = doc;

        // Show document info
        const infoDiv = document.getElementById('selected-doc-info');
        infoDiv.innerHTML = `
            <strong>${doc.staff_name}</strong><br>
            ${doc.doc_type === 'vacation_paid' ? 'Відпустка оплачувана' :
              doc.doc_type === 'vacation_unpaid' ? 'Відпустка без збереження' :
              'Продовження контракту'}<br>
            з ${formatDate(doc.date_start)} по ${formatDate(doc.date_end)} (${doc.days_count} днів)
        `;

        // Set document ID
        document.getElementById('document-id').value = documentId;

        // Show upload section
        document.getElementById('upload-section').style.display = 'block';

        // Scroll to upload section
        document.getElementById('upload-section').scrollIntoView({ behavior: 'smooth' });

    } catch (error) {
        console.error('Error loading document:', error);
        showError('Помилка отримання документа');
    }
}

/**
 * Close upload section
 */
function closeUploadSection() {
    document.getElementById('upload-section').style.display = 'none';
    document.getElementById('upload-form').reset();
    document.getElementById('preview-container').innerHTML = '<p class="preview-placeholder">Файл не обрано</p>';
    currentDocument = null;
}

/**
 * Handle file selection
 */
function handleFileSelect(event) {
    const file = event.target.files[0];
    const previewContainer = document.getElementById('preview-container');

    if (!file) {
        previewContainer.innerHTML = '<p class="preview-placeholder">Файл не обрано</p>';
        return;
    }

    // Check file size (10MB)
    if (file.size > 10 * 1024 * 1024) {
        showError('Файл завеликий. Максимальний розмір: 10 MB');
        event.target.value = '';
        return;
    }

    // Check file type
    const allowedTypes = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png'];
    if (!allowedTypes.includes(file.type)) {
        showError('Недопустимий формат файлу. Дозволені: PDF, JPG, PNG');
        event.target.value = '';
        return;
    }

    // Show preview
    if (file.type === 'application/pdf') {
        previewContainer.innerHTML = `
            <div style="text-align: center;">
                <p>📄 ${file.name}</p>
                <small>${(file.size / 1024).toFixed(1)} KB</small>
            </div>
        `;
    } else {
        const reader = new FileReader();
        reader.onload = (e) => {
            previewContainer.innerHTML = `<img src="${e.target.result}" alt="Preview">`;
        };
        reader.readAsDataURL(file);
    }
}

/**
 * Handle file upload
 */
async function handleUpload(event) {
    event.preventDefault();

    const fileInput = document.getElementById('file-input');
    const file = fileInput.files[0];
    const documentId = document.getElementById('document-id').value;

    if (!file) {
        showError('Оберіть файл для завантаження');
        return;
    }

    const uploadBtn = document.getElementById('upload-btn');
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Завантаження...';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE}/upload/${documentId}`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Помилка завантаження');
        }

        // Show success modal
        showSuccessModal();

    } catch (error) {
        console.error('Upload error:', error);
        showError(error.message || 'Помилка завантаження файлу');
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Завантажити';
    }
}

/**
 * Show success modal
 */
function showSuccessModal() {
    document.getElementById('success-modal').style.display = 'flex';
}

/**
 * Show error modal
 */
function showError(message) {
    document.getElementById('error-message').textContent = message;
    document.getElementById('error-modal').style.display = 'flex';
}

/**
 * Close success modal
 */
function closeModal() {
    document.getElementById('success-modal').style.display = 'none';
}

/**
 * Close error modal
 */
function closeErrorModal() {
    document.getElementById('error-modal').style.display = 'none';
}

/**
 * Format date for display
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('uk-UA', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    });
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
