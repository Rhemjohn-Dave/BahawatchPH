from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from config import Config
from models import db, Report, CycloneImpact, User
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session
from functools import wraps
from flask_migrate import Migrate
import json

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

migrate = Migrate(app, db)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Helper to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.cli.command('init-db')
def init_db():
    '''Initialize the database.'''
    db.create_all()
    print('Database initialized.')

@app.cli.command('create-admin')
def create_admin():
    name = input('Admin name: ')
    email = input('Admin email: ')
    password = input('Admin password: ')
    from models import User, db
    if User.query.filter_by(email=email).first():
        print('User with this email already exists.')
        return
    user = User(name=name, email=email, role='admin')
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    print(f'Admin user {email} created.')

@app.route('/')
def index():
    # Try to load latest cyclone bulletin info from JSON file
    bulletin_path = os.path.join('utils', 'cyclone_bulletin.json')
    cyclone_bulletin = cyclone_storm_name = cyclone_issue_time = cyclone_summary = None
    cyclone_hazards = []
    if os.path.exists(bulletin_path):
        with open(bulletin_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            cyclone_bulletin = data.get('bulletin')
            cyclone_storm_name = data.get('storm_name')
            cyclone_issue_time = data.get('issue_time')
            cyclone_summary = data.get('summary')
            cyclone_hazards = data.get('hazards', [])
    return render_template('index.html', user_name=session.get('user_name'), user_role=session.get('user_role'),
        cyclone_bulletin=cyclone_bulletin, cyclone_storm_name=cyclone_storm_name, cyclone_issue_time=cyclone_issue_time, cyclone_summary=cyclone_summary, cyclone_hazards=cyclone_hazards)

@app.route('/api/reports')
def api_reports():
    reports = Report.query.filter_by(approved=True).all()
    data = []
    for r in reports:
        data.append({
            'id': r.id,
            'area': r.area,
            'lat': r.lat,
            'lng': r.lng,
            'flood_level': r.flood_level,
            'status': r.status,
            'description': r.description,
            'image_url': r.image_url,
            'timestamp': r.timestamp.isoformat(),
            'rainfall': None  # Placeholder for future weather API integration
        })
    return jsonify(data)

@app.route('/api/cyclone-impacts')
def api_cyclone_impacts():
    impacts = CycloneImpact.query.all()
    data = []
    for i in impacts:
        data.append({
            'id': i.id,
            'area': i.area,
            'lat': i.lat,
            'lng': i.lng,
            'status': i.status,
            'description': i.description,
            'timestamp': i.timestamp.isoformat()
        })
    return jsonify(data)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/report', methods=['GET', 'POST'])
@login_required
def report():
    if request.method == 'POST':
        area = request.form.get('area')
        description = request.form.get('description')
        status = request.form.get('status')
        lat = request.form.get('lat')
        lng = request.form.get('lng')
        image = request.files.get('image')
        image_url = None
        if image and allowed_file(image.filename):
            filename = secure_filename(f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{image.filename}")
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            image.save(image_path)
            image_url = '/static/uploads/' + filename
        report = Report(
            area=area,
            lat=float(lat),
            lng=float(lng),
            flood_level=None,
            status=status,
            description=description,
            image_url=image_url,
            approved=False
        )
        db.session.add(report)
        db.session.commit()
        flash('Report submitted! Awaiting admin approval.', 'success')
        return redirect(url_for('index'))
    return render_template('report.html', user_name=session.get('user_name'), user_role=session.get('user_role'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('register.html')
        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['user_role'] = user.role
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password.', 'danger')
            return render_template('login.html')
    return render_template('login.html')

@app.route('/admin', methods=['GET'])
@login_required
@admin_required
def admin_panel():
    pending_reports = Report.query.filter_by(approved=False).order_by(Report.timestamp.desc()).all()
    approved_reports = Report.query.filter_by(approved=True).order_by(Report.timestamp.desc()).all()
    return render_template('admin.html', pending_reports=pending_reports, approved_reports=approved_reports, user_name=session.get('user_name'), user_role=session.get('user_role'))

@app.route('/admin/approve/<int:report_id>', methods=['POST'])
def admin_approve(report_id):
    report = Report.query.get_or_404(report_id)
    report.approved = True
    db.session.commit()
    flash('Report approved!', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete/<int:report_id>', methods=['POST'])
def admin_delete(report_id):
    report = Report.query.get_or_404(report_id)
    db.session.delete(report)
    db.session.commit()
    flash('Report deleted.', 'info')
    return redirect(url_for('admin_panel'))

@app.route('/admin/update/<int:report_id>', methods=['POST'])
def admin_update(report_id):
    # For now, just toggle status between Safe, Alert, Flooded (demo)
    report = Report.query.get_or_404(report_id)
    if report.status == 'Safe':
        report.status = 'Alert'
    elif report.status == 'Alert':
        report.status = 'Flooded'
    else:
        report.status = 'Safe'
    db.session.commit()
    flash(f'Report status updated to {report.status}.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/update-cyclone', methods=['POST'])
@admin_required
def update_cyclone():
    import subprocess
    try:
        result = subprocess.run(['python', '/home/rhemjohn/BahawatchPH/utils/pagasa_cyclone_scraper.py'], capture_output=True, text=True, check=True)
        flash('Cyclone-Affected Areas updated!\n' + result.stdout, 'success')
    except subprocess.CalledProcessError as e:
        flash('Error updating Cyclone-Affected Areas: ' + e.stderr, 'danger')
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    app.run(debug=True) 