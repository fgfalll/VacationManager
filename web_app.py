from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
import uuid

from app.models import Staff, VacationRequest, LeaveReason, get_db
from app.database import init_db
from config import SCANS_DIRECTORY, DATABASE_URL

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = SCANS_DIRECTORY

# Ensure directories exist
os.makedirs(SCANS_DIRECTORY, exist_ok=True)
os.makedirs(os.path.join(app.static_folder, 'css'), exist_ok=True)
os.makedirs(os.path.join(app.static_folder, 'js'), exist_ok=True)

# Initialize database
init_db()

# HTML template for mobile view
MOBILE_TEMPLATE = """
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VacationManager - Мобільний додаток</title>
    <link rel="stylesheet" href="/static/css/mobile.css">
</head>
<body>
    <div class="container">
        <h1>Заявки на підпис</h1>
        <div id="requests-list" class="requests-list">
            <!-- Requests will be loaded here -->
        </div>
    </div>

    <div id="upload-modal" class="modal">
        <div class="modal-content">
            <span class="close">&times;</span>
            <h2>Завантажити скан підпису</h2>
            <p id="request-info"></p>
            <input type="file" id="scan-input" accept="image/*,.pdf" capture="environment">
            <button id="upload-btn">Завантажити</button>
        </div>
    </div>

    <script src="/static/js/mobile.js"></script>
</body>
</html>
"""

# CSS for mobile view
MOBILE_CSS = """
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    background-color: #f5f5f5;
    color: #333;
}

.container {
    max-width: 600px;
    margin: 0 auto;
    padding: 20px;
}

h1 {
    color: #2c3e50;
    margin-bottom: 20px;
    text-align: center;
}

.requests-list {
    display: flex;
    flex-direction: column;
    gap: 15px;
}

.request-card {
    background: white;
    border-radius: 10px;
    padding: 15px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    cursor: pointer;
    transition: transform 0.2s;
}

.request-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.15);
}

.request-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 10px;
}

.staff-name {
    font-weight: bold;
    font-size: 18px;
}

.request-dates {
    color: #666;
    font-size: 14px;
}

.upload-btn {
    background: #3498db;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 5px;
    cursor: pointer;
    margin-top: 10px;
}

.upload-btn:hover {
    background: #2980b9;
}

.modal {
    display: none;
    position: fixed;
    z-index: 1000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0,0,0,0.4);
}

.modal-content {
    background-color: white;
    margin: 20% auto;
    padding: 20px;
    border-radius: 10px;
    width: 90%;
    max-width: 500px;
}

.close {
    color: #aaa;
    float: right;
    font-size: 28px;
    font-weight: bold;
    cursor: pointer;
}

.close:hover {
    color: black;
}

#scan-input {
    width: 100%;
    margin: 15px 0;
    padding: 10px;
    border: 2px dashed #ccc;
    border-radius: 5px;
}

#upload-btn {
    background: #27ae60;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 5px;
    cursor: pointer;
    width: 100%;
    font-size: 16px;
}

#upload-btn:hover {
    background: #229954;
}
"""

# JavaScript for mobile view
MOBILE_JS = """
let currentRequestId = null;

document.addEventListener('DOMContentLoaded', function() {
    loadRequests();

    // Modal close button
    const closeBtn = document.querySelector('.close');
    closeBtn.onclick = function() {
        document.getElementById('upload-modal').style.display = 'none';
    }

    // Upload button
    document.getElementById('upload-btn').addEventListener('click', uploadScan);
});

function loadRequests() {
    fetch('/api/requests/pending')
        .then(response => response.json())
        .then(requests => {
            const list = document.getElementById('requests-list');
            list.innerHTML = '';

            requests.forEach(req => {
                const card = document.createElement('div');
                card.className = 'request-card';
                card.onclick = () => showUploadModal(req);

                card.innerHTML = `
                    <div class="request-header">
                        <span class="staff-name">${req.staff_name}</span>
                        <span class="request-dates">${req.start_date} - ${req.end_date}</span>
                    </div>
                    <div>Кількість днів: ${req.total_days}</div>
                    <div>Тип: ${req.leave_type}</div>
                    <button class="upload-btn">Завантажити скан підпису</button>
                `;

                list.appendChild(card);
            });
        });
}

function showUploadModal(request) {
    currentRequestId = request.id;
    const modal = document.getElementById('upload-modal');
    const info = document.getElementById('request-info');

    info.innerHTML = `
        <strong>Співробітник:</strong> ${request.staff_name}<br>
        <strong>Період:</strong> ${request.start_date} - ${request.end_date}<br>
        <strong>Тип відпустки:</strong> ${request.leave_type}
    `;

    modal.style.display = 'block';
}

function uploadScan() {
    const fileInput = document.getElementById('scan-input');
    const file = fileInput.files[0];

    if (!file) {
        alert('Оберіть файл для завантаження');
        return;
    }

    const formData = new FormData();
    formData.append('scan', file);

    fetch(`/api/requests/${currentRequestId}/upload-scan`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Скан успішно завантажено!');
            document.getElementById('upload-modal').style.display = 'none';
            loadRequests(); // Refresh list
        } else {
            alert('Помилка: ' + data.message);
        }
    })
    .catch(error => {
        alert('Помилка завантаження: ' + error);
    });
}
"""

@app.route('/')
def index():
    """Mobile app main page"""
    return MOBILE_TEMPLATE

@app.route('/static/css/mobile.css')
def mobile_css():
    """Serve mobile CSS"""
    return MOBILE_CSS, 200, {'Content-Type': 'text/css'}

@app.route('/static/js/mobile.js')
def mobile_js():
    """Serve mobile JavaScript"""
    return MOBILE_JS, 200, {'Content-Type': 'application/javascript'}

@app.route('/api/requests/pending')
def get_pending_requests():
    """Get all requests with status 'На підписі'"""
    db = next(get_db())
    try:
        requests = db.query(VacationRequest).filter_by(status='На підписі').all()

        result = []
        for req in requests:
            result.append({
                'id': req.id,
                'staff_name': req.staff.full_name,
                'start_date': req.start_date.strftime('%d.%m.%Y'),
                'end_date': req.end_date.strftime('%d.%m.%Y'),
                'total_days': req.total_days,
                'leave_type': req.leave_type
            })

        return jsonify(result)
    finally:
        db.close()

@app.route('/api/requests/<int:request_id>/upload-scan', methods=['POST'])
def upload_scan(request_id):
    """Upload scan for a vacation request"""
    db = next(get_db())
    try:
        request = db.query(VacationRequest).filter_by(id=request_id).first()
        if not request:
            return jsonify({'success': False, 'message': 'Заявку не знайдено'})

        # Check if file was uploaded
        if 'scan' not in request.files:
            return jsonify({'success': False, 'message': 'Файл не завантажено'})

        file = request.files['scan']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Файл не обрано'})

        # Secure filename and save
        filename = secure_filename(file.filename)
        unique_filename = f"scan_{request_id}_{uuid.uuid4().hex[:8]}_{filename}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        file.save(save_path)

        # Update request
        request.scan_path = save_path
        request.status = 'Підписано'
        request.updated_at = datetime.utcnow()

        db.commit()

        return jsonify({'success': True, 'message': 'Скан успішно завантажено'})

    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        db.close()

@app.route('/api/requests/<int:request_id>')
def get_request(request_id):
    """Get details of a specific request"""
    db = next(get_db())
    try:
        request = db.query(VacationRequest).filter_by(id=request_id).first()
        if not request:
            return jsonify({'error': 'Заявку не знайдено'}), 404

        return jsonify({
            'id': request.id,
            'staff_name': request.staff.full_name,
            'staff_position': request.staff.position,
            'start_date': request.start_date.strftime('%d.%m.%Y'),
            'end_date': request.end_date.strftime('%d.%m.%Y'),
            'total_days': request.total_days,
            'leave_type': request.leave_type,
            'reason_text': request.reason_text,
            'status': request.status,
            'has_scan': bool(request.scan_path),
            'timesheet_processed': request.timesheet_processed,
            'created_at': request.created_at.isoformat(),
            'updated_at': request.updated_at.isoformat()
        })
    finally:
        db.close()

@app.route('/api/requests/<int:request_id>/scan')
def get_scan(request_id):
    """Serve scan file if exists"""
    db = next(get_db())
    try:
        request = db.query(VacationRequest).filter_by(id=request_id).first()
        if not request or not request.scan_path:
            return jsonify({'error': 'Скан не знайдено'}), 404

        if os.path.exists(request.scan_path):
            return send_from_directory(
                os.path.dirname(request.scan_path),
                os.path.basename(request.scan_path)
            )
        else:
            return jsonify({'error': 'Файл не знайдено'}), 404

    finally:
        db.close()

@app.route('/api/requests/<int:request_id>/status', methods=['PUT'])
def update_status(request_id):
    """Update request status (for desktop app)"""
    db = next(get_db())
    try:
        request = db.query(VacationRequest).filter_by(id=request_id).first()
        if not request:
            return jsonify({'error': 'Заявку не знайдено'}), 404

        data = request.get_json()
        new_status = data.get('status')

        if new_status in ['Створено', 'На підписі', 'Підписано', 'Додано до табелю']:
            request.status = new_status
            request.updated_at = datetime.utcnow()

            if new_status == 'Додано до табелю':
                request.timesheet_processed = True

            db.commit()
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Невірний статус'}), 400

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@app.route('/api/staff')
def get_staff():
    """Get all staff (for desktop app)"""
    db = next(get_db())
    try:
        staff = db.query(Staff).all()
        result = []
        for s in staff:
            result.append({
                'id': s.id,
                'full_name': s.full_name,
                'position': s.position,
                'rate': s.rate,
                'employment_type': s.employment_type,
                'academic_degree': s.academic_degree
            })
        return jsonify(result)
    finally:
        db.close()

@app.route('/api/leave-reasons', methods=['GET', 'POST'])
def leave_reasons():
    """Get or create leave reasons"""
    db = next(get_db())
    try:
        if request.method == 'GET':
            reasons = db.query(LeaveReason).all()
            return jsonify([{'id': r.id, 'text': r.reason_text} for r in reasons])

        elif request.method == 'POST':
            data = request.get_json()
            reason_text = data.get('text', '').strip()

            if not reason_text:
                return jsonify({'error': 'Текст причини не може бути порожнім'}), 400

            # Check if reason already exists
            existing = db.query(LeaveReason).filter_by(reason_text=reason_text).first()
            if existing:
                return jsonify({'id': existing.id, 'text': existing.reason_text})

            # Create new reason
            new_reason = LeaveReason(reason_text=reason_text)
            db.add(new_reason)
            db.commit()

            return jsonify({'id': new_reason.id, 'text': new_reason.reason_text})

    finally:
        db.close()

if __name__ == '__main__':
    # Create static directory if it doesn't exist
    os.makedirs('static', exist_ok=True)

    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)