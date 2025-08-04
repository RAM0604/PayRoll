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
from flask import Flask, render_template_string, request, redirect, url_for, flash, send_file, jsonify
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
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PayrollPro - Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --primary-color: #2c3e50;
            --secondary-color: #3498db;
            --success-color: #27ae60;
            --warning-color: #f39c12;
            --danger-color: #e74c3c;
            --light-bg: #f8f9fa;
            --card-shadow: 0 0.125rem 0.25rem rgba(0,0,0,0.075);
        }

        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        .dashboard-container {
            background: white;
            margin: 20px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }

        .header h1 {
            margin: 0;
            font-size: 2.5rem;
            font-weight: 300;
        }

        .header p {
            margin: 10px 0 0 0;
            opacity: 0.9;
        }

        .stats-row {
            padding: 30px;
            background: var(--light-bg);
        }

        .stat-card {
            background: white;
            border-radius: 12px;
            padding: 25px;
            text-align: center;
            box-shadow: var(--card-shadow);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            border-left: 4px solid;
            margin-bottom: 20px;
        }

        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        }

        .stat-card.employees { border-left-color: var(--secondary-color); }
        .stat-card.payroll { border-left-color: var(--success-color); }
        .stat-card.pending { border-left-color: var(--warning-color); }
        .stat-card.total { border-left-color: var(--danger-color); }

        .stat-card i {
            font-size: 2.5rem;
            margin-bottom: 15px;
            opacity: 0.8;
        }

        .stat-card h3 {
            font-size: 2rem;
            font-weight: bold;
            margin: 0;
        }

        .stat-card p {
            margin: 0;
            color: #666;
            font-size: 0.9rem;
        }

        .main-content {
            padding: 30px;
        }

        .section-card {
            background: white;
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: var(--card-shadow);
            border: 1px solid #e9ecef;
        }

        .section-title {
            color: var(--primary-color);
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e9ecef;
        }

        .btn-custom {
            border-radius: 8px;
            padding: 10px 20px;
            font-weight: 500;
            transition: all 0.3s ease;
            border: none;
            margin: 5px;
        }

        .btn-primary-custom {
            background: linear-gradient(135deg, var(--secondary-color) 0%, #2980b9 100%);
            color: white;
        }

        .btn-primary-custom:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(52, 152, 219, 0.4);
            color: white;
        }

        .btn-success-custom {
            background: linear-gradient(135deg, var(--success-color) 0%, #219a52 100%);
            color: white;
        }

        .btn-success-custom:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(39, 174, 96, 0.4);
            color: white;
        }

        .btn-warning-custom {
            background: linear-gradient(135deg, var(--warning-color) 0%, #d68910 100%);
            color: white;
        }

        .btn-warning-custom:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(243, 156, 18, 0.4);
            color: white;
        }

        .btn-info-custom {
            background: linear-gradient(135deg, #17a2b8 0%, #138496 100%);
            color: white;
        }

        .btn-info-custom:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(23, 162, 184, 0.4);
            color: white;
        }

        .form-control, .form-select {
            border-radius: 8px;
            border: 1px solid #ddd;
            padding: 12px;
            transition: all 0.3s ease;
        }

        .form-control:focus, .form-select:focus {
            border-color: var(--secondary-color);
            box-shadow: 0 0 0 0.2rem rgba(52, 152, 219, 0.25);
        }

        .table {
            border-radius: 8px;
            overflow: hidden;
            box-shadow: var(--card-shadow);
        }

        .table thead {
            background: var(--primary-color);
            color: white;
        }

        .table tbody tr:hover {
            background-color: rgba(52, 152, 219, 0.1);
        }

        .alert {
            border-radius: 8px;
            border: none;
            box-shadow: var(--card-shadow);
        }

        .modal-content {
            border-radius: 12px;
            border: none;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }

        .modal-header {
            background: var(--primary-color);
            color: white;
            border-radius: 12px 12px 0 0;
        }

        .file-upload-area {
            border: 2px dashed #ddd;
            border-radius: 8px;
            padding: 30px;
            text-align: center;
            background: #f8f9fa;
            transition: all 0.3s ease;
        }

        .file-upload-area:hover {
            border-color: var(--secondary-color);
            background: rgba(52, 152, 219, 0.1);
        }

        .chart-container {
            position: relative;
            height: 300px;
            margin: 20px 0;
        }

        @media (max-width: 768px) {
            .dashboard-container {
                margin: 10px;
            }
            
            .header {
                padding: 20px;
            }
            
            .header h1 {
                font-size: 2rem;
            }
            
            .stats-row, .main-content {
                padding: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="dashboard-container">
        <!-- Header -->
        <div class="header">
            <h1><i class="fas fa-calculator"></i> PayrollPro</h1>
            <p>Comprehensive Payroll Management System</p>
            <div style="margin-top: 15px;">
                <span style="opacity: 0.9; margin-right: 20px;">
                    <i class="fas fa-user me-2"></i>{{ session.user_name }} ({{ session.user_role }})
                </span>
                <a href="{{ url_for('logout') }}" class="btn btn-outline-light btn-sm">
                    <i class="fas fa-sign-out-alt me-1"></i> Logout
                </a>
            </div>
        </div>
        

        <!-- Flash Messages -->
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="container mt-3">
                    {% for category, message in messages %}
                        <div class="alert alert-{{ 'danger' if category == 'error' else 'success' }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <!-- Statistics Row -->
        <div class="stats-row">
            <div class="row">
                <div class="col-md-3">
                    <div class="stat-card employees">
                        <i class="fas fa-users text-info"></i>
                        <h3>{{ total_employees }}</h3>
                        <p>Total Employees</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-card payroll">
                        <i class="fas fa-money-bill-wave text-success"></i>
                        <h3>{{ recent_payroll|length }}</h3>
                        <p>Recent Payrolls</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-card pending">
                        <i class="fas fa-clock text-warning"></i>
                        <h3>{{ monthly_stats|length }}</h3>
                        <p>Monthly Records</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-card total">
                        <i class="fas fa-chart-line text-danger"></i>
                        <h3>₹{{ "%.0f"|format(monthly_stats[0].total_payout if monthly_stats else 0) }}</h3>
                        <p>Latest Month Payout</p>
                    </div>
                </div>
            </div>
        </div>
        

        <!-- Main Content -->
        <div class="main-content">
            <div class="row">
                <!-- Employee Management -->
                <div class="col-lg-6">
                    <div class="section-card">
                        <h3 class="section-title"><i class="fas fa-user-plus"></i> Employee Management</h3>
                        
                        <!-- Add Single Employee -->
                        <div class="mb-4">
                            <button class="btn btn-primary-custom btn-custom" data-bs-toggle="modal" data-bs-target="#addEmployeeModal">
                                <i class="fas fa-user-plus"></i> Add Employee
                            </button>
                            <button class="btn btn-success-custom btn-custom" data-bs-toggle="modal" data-bs-target="#bulkEmployeeModal">
                                <i class="fas fa-upload"></i> Bulk Add
                            </button>
                            <a href="{{ url_for('download_employee_template') }}" class="btn btn-warning-custom btn-custom">
                                <i class="fas fa-download"></i> Template
                            </a>
                        </div>

                        <!-- Recent Employees -->
                        <div class="table-responsive">
                            <table class="table table-hover">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>Name</th>
                                        <th>CTC</th>
                                        <th>Department</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for emp in employees[:5] %}
                                    <tr>
                                        <td>{{ emp.emp_id }}</td>
                                        <td>{{ emp.name }}</td>
                                        <td>₹{{ "%.0f"|format(emp.ctc_monthly) }}</td>
                                        <td>{{ emp.department or 'N/A' }}</td>
                                        <td>
                                            <button class="btn btn-sm btn-info-custom" onclick="viewEmployeeCostBreakdown('{{ emp.emp_id }}', '{{ emp.name }}', {{ emp.ctc_monthly }})">
                                                <i class="fas fa-calculator"></i> View
                                            </button>
                                        </td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- Payroll Management -->
                <div class="col-lg-6">
                    <div class="section-card">
                        <h3 class="section-title"><i class="fas fa-calculator"></i> Payroll Management</h3>
                        
                        <!-- Process Payroll -->
                        <div class="mb-4">
                            <button class="btn btn-primary-custom btn-custom" data-bs-toggle="modal" data-bs-target="#processPayrollModal">
                                <i class="fas fa-calculator"></i> Process Payroll
                            </button>
                            <button class="btn btn-success-custom btn-custom" data-bs-toggle="modal" data-bs-target="#bulkPayrollModal">
                                <i class="fas fa-upload"></i> Bulk Process
                            </button>
                            <a href="{{ url_for('download_payroll_template') }}" class="btn btn-warning-custom btn-custom">
                                <i class="fas fa-download"></i> Template
                            </a>
                        </div>

                        <!-- Recent Payroll -->
                        <div class="table-responsive">
                            <table class="table table-hover">
                                <thead>
                                    <tr>
                                        <th>Employee</th>
                                        <th>Month</th>
                                        <th>Net Salary</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for payroll in recent_payroll %}
                                    <tr>
                                        <td>{{ payroll.name }}</td>
                                        <td>{{ payroll.month }} {{ payroll.year }}</td>
                                        <td>₹{{ "%.0f"|format(payroll.net_salary) }}</td>
                                        <td>
                                            <button class="btn btn-sm btn-primary-custom" onclick="viewPayslip('{{ payroll.emp_id }}', '{{ payroll.month }}', {{ payroll.year }})">
                                                <i class="fas fa-eye"></i> View
                                            </button>
                                            <a href="/download_payslip/{{ payroll.emp_id }}/{{ payroll.month }}/{{ payroll.year }}" class="btn btn-sm btn-success-custom">
                                                <i class="fas fa-download"></i> PDF
                                            </a>
                                        </td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Enhanced Payroll Management -->
            <div class="row">
                <div class="col-lg-12">
                    <div class="section-card">
                        <h3 class="section-title"><i class="fas fa-file-invoice-dollar"></i> All Payroll Records</h3>
                        
                        <!-- Filter Options -->
                        <div class="row mb-4">
                            <div class="col-md-3">
                                <select class="form-select" id="monthFilter">
                                    <option value="">All Months</option>
                                    <option value="January">January</option>
                                    <option value="February">February</option>
                                    <option value="March">March</option>
                                    <option value="April">April</option>
                                    <option value="May">May</option>
                                    <option value="June">June</option>
                                    <option value="July">July</option>
                                    <option value="August">August</option>
                                    <option value="September">September</option>
                                    <option value="October">October</option>
                                    <option value="November">November</option>
                                    <option value="December">December</option>
                                </select>
                            </div>
                            <div class="col-md-3">
                                <select class="form-select" id="yearFilter">
                                    <option value="">All Years</option>
                                    <option value="2024">2024</option>
                                    <option value="2023">2023</option>
                                    <option value="2025">2025</option>
                                </select>
                            </div>
                            <div class="col-md-6 text-end">
                                <button class="btn btn-primary-custom btn-custom" onclick="loadAllPayrolls()">
                                    <i class="fas fa-sync-alt"></i> Refresh
                                </button>
                                <button class="btn btn-success-custom btn-custom" data-bs-toggle="modal" data-bs-target="#emailModal">
                                    <i class="fas fa-paper-plane"></i> Send Payslips
                                </button>
                                <button class="btn btn-warning-custom btn-custom" onclick="downloadReport()">
                                    <i class="fas fa-file-excel"></i> Download Report
                                </button>
                            </div>
                        </div>

                        <!-- All Payroll Records Table -->
                        <div class="table-responsive" id="allPayrollTable">
                            <table class="table table-hover">
                                <thead>
                                    <tr>
                                        <th>Employee ID</th>
                                        <th>Name</th>
                                        <th>Month/Year</th>
                                        <th>Days Worked</th>
                                        <th>Gross Salary</th>
                                        <th>Net Salary</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="payrollTableBody">
                                    {% for payroll in all_payroll %}
                                    <tr>
                                        <td>{{ payroll.emp_id }}</td>
                                        <td>{{ payroll.name }}</td>
                                        <td>{{ payroll.month }} {{ payroll.year }}</td>
                                        <td>{{ payroll.days_worked }} days</td>
                                        <td>₹{{ "%.2f"|format(payroll.gross_salary) }}</td>
                                        <td>₹{{ "%.2f"|format(payroll.net_salary) }}</td>
                                        <td>
                                            <button class="btn btn-sm btn-primary-custom" onclick="viewPayslip('{{ payroll.emp_id }}', '{{ payroll.month }}', {{ payroll.year }})">
                                                <i class="fas fa-eye"></i> View
                                            </button>
                                            <a href="/download_payslip/{{ payroll.emp_id }}/{{ payroll.month }}/{{ payroll.year }}" class="btn btn-sm btn-success-custom">
                                                <i class="fas fa-download"></i> PDF
                                            </a>
                                        </td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Additional Actions -->
            <div class="row">
                <div class="col-lg-6">
                    <div class="section-card">
                        <h3 class="section-title"><i class="fas fa-arrow-up"></i> Salary Hike Management</h3>
                        <button class="btn btn-primary-custom btn-custom" data-bs-toggle="modal" data-bs-target="#hikeModal">
                            <i class="fas fa-arrow-up"></i> Apply Hike
                        </button>
                        <p class="mt-2 text-muted">Select employee and apply salary hike during payroll processing</p>
                    </div>
                </div>
                <div class="col-lg-6">
                    <div class="section-card">
                        <h3 class="section-title"><i class="fas fa-users"></i> Employee Overview</h3>
                        <button class="btn btn-warning-custom btn-custom" data-bs-toggle="modal" data-bs-target="#allEmployeesModal">
                            <i class="fas fa-list"></i> View All Employees
                        </button>
                        <p class="mt-2 text-muted">View complete employee list with details and salary information</p>
                    </div>
                </div>
            </div>

            <!-- Charts -->
            <div class="row">
                <div class="col-12">
                    <div class="section-card">
                        <h3 class="section-title"><i class="fas fa-chart-bar"></i> Monthly Payroll Analytics</h3>
                        <div class="chart-container">
                            <canvas id="payrollChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Modals -->
    
    <!-- Add Employee Modal -->
    <div class="modal fade" id="addEmployeeModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-user-plus"></i> Add Employee</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <form method="POST" action="{{ url_for('add_employee') }}">
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="emp_id" class="form-label">Employee ID</label>
                                    <input type="text" class="form-control" name="emp_id" required>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="name" class="form-label">Full Name</label>
                                    <input type="text" class="form-control" name="name" required>
                                </div>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="email" class="form-label">Email Address</label>
                                    <input type="email" class="form-control" name="email" required>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="designation" class="form-label">Designation</label>
                                    <input type="text" class="form-control" name="designation">
                                </div>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="department" class="form-label">Department</label>
                                    <input type="text" class="form-control" name="department">
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="joining_date" class="form-label">Joining Date</label>
                                    <input type="date" class="form-control" name="joining_date">
                                </div>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="ctc_monthly" class="form-label">Monthly CTC (₹)</label>
                                    <input type="number" class="form-control" name="ctc_monthly" step="0.01" required>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label class="form-label">PF Opted</label>
                                    <div class="form-check mt-2">
                                        <input class="form-check-input" type="checkbox" name="pf_opted" checked>
                                        <label class="form-check-label">Employee opts for Provident Fund</label>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="submit" class="btn btn-primary-custom">Add Employee</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- Bulk Add Employee Modal -->
    <div class="modal fade" id="bulkEmployeeModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-upload"></i> Bulk Add Employees</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <form method="POST" action="{{ url_for('bulk_add_employees') }}" enctype="multipart/form-data">
                    <div class="modal-body">
                        <div class="file-upload-area">
                            <i class="fas fa-cloud-upload-alt fa-3x mb-3 text-muted"></i>
                            <h5>Upload Employee Excel File</h5>
                            <p class="text-muted">Select your filled employee template file</p>
                            <input type="file" class="form-control" name="file" accept=".xlsx,.xls" required>
                        </div>
                        <div class="mt-3">
                            <small class="text-muted">
                                <strong>Template Format:</strong> emp_id, name, email, designation, department, joining_date, ctc_monthly, pf_opted
                            </small>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="submit" class="btn btn-success-custom">Upload & Process</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- Process Payroll Modal -->
    <div class="modal fade" id="processPayrollModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-calculator"></i> Process Individual Payroll</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <form method="POST" action="{{ url_for('process_individual_payroll') }}">
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="emp_id_select" class="form-label">Select Employee</label>
                                    <select class="form-select" name="emp_id" required>
                                        <option value="">Choose Employee...</option>
                                        {% for emp in employees %}
                                        <option value="{{ emp.emp_id }}">{{ emp.emp_id }} - {{ emp.name }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="days_worked" class="form-label">Days Worked</label>
                                    <input type="number" class="form-control" name="days_worked" value="30" min="1" max="31" required>
                                </div>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="month" class="form-label">Month</label>
                                    <select class="form-select" name="month" required>
                                        <option value="January">January</option>
                                        <option value="February">February</option>
                                        <option value="March">March</option>
                                        <option value="April">April</option>
                                        <option value="May">May</option>
                                        <option value="June">June</option>
                                        <option value="July">July</option>
                                        <option value="August">August</option>
                                        <option value="September">September</option>
                                        <option value="October">October</option>
                                        <option value="November">November</option>
                                        <option value="December">December</option>
                                    </select>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="year" class="form-label">Year</label>
                                    <input type="number" class="form-control" name="year" value="2024" min="2020" max="2030" required>
                                </div>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label class="form-label">PF Opted</label>
                                    <div class="form-check mt-2">
                                        <input class="form-check-input" type="checkbox" name="pf_opted" checked>
                                        <label class="form-check-label">Employee opts for PF deduction</label>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="hike_amount" class="form-label">Hike Amount (₹)</label>
                                    <input type="number" class="form-control" name="hike_amount" value="0" step="0.01">
                                    <small class="text-muted">Optional: Add hike to monthly CTC</small>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="submit" class="btn btn-primary-custom">Process Payroll</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- Bulk Process Payroll Modal -->
    <div class="modal fade" id="bulkPayrollModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-upload"></i> Bulk Process Payroll</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <form method="POST" action="{{ url_for('bulk_process_payroll') }}" enctype="multipart/form-data">
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="month" class="form-label">Month</label>
                                    <select class="form-select" name="month" required>
                                        <option value="January">January</option>
                                        <option value="February">February</option>
                                        <option value="March">March</option>
                                        <option value="April">April</option>
                                        <option value="May">May</option>
                                        <option value="June">June</option>
                                        <option value="July">July</option>
                                        <option value="August">August</option>
                                        <option value="September">September</option>
                                        <option value="October">October</option>
                                        <option value="November">November</option>
                                        <option value="December">December</option>
                                    </select>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="year" class="form-label">Year</label>
                                    <input type="number" class="form-control" name="year" value="2024" min="2020" max="2030" required>
                                </div>
                            </div>
                        </div>
                        <div class="file-upload-area">
                            <i class="fas fa-cloud-upload-alt fa-3x mb-3 text-muted"></i>
                            <h5>Upload Payroll Excel File</h5>
                            <p class="text-muted">Select your filled payroll template file</p>
                            <input type="file" class="form-control" name="file" accept=".xlsx,.xls" required>
                        </div>
                        <div class="mt-3">
                            <small class="text-muted">
                                <strong>Template Format:</strong> emp_id, name, days_worked, pf_opted
                            </small>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="submit" class="btn btn-success-custom">Upload & Process</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- Salary Hike Modal -->
    <div class="modal fade" id="hikeModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-arrow-up"></i> Apply Salary Hike</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <form method="POST" action="{{ url_for('apply_hike') }}">
                    <div class="modal-body">
                        <div class="mb-3">
                            <label for="hike_emp_id" class="form-label">Select Employee</label>
                            <select class="form-select" name="emp_id" required>
                                <option value="">Choose Employee...</option>
                                {% for emp in employees %}
                                <option value="{{ emp.emp_id }}">{{ emp.emp_id }} - {{ emp.name }} (Current: ₹{{ "%.0f"|format(emp.ctc_monthly) }})</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="mb-3">
                            <label for="hike_amount" class="form-label">Hike Amount (₹)</label>
                            <input type="number" class="form-control" name="hike_amount" step="0.01" required>
                            <small class="text-muted">This amount will be added to the current monthly CTC</small>
                        </div>
                        <div class="mb-3">
                            <label for="hike_reason" class="form-label">Reason for Hike</label>
                            <textarea class="form-control" name="hike_reason" rows="3" placeholder="Performance increment, promotion, etc."></textarea>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="submit" class="btn btn-primary-custom">Apply Hike</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- Email Modal -->
    <div class="modal fade" id="emailModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-envelope"></i> Send Payslips</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <form method="POST" action="{{ url_for('send_payslips') }}">
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="email_month" class="form-label">Month</label>
                                    <select class="form-select" name="month" required>
                                        <option value="January">January</option>
                                        <option value="February">February</option>
                                        <option value="March">March</option>
                                        <option value="April">April</option>
                                        <option value="May">May</option>
                                        <option value="June">June</option>
                                        <option value="July">July</option>
                                        <option value="August">August</option>
                                        <option value="September">September</option>
                                        <option value="October">October</option>
                                        <option value="November">November</option>
                                        <option value="December">December</option>
                                    </select>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="email_year" class="form-label">Year</label>
                                    <input type="number" class="form-control" name="year" value="2024" min="2020" max="2030" required>
                                </div>
                            </div>
                        </div>
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle"></i> 
                            This will send payslips to all employees who have processed payroll for the selected month/year.
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="submit" class="btn btn-success-custom">Send Payslips</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- Payslip View Modal -->
    <div class="modal fade" id="payslipModal" tabindex="-1">
        <div class="modal-dialog modal-xl">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-file-invoice-dollar"></i> Payslip Details</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" id="payslipContent">
                    <!-- Payslip content will be loaded here -->
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    <button type="button" class="btn btn-success-custom" id="downloadPayslipBtn">
                        <i class="fas fa-download"></i> Download PDF
                    </button>
                </div>
            </div>
        </div>
    </div>

    <!-- All Employees Modal -->
    <div class="modal fade" id="allEmployeesModal" tabindex="-1">
        <div class="modal-dialog modal-xl">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-users"></i> All Employees</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="table-responsive">
                        <table class="table table-hover">
                            <thead>
                                <tr>
                                    <th>Employee ID</th>
                                    <th>Name</th>
                                    <th>Email</th>
                                    <th>Designation</th>
                                    <th>Department</th>
                                    <th>Monthly CTC</th>
                                    <th>PF Opted</th>
                                    <th>Joining Date</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for emp in employees %}
                                <tr>
                                    <td>{{ emp.emp_id }}</td>
                                    <td>{{ emp.name }}</td>
                                    <td>{{ emp.email }}</td>
                                    <td>{{ emp.designation or 'N/A' }}</td>
                                    <td>{{ emp.department or 'N/A' }}</td>
                                    <td>₹{{ "%.2f"|format(emp.ctc_monthly) }}</td>
                                    <td>
                                        {% if emp.pf_opted %}
                                            <span class="badge bg-success">Yes</span>
                                        {% else %}
                                            <span class="badge bg-danger">No</span>
                                        {% endif %}
                                    </td>
                                    <td>{{ emp.joining_date or 'N/A' }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Employee Cost Breakdown Modal -->
    <div class="modal fade" id="employeeCostModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-calculator"></i> Employee Cost Breakdown</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" id="employeeCostContent">
                    <!-- Cost breakdown content will be loaded here -->
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    
    <script>
        // Chart.js for payroll analytics
        document.addEventListener('DOMContentLoaded', function() {
            const ctx = document.getElementById('payrollChart').getContext('2d');
            
            // Sample data - this would come from the backend in a real application
            const monthlyData = {{ monthly_stats|tojson }};
            const labels = [];
            const data = [];
            
            monthlyData.forEach(function(item) {
                labels.push(item.month + ' ' + item.year);
                data.push(item.total_payout || 0);
            });
            
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels.reverse(),
                    datasets: [{
                        label: 'Monthly Payout (₹)',
                        data: data.reverse(),
                        backgroundColor: 'rgba(52, 152, 219, 0.8)',
                        borderColor: 'rgba(52, 152, 219, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return '₹' + value.toLocaleString();
                                }
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top'
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return 'Total Payout: ₹' + context.parsed.y.toLocaleString();
                                }
                            }
                        }
                    }
                }
            });
        });

        // Auto-dismiss alerts after 5 seconds
        setTimeout(function() {
            const alerts = document.querySelectorAll('.alert');
            alerts.forEach(function(alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            });
        }, 5000);

        // View payslip function
        function viewPayslip(empId, month, year) {
            fetch(`/api/payslip/${empId}/${month}/${year}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('payslipContent').innerHTML = data.html;
                        document.getElementById('downloadPayslipBtn').onclick = function() {
                            window.open(`/download_payslip/${empId}/${month}/${year}`, '_blank');
                        };
                        new bootstrap.Modal(document.getElementById('payslipModal')).show();
                    } else {
                        alert('Error loading payslip: ' + data.message);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Error loading payslip');
                });
        }

        // Load all payrolls with filtering
        function loadAllPayrolls() {
            const month = document.getElementById('monthFilter').value;
            const year = document.getElementById('yearFilter').value;
            
            let url = '/api/payrolls';
            const params = new URLSearchParams();
            if (month) params.append('month', month);
            if (year) params.append('year', year);
            if (params.toString()) url += '?' + params.toString();
            
            fetch(url)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updatePayrollTable(data.payrolls);
                    } else {
                        alert('Error loading payrolls: ' + data.message);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Error loading payrolls');
                });
        }

        function updatePayrollTable(payrolls) {
            const tbody = document.getElementById('payrollTableBody');
            tbody.innerHTML = '';
            
            payrolls.forEach(payroll => {
                const row = `
                    <tr>
                        <td>${payroll.emp_id}</td>
                        <td>${payroll.name}</td>
                        <td>${payroll.month} ${payroll.year}</td>
                        <td>${payroll.days_worked} days</td>
                        <td>₹${parseFloat(payroll.gross_salary).toFixed(2)}</td>
                        <td>₹${parseFloat(payroll.net_salary).toFixed(2)}</td>
                        <td>
                            <button class="btn btn-sm btn-primary-custom" onclick="viewPayslip('${payroll.emp_id}', '${payroll.month}', ${payroll.year})">
                                <i class="fas fa-eye"></i> View
                            </button>
                            <a href="/download_payslip/${payroll.emp_id}/${payroll.month}/${payroll.year}" class="btn btn-sm btn-success-custom">
                                <i class="fas fa-download"></i> PDF
                            </a>
                        </td>
                    </tr>
                `;
                tbody.innerHTML += row;
            });
        }

        // Add event listeners for filters
        document.getElementById('monthFilter').addEventListener('change', loadAllPayrolls);
        document.getElementById('yearFilter').addEventListener('change', loadAllPayrolls);

        // View employee cost breakdown
        function viewEmployeeCostBreakdown(empId, name, ctcMonthly) {
            const breakdown = calculateSalaryBreakdown(ctcMonthly);
            
            const costHtml = `
                <div class="cost-breakdown-container">
                    <div class="employee-header" style="text-align: center; margin-bottom: 30px; padding: 20px; background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%); color: white; border-radius: 8px;">
                        <h3 style="margin: 0;">${name} (${empId})</h3>
                        <p style="margin: 5px 0 0 0; opacity: 0.9;">Monthly CTC: ₹${ctcMonthly.toFixed(2)}</p>
                    </div>
                    
                    <div class="cost-table" style="background: white; border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
                        <div class="section-header" style="background: #2c3e50; color: white; padding: 15px; text-align: center;">
                            <h4 style="margin: 0;">SALARY STRUCTURE</h4>
                        </div>
                        
                        <table style="width: 100%; border-collapse: collapse;">
                            <thead>
                                <tr style="background: #3498db; color: white;">
                                    <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">Component</th>
                                    <th style="padding: 12px; text-align: right; border: 1px solid #ddd;">Amount (₹)</th>
                                    <th style="padding: 12px; text-align: right; border: 1px solid #ddd;">Percentage</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr><td style="padding: 10px; border: 1px solid #ddd;">Basic Salary</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">₹${breakdown.basic_salary.toFixed(2)}</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">40%</td></tr>
                                <tr><td style="padding: 10px; border: 1px solid #ddd;">HRA</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">₹${breakdown.hra.toFixed(2)}</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">20%</td></tr>
                                <tr><td style="padding: 10px; border: 1px solid #ddd;">Travel Allowance</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">₹${breakdown.travel_allowance.toFixed(2)}</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">10%</td></tr>
                                <tr><td style="padding: 10px; border: 1px solid #ddd;">Medical Allowance</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">₹${breakdown.medical_allowance.toFixed(2)}</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">5%</td></tr>
                                <tr><td style="padding: 10px; border: 1px solid #ddd;">LTA</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">₹${breakdown.lta.toFixed(2)}</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">8%</td></tr>
                                <tr><td style="padding: 10px; border: 1px solid #ddd;">Special Allowance</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">₹${breakdown.special_allowance.toFixed(2)}</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">17%</td></tr>
                                <tr style="background: #e8f5e8; font-weight: bold;"><td style="padding: 12px; border: 1px solid #ddd;">GROSS SALARY</td><td style="padding: 12px; text-align: right; border: 1px solid #ddd;">₹${breakdown.gross_salary.toFixed(2)}</td><td style="padding: 12px; text-align: right; border: 1px solid #ddd;">100%</td></tr>
                                <tr><td style="padding: 10px; border: 1px solid #ddd; color: #e74c3c; font-weight: bold;">Potential Deductions:</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;"></td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;"></td></tr>
                                <tr><td style="padding: 10px; border: 1px solid #ddd; padding-left: 30px;">PF Contribution (12%)</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd; color: #e74c3c;">₹${breakdown.pf_deduction.toFixed(2)}</td><td style="padding: 10px; text-align: right; border: 1px solid #ddd;">-12%</td></tr>
                                <tr style="background: #2c3e50; color: white; font-weight: bold; font-size: 1.1em;"><td style="padding: 15px; border: 1px solid #ddd;">POTENTIAL NET SALARY</td><td style="padding: 15px; text-align: right; border: 1px solid #ddd;">₹${breakdown.net_salary.toFixed(2)}</td><td style="padding: 15px; text-align: right; border: 1px solid #ddd;">88%</td></tr>
                            </tbody>
                        </table>
                    </div>
                    
                    <div style="margin-top: 20px; padding: 15px; background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px;">
                        <i class="fas fa-info-circle"></i> <strong>Note:</strong> This is the salary structure breakdown. Actual deductions may vary based on PF opt-in, attendance, and other factors.
                    </div>
                </div>
            `;
            
            document.getElementById('employeeCostContent').innerHTML = costHtml;
            new bootstrap.Modal(document.getElementById('employeeCostModal')).show();
        }

        // Download report function
        function downloadReport() {
            const month = document.getElementById('monthFilter').value;
            const year = document.getElementById('yearFilter').value;
            
            if (!month || !year) {
                alert('Please select both month and year to download report');
                return;
            }
            
            window.open(`/download_report/${month}/${year}`, '_blank');
        }

        // Helper function to calculate salary breakdown
        function calculateSalaryBreakdown(ctcMonthly) {
            const basic_salary = ctcMonthly * 0.40;
            const hra = ctcMonthly * 0.20;
            const travel_allowance = ctcMonthly * 0.10;
            const medical_allowance = ctcMonthly * 0.05;
            const lta = ctcMonthly * 0.08;
            const special_allowance = ctcMonthly * 0.17;
            const gross_salary = basic_salary + hra + travel_allowance + medical_allowance + lta + special_allowance;
            const pf_deduction = basic_salary * 0.12;
            const net_salary = gross_salary - pf_deduction;
            
            return {
                basic_salary,
                hra,
                travel_allowance,
                medical_allowance,
                lta,
                special_allowance,
                gross_salary,
                pf_deduction,
                net_salary
            };
        }
    </script>
</body>
</html>
"""

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
    
    return render_template_string(HTML_TEMPLATE, 
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
    
    return render_template_string(LOGIN_TEMPLATE)
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PayrollPro - Login</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            display: flex;
        }
        
        .auth-container {
            display: flex;
            width: 100%;
            min-height: 100vh;
        }
        
        .auth-left {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            background: white;
            padding: 60px 40px;
        }
        
        .auth-right {
            flex: 1;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            padding: 60px 40px;
            text-align: center;
        }
        
        .auth-form {
            width: 100%;
            max-width: 400px;
        }
        
        .brand {
            display: flex;
            align-items: center;
            margin-bottom: 30px;
            color: #667eea;
            font-size: 1.8rem;
            font-weight: 600;
        }
        
        .brand i {
            margin-right: 12px;
            font-size: 2rem;
        }
        
        .welcome-title {
            color: #2c3e50;
            font-size: 1.8rem;
            font-weight: 600;
            margin-bottom: 10px;
        }
        
        .welcome-subtitle {
            color: #6c757d;
            margin-bottom: 30px;
        }
        
        .form-control {
            border-radius: 10px;
            border: 2px solid #e9ecef;
            padding: 15px 20px;
            font-size: 1rem;
            transition: all 0.3s ease;
        }
        
        .form-control:focus {
            border-color: #667eea;
            box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
        }
        
        .input-group-text {
            border-radius: 10px 0 0 10px;
            border: 2px solid #e9ecef;
            border-right: none;
            background: #f8f9fa;
            color: #6c757d;
        }
        
        .input-group .form-control {
            border-left: none;
            border-radius: 0 10px 10px 0;
        }
        
        .btn-login {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            border-radius: 10px;
            padding: 15px;
            font-size: 1.1rem;
            font-weight: 600;
            color: white;
            width: 100%;
            transition: all 0.3s ease;
            margin-bottom: 20px;
        }
        
        .btn-login:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
            color: white;
        }
        
        .alert {
            border-radius: 10px;
            border: none;
            margin-bottom: 20px;
        }
        
        .credentials-info {
            background: #f0f3ff;
            border-radius: 10px;
            padding: 20px;
            margin-top: 30px;
            border-left: 4px solid #667eea;
        }
        
        .credentials-info h6 {
            color: #2c3e50;
            font-weight: 600;
            margin-bottom: 15px;
        }
        
        .credential-item {
            background: white;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
            border: 1px solid #dee2e6;
        }
        
        .credential-item:last-child {
            margin-bottom: 0;
        }
        
        .brand-logo {
            font-size: 2.5rem;
            margin-bottom: 20px;
        }
        
        .brand-title {
            font-size: 2rem;
            font-weight: 300;
            margin-bottom: 15px;
        }
        
        .brand-subtitle {
            opacity: 0.9;
            font-size: 1.1rem;
            line-height: 1.6;
            margin-bottom: 20px;
        }
        
        @media (max-width: 768px) {
            .auth-container {
                flex-direction: column;
            }
            .auth-right {
                display: none;
            }
            .auth-left {
                padding: 40px 30px;
            }
            .brand-title {
                font-size: 1.5rem;
            }
            .brand-subtitle {
                font-size: 1rem;
            }
        }
    </style>
</head>
<body>
    <div class="auth-container">
        <!-- Left Side - Login Form -->
        <div class="auth-left">
            <div class="auth-form">
                <div class="brand">
                    <i class="fas fa-calculator"></i>
                    PayrollPro
                </div>
                
                <!-- Flash Messages -->
                <!-- {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        {% for category, message in messages %}
                            <div class="alert alert-{{ 'danger' if category == 'error' else 'success' }} alert-dismissible fade show" role="alert">
                                {{ message }}
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %} -->
                
                <h2 class="welcome-title">Welcome Back</h2>
                <p class="welcome-subtitle">Sign in to continue to your account</p>
                
                <form method="POST" action="{{ url_for('login') }}">
                    <div class="mb-3">
                        <label for="email" class="form-label">Email Address</label>
                        <div class="input-group">
                            <span class="input-group-text">
                                <i class="fas fa-envelope"></i>
                            </span>
                            <input type="email" class="form-control" id="email" name="email" 
                                   placeholder="Enter your email" required>
                        </div>
                    </div>
                    
                    <div class="mb-4">
                        <label for="password" class="form-label">Password</label>
                        <div class="input-group">
                            <span class="input-group-text">
                                <i class="fas fa-lock"></i>
                            </span>
                            <input type="password" class="form-control" id="password" name="password" 
                                   placeholder="Enter your password" required>
                        </div>
                    </div>
                    
                    <button type="submit" class="btn btn-login">
                        <i class="fas fa-sign-in-alt me-2"></i>
                        Sign In
                    </button>
                </form>
                
                
            </div>
        </div>
        
        <!-- Right Side - Branding/Info -->
        <div class="auth-right">
            <div>
                <div class="brand-logo">
                    <i class="fas fa-calculator"></i>
                </div>
                <h1 class="brand-title">PayrollPro</h1>
                <p class="brand-subtitle">
                    Modern Payroll Management
                </p>
                <p class="brand-subtitle">
                    Streamline your payroll process with our comprehensive solution featuring real-time calculations, advanced analytics, and seamless document management.
                </p>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)