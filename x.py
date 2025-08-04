import os
import sqlite3
import pandas as pd
import smtplib
import logging
from datetime import datetime, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from io import BytesIO
from flask import Flask, render_template_string, request, redirect, url_for, flash, send_file, jsonify,render_template
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from flask import session
from functools import wraps
import hashlib
# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "your-secret-key-here")
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()
# HTML Template with embedded CSS and JS

# Database initialization
def init_db():
    conn = sqlite3.connect('payroll.db')
    cursor = conn.cursor()
    
    # Create employees table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            designation TEXT,
            department TEXT,
            joining_date DATE,
            ctc_monthly REAL NOT NULL,
            ctc_annual REAL NOT NULL,
            pf_opted INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create payroll table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payroll (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id TEXT NOT NULL,
            month TEXT NOT NULL,
            year INTEGER NOT NULL,
            days_worked INTEGER DEFAULT 30,
            basic_salary REAL,
            hra REAL,
            travel_allowance REAL,
            medical_allowance REAL,
            lta REAL,
            special_allowance REAL,
            employer_pf REAL,
            employee_pf REAL,
            pf_deduction REAL,
            gross_salary REAL,
            net_salary REAL,
            hike_amount REAL DEFAULT 0,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (emp_id) REFERENCES employees (emp_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create employees table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            designation TEXT,
            department TEXT,
            joining_date DATE,
            ctc_monthly REAL NOT NULL,
            ctc_annual REAL NOT NULL,
            pf_opted INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create payroll table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payroll (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id TEXT NOT NULL,
            month TEXT NOT NULL,
            year INTEGER NOT NULL,
            days_worked INTEGER DEFAULT 30,
            basic_salary REAL,
            hra REAL,
            travel_allowance REAL,
            medical_allowance REAL,
            lta REAL,
            special_allowance REAL,
            employer_pf REAL,
            employee_pf REAL,
            pf_deduction REAL,
            gross_salary REAL,
            net_salary REAL,
            hike_amount REAL DEFAULT 0,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (emp_id) REFERENCES employees (emp_id)
        )
    ''')
    
    # Insert default admin users if they don't exist
    admin_users = [
        ('admin@payrollpro.com', 'admin123', 'Admin User', 'Admin'),
        ('hr@payrollpro.com', 'hr123', 'HR Manager', 'HR')
    ]
    
    for email, password, name, role in admin_users:
        existing_user = cursor.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if not existing_user:
            password_hash = hash_password(password)
            cursor.execute('''
                INSERT INTO users (email, password_hash, name, role)
                VALUES (?, ?, ?, ?)
            ''', (email, password_hash, name, role))
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()
def get_db_path():
    if os.path.exists('/tmp'):
        return '/tmp/payroll.db'  # Vercel temp directory
    return 'payroll.db'  # Local development
def get_db_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn
def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def calculate_salary_components(ctc_monthly, pf_opted=True):
    """Calculate salary components based on CTC structure from the provided image"""
    # Proportional calculation based on the 1 lakh example
    ratio = ctc_monthly / 100000.0
    
    # Base amounts from the 1 lakh structure
    base_basic = 50000
    base_hra = 20000
    base_travel = 1600
    base_medical = 1250
    base_lta = 2083
    base_employer_pf = 1800
    
    # Calculate proportional amounts
    basic = base_basic * ratio
    hra = base_hra * ratio
    travel_allowance = base_travel * ratio
    medical_allowance = base_medical * ratio
    lta = base_lta * ratio
    employer_pf = base_employer_pf * ratio
    
    # Special allowance is the remainder
    other_components = basic + hra + travel_allowance + medical_allowance + lta + employer_pf
    special_allowance = max(0, ctc_monthly - other_components + employer_pf)  # Add back employer_pf as it's not part of gross
    
    # PF calculation based on salary and opt-in status
    if not pf_opted or ctc_monthly < 15000:
        pf_deduction = 0
    elif ctc_monthly <= 19999:
        pf_deduction = 150
    else:
        pf_deduction = 200
    
    employee_pf = pf_deduction
    
    gross_salary = basic + hra + travel_allowance + medical_allowance + lta + special_allowance
    net_salary = gross_salary - pf_deduction
    
    return {
        'basic': round(basic, 2),
        'hra': round(hra, 2),
        'travel_allowance': round(travel_allowance, 2),
        'medical_allowance': round(medical_allowance, 2),
        'lta': round(lta, 2),
        'special_allowance': round(special_allowance, 2),
        'employer_pf': round(employer_pf, 2),
        'employee_pf': round(employee_pf, 2),
        'pf_deduction': round(pf_deduction, 2),
        'gross_salary': round(gross_salary, 2),
        'net_salary': round(net_salary, 2)
    }

def generate_payslip_pdf(employee_data, payroll_data):
    """Generate PDF payslip for an employee"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.darkblue
    )
    
    content = []
    
    # Title
    content.append(Paragraph("PAYSLIP", title_style))
    content.append(Spacer(1, 20))
    
    # Employee Information
    emp_info = [
        ['Employee ID:', employee_data['emp_id']],
        ['Name:', employee_data['name']],
        ['Designation:', employee_data['designation'] or 'N/A'],
        ['Department:', employee_data['department'] or 'N/A'],
        ['Pay Period:', f"{payroll_data['month']} {payroll_data['year']}"],
        ['Days Worked:', str(payroll_data['days_worked'])]
    ]
    
    emp_table = Table(emp_info, colWidths=[2*inch, 3*inch])
    emp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    content.append(emp_table)
    content.append(Spacer(1, 20))
    
    # Salary Breakdown
    content.append(Paragraph("SALARY BREAKDOWN", heading_style))
    
    salary_data = [
        ['Component', 'Amount (₹)'],
        ['Basic Salary', f"{payroll_data['basic_salary']:,.2f}"],
        ['HRA', f"{payroll_data['hra']:,.2f}"],
        ['Travel Allowance', f"{payroll_data['travel_allowance']:,.2f}"],
        ['Medical Allowance', f"{payroll_data['medical_allowance']:,.2f}"],
        ['LTA', f"{payroll_data['lta']:,.2f}"],
        ['Special Allowance', f"{payroll_data['special_allowance']:,.2f}"],
        ['', ''],
        ['Gross Salary', f"{payroll_data['gross_salary']:,.2f}"],
        ['', ''],
        ['Deductions:', ''],
        ['PF Contribution', f"{payroll_data['pf_deduction']:,.2f}"],
        ['', ''],
        ['NET SALARY', f"{payroll_data['net_salary']:,.2f}"]
    ]
    
    salary_table = Table(salary_data, colWidths=[3*inch, 2*inch])
    salary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('BACKGROUND', (0, 7), (-1, 7), colors.lightgrey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.darkblue),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    content.append(salary_table)
    content.append(Spacer(1, 30))
    
    # Footer
    footer_text = f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    content.append(Paragraph(footer_text, styles['Normal']))
    
    doc.build(content)
    buffer.seek(0)
    return buffer

def send_payslip_email(employee_email, employee_name, payslip_pdf, month, year):
    """Send payslip via email"""
    try:
        msg = MIMEMultipart()
        msg['From'] = "stud.studentsmart@gmail.com"
        msg['To'] = employee_email
        msg['Subject'] = f"Payslip for {month} {year}"
        
        body = f"""
        Dear {employee_name},
        
        Please find attached your payslip for {month} {year}.
        
        If you have any questions regarding your payslip, please contact HR.
        
        Best regards,
        HR Team
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach PDF
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(payslip_pdf.read())
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename="payslip_{month}_{year}.pdf"'
        )
        msg.attach(part)
        
        # SMTP configuration
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login("stud.studentsmart@gmail.com", "jygr uhcl odmk flve")
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        logging.error(f"Email sending failed: {str(e)}")
        return False

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully!', 'success')
    return redirect(url_for('login'))
@app.route('/')
@login_required
def dashboard():
    conn = get_db_connection()
    
    # Get dashboard statistics
    total_employees = conn.execute('SELECT COUNT(*) FROM employees').fetchone()[0]
    
    # Get recent payroll entries
    recent_payroll_raw = conn.execute('''
        SELECT p.*, e.name 
        FROM payroll p 
        JOIN employees e ON p.emp_id = e.emp_id 
        ORDER BY p.processed_at DESC 
        LIMIT 5
    ''').fetchall()
    
    recent_payroll = []
    for row in recent_payroll_raw:
        recent_payroll.append({
            'emp_id': row['emp_id'],
            'name': row['name'],
            'month': row['month'],
            'year': row['year'],
            'net_salary': row['net_salary']
        })
    
    # Get employees
    employees_raw = conn.execute('SELECT * FROM employees ORDER BY name').fetchall()
    employees = []
    for row in employees_raw:
        employees.append({
            'emp_id': row['emp_id'],
            'name': row['name'],
            'email': row['email'],
            'designation': row['designation'],
            'department': row['department'],
            'ctc_monthly': row['ctc_monthly'],
            'pf_opted': row['pf_opted'],
            'joining_date': row['joining_date']
        })
    
    # Get all payroll records
    all_payroll_raw = conn.execute('''
        SELECT p.*, e.name 
        FROM payroll p 
        JOIN employees e ON p.emp_id = e.emp_id 
        ORDER BY p.processed_at DESC 
        LIMIT 20
    ''').fetchall()
    
    # Convert to dictionaries for JSON serialization
    all_payroll = []
    for row in all_payroll_raw:
        all_payroll.append({
            'emp_id': row['emp_id'],
            'name': row['name'],
            'month': row['month'],
            'year': row['year'],
            'days_worked': row['days_worked'],
            'gross_salary': row['gross_salary'],
            'net_salary': row['net_salary'],
            'basic_salary': row['basic_salary'],
            'hra': row['hra'],
            'travel_allowance': row['travel_allowance'],
            'medical_allowance': row['medical_allowance'],
            'lta': row['lta'],
            'special_allowance': row['special_allowance'],
            'pf_deduction': row['pf_deduction'],
            'hike_amount': row['hike_amount']
        })
    
    # Monthly payroll stats
    monthly_stats_raw = conn.execute('''
        SELECT month, year, COUNT(*) as count, SUM(net_salary) as total_payout
        FROM payroll 
        GROUP BY month, year 
        ORDER BY year DESC, month DESC
        LIMIT 6
    ''').fetchall()
    
    monthly_stats = []
    for row in monthly_stats_raw:
        monthly_stats.append({
            'month': row['month'],
            'year': row['year'],
            'count': row['count'],
            'total_payout': float(row['total_payout']) if row['total_payout'] else 0
        })
    
    conn.close()
    
    return render_template('index1.html', 
                         total_employees=total_employees,
                         recent_payroll=recent_payroll,
                         employees=employees,
                         all_payroll=all_payroll,
                         monthly_stats=monthly_stats)

@app.route('/add_employee', methods=['POST'])
def add_employee():
    try:
        emp_id = request.form['emp_id']
        name = request.form['name']
        email = request.form['email']
        designation = request.form.get('designation', '')
        department = request.form.get('department', '')
        joining_date = request.form.get('joining_date', date.today().isoformat())
        ctc_monthly = float(request.form['ctc_monthly'])
        ctc_annual = ctc_monthly * 12
        pf_opted = 1 if request.form.get('pf_opted') == 'on' else 0
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO employees (emp_id, name, email, designation, department, 
                                 joining_date, ctc_monthly, ctc_annual, pf_opted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (emp_id, name, email, designation, department, joining_date, 
              ctc_monthly, ctc_annual, pf_opted))
        conn.commit()
        conn.close()
        
        flash('Employee added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding employee: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/download_employee_template')
def download_employee_template():
    """Generate and download employee template Excel file"""
    data = {
        'emp_id': ['EMP001'],
        'name': ['John Doe'],
        'email': ['john@example.com'],
        'designation': ['Developer'],
        'department': ['IT'],
        'joining_date': ['2024-01-01'],
        'ctc_monthly': [50000],
        'pf_opted': ['Yes']
    }
    
    df = pd.DataFrame(data)
    
    output = BytesIO()
    df.to_excel(output, sheet_name='Employee_Template', index=False, engine='openpyxl')
    
    output.seek(0)
    return send_file(output, 
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, 
                     download_name='employee_template.xlsx')

@app.route('/bulk_add_employees', methods=['POST'])
def bulk_add_employees():
    if 'file' not in request.files:
        flash('No file selected!', 'error')
        return redirect(url_for('dashboard'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected!', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        df = pd.read_excel(file)
        conn = get_db_connection()
        
        success_count = 0
        error_count = 0
        
        for _, row in df.iterrows():
            try:
                pf_opted = 1 if str(row['pf_opted']).lower() in ['yes', '1', 'true'] else 0
                ctc_monthly = float(row['ctc_monthly'])
                ctc_annual = ctc_monthly * 12
                
                conn.execute('''
                    INSERT INTO employees (emp_id, name, email, designation, department, 
                                         joining_date, ctc_monthly, ctc_annual, pf_opted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (str(row['emp_id']), str(row['name']), str(row['email']), 
                      str(row.get('designation', '')), str(row.get('department', '')), 
                      str(row.get('joining_date', date.today().isoformat())), 
                      ctc_monthly, ctc_annual, pf_opted))
                success_count += 1
            except Exception as e:
                logging.error(f"Error adding employee {row.get('emp_id', 'Unknown')}: {str(e)}")
                error_count += 1
                continue
        
        conn.commit()
        conn.close()
        
        flash(f'Successfully added {success_count} employees. {error_count} errors.', 'success')
    except Exception as e:
        flash(f'Error processing file: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/download_payroll_template')
def download_payroll_template():
    """Generate and download payroll template Excel file"""
    data = {
        'emp_id': ['EMP001'],
        'name': ['John Doe'],
        'days_worked': [30],
        'pf_opted': ['Yes']
    }
    
    df = pd.DataFrame(data)
    
    output = BytesIO()
    df.to_excel(output, sheet_name='Payroll_Template', index=False, engine='openpyxl')
    
    output.seek(0)
    return send_file(output, 
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, 
                     download_name='payroll_template.xlsx')

@app.route('/process_individual_payroll', methods=['POST'])
def process_individual_payroll():
    try:
        emp_id = request.form['emp_id']
        days_worked = int(float(request.form.get('days_worked', 30)))
        month = request.form['month']
        year = int(request.form['year'])
        pf_opted = 1 if request.form.get('pf_opted') == 'on' else 0
        hike_amount = float(request.form.get('hike_amount', 0))
        
        conn = get_db_connection()
        
        # Get employee data
        employee = conn.execute('SELECT * FROM employees WHERE emp_id = ?', (emp_id,)).fetchone()
        if not employee:
            flash('Employee not found!', 'error')
            return redirect(url_for('dashboard'))
        
        # Apply hike if specified
        ctc_monthly = employee['ctc_monthly'] + hike_amount
        
        # Calculate salary components
        salary_components = calculate_salary_components(ctc_monthly, bool(pf_opted))
        
        # Adjust for days worked
        if days_worked != 30:
            ratio = days_worked / 30.0
            for key in salary_components:
                if key != 'employer_pf':  # Employer PF remains constant
                    salary_components[key] = round(salary_components[key] * ratio, 2)
        
        # Check if payroll already exists for this employee/month/year
        existing = conn.execute('''
            SELECT id FROM payroll 
            WHERE emp_id = ? AND month = ? AND year = ?
        ''', (emp_id, month, year)).fetchone()
        
        if existing:
            # Update existing payroll
            conn.execute('''
                UPDATE payroll SET
                    days_worked = ?, basic_salary = ?, hra = ?, travel_allowance = ?,
                    medical_allowance = ?, lta = ?, special_allowance = ?, employer_pf = ?,
                    employee_pf = ?, pf_deduction = ?, gross_salary = ?, net_salary = ?,
                    hike_amount = ?, processed_at = CURRENT_TIMESTAMP
                WHERE emp_id = ? AND month = ? AND year = ?
            ''', (days_worked, salary_components['basic'], salary_components['hra'],
                  salary_components['travel_allowance'], salary_components['medical_allowance'],
                  salary_components['lta'], salary_components['special_allowance'],
                  salary_components['employer_pf'], salary_components['employee_pf'],
                  salary_components['pf_deduction'], salary_components['gross_salary'],
                  salary_components['net_salary'], hike_amount, emp_id, month, year))
        else:
            # Insert new payroll
            conn.execute('''
                INSERT INTO payroll (emp_id, month, year, days_worked, basic_salary, hra, 
                                   travel_allowance, medical_allowance, lta, special_allowance,
                                   employer_pf, employee_pf, pf_deduction, gross_salary, 
                                   net_salary, hike_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (emp_id, month, year, days_worked, salary_components['basic'],
                  salary_components['hra'], salary_components['travel_allowance'],
                  salary_components['medical_allowance'], salary_components['lta'],
                  salary_components['special_allowance'], salary_components['employer_pf'],
                  salary_components['employee_pf'], salary_components['pf_deduction'],
                  salary_components['gross_salary'], salary_components['net_salary'], hike_amount))
        
        # Update employee CTC if hike was applied
        if hike_amount > 0:
            new_ctc_monthly = employee['ctc_monthly'] + hike_amount
            new_ctc_annual = new_ctc_monthly * 12
            conn.execute('''
                UPDATE employees SET ctc_monthly = ?, ctc_annual = ? WHERE emp_id = ?
            ''', (new_ctc_monthly, new_ctc_annual, emp_id))
        
        conn.commit()
        conn.close()
        
        flash(f'Payroll processed successfully for {employee["name"]}!', 'success')
    except Exception as e:
        flash(f'Error processing payroll: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/bulk_process_payroll', methods=['POST'])
def bulk_process_payroll():
    if 'file' not in request.files:
        flash('No file selected!', 'error')
        return redirect(url_for('dashboard'))
    
    file = request.files['file']
    month = request.form['month']
    year = int(request.form['year'])
    
    if file.filename == '':
        flash('No file selected!', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        df = pd.read_excel(file)
        conn = get_db_connection()
        
        success_count = 0
        error_count = 0
        
        for _, row in df.iterrows():
            try:
                emp_id = str(row['emp_id'])
                days_worked = int(float(row.get('days_worked', 30)))
                pf_opted = str(row.get('pf_opted', 'Yes')).lower() in ['yes', '1', 'true']
                
                # Get employee data
                employee = conn.execute('SELECT * FROM employees WHERE emp_id = ?', (emp_id,)).fetchone()
                if not employee:
                    error_count += 1
                    continue
                
                # Calculate salary components
                salary_components = calculate_salary_components(employee['ctc_monthly'], pf_opted)
                
                # Adjust for days worked
                if days_worked != 30:
                    ratio = days_worked / 30.0
                    for key in salary_components:
                        if key != 'employer_pf':  # Employer PF remains constant
                            salary_components[key] = round(salary_components[key] * ratio, 2)
                
                # Check if payroll already exists
                existing = conn.execute('''
                    SELECT id FROM payroll 
                    WHERE emp_id = ? AND month = ? AND year = ?
                ''', (emp_id, month, year)).fetchone()
                
                if existing:
                    # Update existing payroll
                    conn.execute('''
                        UPDATE payroll SET
                            days_worked = ?, basic_salary = ?, hra = ?, travel_allowance = ?,
                            medical_allowance = ?, lta = ?, special_allowance = ?, employer_pf = ?,
                            employee_pf = ?, pf_deduction = ?, gross_salary = ?, net_salary = ?,
                            processed_at = CURRENT_TIMESTAMP
                        WHERE emp_id = ? AND month = ? AND year = ?
                    ''', (days_worked, salary_components['basic'], salary_components['hra'],
                          salary_components['travel_allowance'], salary_components['medical_allowance'],
                          salary_components['lta'], salary_components['special_allowance'],
                          salary_components['employer_pf'], salary_components['employee_pf'],
                          salary_components['pf_deduction'], salary_components['gross_salary'],
                          salary_components['net_salary'], emp_id, month, year))
                else:
                    # Insert new payroll
                    conn.execute('''
                        INSERT INTO payroll (emp_id, month, year, days_worked, basic_salary, hra, 
                                           travel_allowance, medical_allowance, lta, special_allowance,
                                           employer_pf, employee_pf, pf_deduction, gross_salary, 
                                           net_salary, hike_amount)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (emp_id, month, year, days_worked, salary_components['basic'],
                          salary_components['hra'], salary_components['travel_allowance'],
                          salary_components['medical_allowance'], salary_components['lta'],
                          salary_components['special_allowance'], salary_components['employer_pf'],
                          salary_components['employee_pf'], salary_components['pf_deduction'],
                          salary_components['gross_salary'], salary_components['net_salary'], 0))
                
                success_count += 1
            except Exception as e:
                logging.error(f"Error processing payroll for {row.get('emp_id', 'Unknown')}: {str(e)}")
                error_count += 1
                continue
        
        conn.commit()
        conn.close()
        
        flash(f'Successfully processed {success_count} payrolls. {error_count} errors.', 'success')
    except Exception as e:
        flash(f'Error processing file: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/apply_hike', methods=['POST'])
def apply_hike():
    try:
        emp_id = request.form['emp_id']
        hike_amount = float(request.form['hike_amount'])
        hike_reason = request.form.get('hike_reason', '')
        
        conn = get_db_connection()
        
        # Get employee data
        employee = conn.execute('SELECT * FROM employees WHERE emp_id = ?', (emp_id,)).fetchone()
        if not employee:
            flash('Employee not found!', 'error')
            return redirect(url_for('dashboard'))
        
        # Update employee CTC
        new_ctc_monthly = employee['ctc_monthly'] + hike_amount
        new_ctc_annual = new_ctc_monthly * 12
        
        conn.execute('''
            UPDATE employees SET ctc_monthly = ?, ctc_annual = ? WHERE emp_id = ?
        ''', (new_ctc_monthly, new_ctc_annual, emp_id))
        
        conn.commit()
        conn.close()
        
        flash(f'Salary hike of ₹{hike_amount:,.2f} applied successfully for {employee["name"]}!', 'success')
    except Exception as e:
        flash(f'Error applying hike: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/send_payslips', methods=['POST'])
def send_payslips():
    try:
        month = request.form['month']
        year = int(request.form['year'])
        
        conn = get_db_connection()
        
        # Get all payroll records for the specified month/year
        payroll_records = conn.execute('''
            SELECT p.*, e.name, e.email, e.designation, e.department
            FROM payroll p 
            JOIN employees e ON p.emp_id = e.emp_id 
            WHERE p.month = ? AND p.year = ?
        ''', (month, year)).fetchall()
        
        if not payroll_records:
            flash(f'No payroll records found for {month} {year}!', 'error')
            return redirect(url_for('dashboard'))
        
        success_count = 0
        error_count = 0
        
        for record in payroll_records:
            try:
                # Generate payslip PDF
                employee_data = {
                    'emp_id': record['emp_id'],
                    'name': record['name'],
                    'designation': record['designation'],
                    'department': record['department']
                }
                
                payslip_pdf = generate_payslip_pdf(employee_data, record)
                
                # Send email
                if send_payslip_email(record['email'], record['name'], payslip_pdf, month, year):
                    success_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                logging.error(f"Error sending payslip to {record['name']}: {str(e)}")
                error_count += 1
                continue
        
        conn.close()
        
        flash(f'Payslips sent successfully to {success_count} employees. {error_count} failed.', 'success')
    except Exception as e:
        flash(f'Error sending payslips: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/api/payslip/<emp_id>/<month>/<int:year>')
def api_payslip(emp_id, month, year):
    """API endpoint to get payslip data as HTML"""
    try:
        conn = get_db_connection()
        
        # Get payroll record
        payroll = conn.execute('''
            SELECT p.*, e.name, e.designation, e.department, e.email
            FROM payroll p 
            JOIN employees e ON p.emp_id = e.emp_id 
            WHERE p.emp_id = ? AND p.month = ? AND p.year = ?
        ''', (emp_id, month, year)).fetchone()
        
        if not payroll:
            return jsonify({'success': False, 'message': 'Payroll record not found'})
        
        # Generate HTML payslip
        payslip_html = f"""
        <div class="payslip-container" style="max-width: 800px; margin: 0 auto; font-family: Arial, sans-serif;">
            <div class="payslip-header" style="text-align: center; margin-bottom: 30px; padding: 20px; background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%); color: white; border-radius: 8px;">
                <h2 style="margin: 0; font-size: 2rem;">PAYSLIP</h2>
                <p style="margin: 5px 0 0 0; opacity: 0.9;">Salary Statement for {month} {year}</p>
            </div>
            
            <div class="employee-info" style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                <div class="row" style="display: flex; flex-wrap: wrap;">
                    <div style="flex: 1; min-width: 300px; margin-bottom: 10px;">
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr><td style="padding: 8px 0; font-weight: bold; width: 40%;">Employee ID:</td><td style="padding: 8px 0;">{payroll['emp_id']}</td></tr>
                            <tr><td style="padding: 8px 0; font-weight: bold;">Name:</td><td style="padding: 8px 0;">{payroll['name']}</td></tr>
                            <tr><td style="padding: 8px 0; font-weight: bold;">Designation:</td><td style="padding: 8px 0;">{payroll['designation'] or 'N/A'}</td></tr>
                            <tr><td style="padding: 8px 0; font-weight: bold;">Department:</td><td style="padding: 8px 0;">{payroll['department'] or 'N/A'}</td></tr>
                            <tr><td style="padding: 8px 0; font-weight: bold;">Days Worked:</td><td style="padding: 8px 0;">{payroll['days_worked']} days</td></tr>
                        </table>
                    </div>
                </div>
            </div>
            
            <div class="salary-breakdown" style="background: white; border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
                <div class="section-header" style="background: #2c3e50; color: white; padding: 15px; text-align: center;">
                    <h4 style="margin: 0;">SALARY BREAKDOWN</h4>
                </div>
                
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #3498db; color: white;">
                            <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">Component</th>
                            <th style="padding: 12px; text-align: right; border: 1px solid #ddd;">Amount (₹)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td style="padding: 10px; border: 1px solid #ddd;">Basic Salary</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">₹{payroll['basic_salary']:,.2f}</td></tr>
                        <tr><td style="padding: 10px; border: 1px solid #ddd;">HRA</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">₹{payroll['hra']:,.2f}</td></tr>
                        <tr><td style="padding: 10px; border: 1px solid #ddd;">Travel Allowance</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">₹{payroll['travel_allowance']:,.2f}</td></tr>
                        <tr><td style="padding: 10px; border: 1px solid #ddd;">Medical Allowance</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">₹{payroll['medical_allowance']:,.2f}</td></tr>
                        <tr><td style="padding: 10px; border: 1px solid #ddd;">LTA</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">₹{payroll['lta']:,.2f}</td></tr>
                        <tr><td style="padding: 10px; border: 1px solid #ddd;">Special Allowance</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">₹{payroll['special_allowance']:,.2f}</td></tr>
                        <tr style="background: #e8f5e8; font-weight: bold;"><td style="padding: 12px; border: 1px solid #ddd;">GROSS SALARY</td><td style="padding: 12px; text-align: right; border: 1px solid #ddd;">₹{payroll['gross_salary']:,.2f}</td></tr>
                        <tr><td style="padding: 10px; border: 1px solid #ddd; color: #e74c3c; font-weight: bold;">Deductions:</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;"></td></tr>
                        <tr><td style="padding: 10px; border: 1px solid #ddd; padding-left: 30px;">PF Contribution</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd; color: #e74c3c;">₹{payroll['pf_deduction']:,.2f}</td></tr>
                        <tr style="background: #2c3e50; color: white; font-weight: bold; font-size: 1.1em;"><td style="padding: 15px; border: 1px solid #ddd;">NET SALARY</td><td style="padding: 15px; text-align: right; border: 1px solid #ddd;">₹{payroll['net_salary']:,.2f}</td></tr>
                    </tbody>
                </table>
            </div>
            
            {f'<div style="margin-top: 20px; padding: 15px; background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px;"><i class="fas fa-info-circle"></i> <strong>Salary Hike Applied:</strong> ₹{payroll["hike_amount"]:,.2f} added to monthly CTC</div>' if payroll['hike_amount'] > 0 else ''}
            
            <div class="footer" style="margin-top: 30px; text-align: center; color: #666; font-size: 0.9em;">
                <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p style="margin-top: 10px;">This is a system-generated payslip. For any queries, please contact HR.</p>
            </div>
        </div>
        """
        
        conn.close()
        
        return jsonify({
            'success': True,
            'html': payslip_html,
            'emp_id': emp_id,
            'month': month,
            'year': year
        })
        
    except Exception as e:
        logging.error(f"Error generating payslip HTML: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/payrolls')
def api_payrolls():
    """API endpoint to get filtered payroll records"""
    try:
        month = request.args.get('month')
        year = request.args.get('year')
        
        conn = get_db_connection()
        
        query = '''
            SELECT p.*, e.name 
            FROM payroll p 
            JOIN employees e ON p.emp_id = e.emp_id 
        '''
        
        params = []
        conditions = []
        
        if month:
            conditions.append('p.month = ?')
            params.append(month)
        
        if year:
            conditions.append('p.year = ?')
            params.append(int(year))
        
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        
        query += ' ORDER BY p.processed_at DESC LIMIT 50'
        
        payrolls = conn.execute(query, params).fetchall()
        
        # Convert to list of dictionaries
        payroll_list = []
        for payroll in payrolls:
            payroll_list.append({
                'emp_id': payroll['emp_id'],
                'name': payroll['name'],
                'month': payroll['month'],
                'year': payroll['year'],
                'days_worked': payroll['days_worked'],
                'gross_salary': payroll['gross_salary'],
                'net_salary': payroll['net_salary'],
                'basic_salary': payroll['basic_salary'],
                'hra': payroll['hra'],
                'travel_allowance': payroll['travel_allowance'],
                'medical_allowance': payroll['medical_allowance'],
                'lta': payroll['lta'],
                'special_allowance': payroll['special_allowance'],
                'pf_deduction': payroll['pf_deduction'],
                'hike_amount': payroll['hike_amount']
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'payrolls': payroll_list
        })
        
    except Exception as e:
        logging.error(f"Error fetching payrolls: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/download_payslip/<emp_id>/<month>/<int:year>')
def download_payslip(emp_id, month, year):
    """Download payslip as PDF"""
    try:
        conn = get_db_connection()
        
        # Get employee and payroll data
        employee = conn.execute('SELECT * FROM employees WHERE emp_id = ?', (emp_id,)).fetchone()
        payroll = conn.execute('''
            SELECT * FROM payroll 
            WHERE emp_id = ? AND month = ? AND year = ?
        ''', (emp_id, month, year)).fetchone()
        
        if not employee or not payroll:
            flash('Employee or payroll record not found!', 'error')
            return redirect(url_for('dashboard'))
        
        # Generate PDF
        payslip_pdf = generate_payslip_pdf(employee, payroll)
        
        conn.close()
        
        return send_file(payslip_pdf,
                        mimetype='application/pdf',
                        as_attachment=True,
                        download_name=f'payslip_{emp_id}_{month}_{year}.pdf')
        
    except Exception as e:
        flash(f'Error generating payslip: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/download_report/<month>/<int:year>')
def download_report(month, year):
    """Download complete payroll report for selected month/year as Excel"""
    try:
        conn = get_db_connection()
        
        # Get all payroll records for the month/year
        payrolls = conn.execute('''
            SELECT p.*, e.name, e.email, e.designation, e.department
            FROM payroll p 
            JOIN employees e ON p.emp_id = e.emp_id 
            WHERE p.month = ? AND p.year = ?
            ORDER BY e.name
        ''', (month, year)).fetchall()
        
        if not payrolls:
            flash(f'No payroll records found for {month} {year}!', 'error')
            return redirect(url_for('dashboard'))
        
        # Create Excel workbook
        import pandas as pd
        from io import BytesIO
        
        # Convert payroll data to list of dictionaries
        data = []
        for payroll in payrolls:
            data.append({
                'Employee ID': payroll['emp_id'],
                'Name': payroll['name'],
                'Email': payroll['email'],
                'Designation': payroll['designation'] or 'N/A',
                'Department': payroll['department'] or 'N/A',
                'Month': payroll['month'],
                'Year': payroll['year'],
                'Days Worked': payroll['days_worked'],
                'Basic Salary': payroll['basic_salary'],
                'HRA': payroll['hra'],
                'Travel Allowance': payroll['travel_allowance'],
                'Medical Allowance': payroll['medical_allowance'],
                'LTA': payroll['lta'],
                'Special Allowance': payroll['special_allowance'],
                'Gross Salary': payroll['gross_salary'],
                'PF Deduction': payroll['pf_deduction'],
                'Net Salary': payroll['net_salary'],
                'Hike Amount': payroll['hike_amount'],
                'Processed Date': payroll['processed_at']
            })
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=f'{month}_{year}_Payroll', index=False)
            
            # Add summary sheet
            summary_data = {
                'Metric': [
                    'Total Employees',
                    'Total Gross Salary',
                    'Total PF Deduction',
                    'Total Net Salary',
                    'Average Gross Salary',
                    'Average Net Salary'
                ],
                'Value': [
                    len(payrolls),
                    f"₹{df['Gross Salary'].sum():.2f}",
                    f"₹{df['PF Deduction'].sum():.2f}",
                    f"₹{df['Net Salary'].sum():.2f}",
                    f"₹{df['Gross Salary'].mean():.2f}",
                    f"₹{df['Net Salary'].mean():.2f}"
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        output.seek(0)
        conn.close()
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'payroll_report_{month}_{year}.xlsx'
        )
        
    except Exception as e:
        logging.error(f"Error generating report: {str(e)}")
        flash(f'Error generating report: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('''
            SELECT * FROM users WHERE email = ? AND password_hash = ?
        ''', (email, hash_password(password))).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            flash(f'Welcome back, {user["name"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!', 'error')
    
    return render_template('login.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)