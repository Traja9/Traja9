import os
import json
import time
import random
import hashlib
import requests
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_cors import CORS

# Configuration
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or hashlib.sha256(str(time.time()).encode()).hexdigest()
    DATABASE_FILE = os.path.join(Path.home(), "skill_match_data.json")
    PAYMENT_LOG = os.path.join(Path.home(), "payment_transactions.json")
    COMMISSION_RATE = 0.10  # 10% platform fee

# Initialize application
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Data storage functions
def load_data():
    """Load database from file"""
    if os.path.exists(Config.DATABASE_FILE):
        with open(Config.DATABASE_FILE, 'r') as f:
            return json.load(f)
    return {"users": [], "jobs": [], "matches": []}

def save_data(data):
    """Save database to file"""
    with open(Config.DATABASE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def log_payment(transaction):
    """Log payment transaction"""
    if os.path.exists(Config.PAYMENT_LOG):
        with open(Config.PAYMENT_LOG, 'r') as f:
            transactions = json.load(f)
    else:
        transactions = []
    
    transactions.append(transaction)
    
    with open(Config.PAYMENT_LOG, 'w') as f:
        json.dump(transactions, f, indent=2)

# User management functions
def create_user(username, password, user_type, skills=None, hourly_rate=None):
    """Create a new user"""
    data = load_data()
    
    # Check if username already exists
    if any(user["username"] == username for user in data["users"]):
        return False, "Username already exists"
    
    user_id = len(data["users"]) + 1
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    new_user = {
        "id": user_id,
        "username": username,
        "password_hash": hashed_password,
        "user_type": user_type,
        "created_at": datetime.now().isoformat(),
        "balance": 0.0,
        "rating": 0,
        "completed_jobs": 0
    }
    
    if user_type == "freelancer":
        new_user["skills"] = skills or []
        new_user["hourly_rate"] = hourly_rate or 0
    
    data["users"].append(new_user)
    save_data(data)
    return True, user_id

def find_user(username, password=None):
    """Find user by username and optionally validate password"""
    data = load_data()
    
    for user in data["users"]:
        if user["username"] == username:
            if password:
                hashed_password = hashlib.sha256(password.encode()).hexdigest()
                if user["password_hash"] == hashed_password:
                    return user
                return None
            return user
    
    return None

def update_user_balance(user_id, amount):
    """Update user balance"""
    data = load_data()
    
    for user in data["users"]:
        if user["id"] == user_id:
            user["balance"] += amount
            save_data(data)
            return True, user["balance"]
    
    return False, "User not found"

# Job management functions
def create_job(client_id, title, description, skills_required, budget, deadline):
    """Create a new job posting"""
    data = load_data()
    
    job_id = len(data["jobs"]) + 1
    
    new_job = {
        "id": job_id,
        "client_id": client_id,
        "title": title,
        "description": description,
        "skills_required": skills_required,
        "budget": budget,
        "deadline": deadline,
        "status": "open",
        "created_at": datetime.now().isoformat(),
        "applications": []
    }
    
    data["jobs"].append(new_job)
    save_data(data)
    return job_id

def apply_for_job(job_id, freelancer_id, proposal, bid_amount):
    """Apply for a job"""
    data = load_data()
    
    for job in data["jobs"]:
        if job["id"] == job_id:
            application = {
                "freelancer_id": freelancer_id,
                "proposal": proposal,
                "bid_amount": bid_amount,
                "status": "pending",
                "submitted_at": datetime.now().isoformat()
            }
            job["applications"].append(application)
            save_data(data)
            return True
    
    return False

def award_job(job_id, freelancer_id):
    """Award job to a freelancer"""
    data = load_data()
    
    for job in data["jobs"]:
        if job["id"] == job_id:
            job["status"] = "awarded"
            job["awarded_to"] = freelancer_id
            job["awarded_at"] = datetime.now().isoformat()
            
            for application in job["applications"]:
                if application["freelancer_id"] == freelancer_id:
                    application["status"] = "accepted"
                else:
                    application["status"] = "rejected"
            
            save_data(data)
            return True
    
    return False

def complete_job(job_id, rating):
    """Mark job as complete and process payment"""
    data = load_data()
    
    for job in data["jobs"]:
        if job["id"] == job_id and job["status"] == "awarded":
            # Update job status
            job["status"] = "completed"
            job["completed_at"] = datetime.now().isoformat()
            job["rating"] = rating
            
            # Find client and freelancer
            client = next((u for u in data["users"] if u["id"] == job["client_id"]), None)
            freelancer = next((u for u in data["users"] if u["id"] == job["awarded_to"]), None)
            
            if client and freelancer:
                # Get the accepted bid amount
                accepted_bid = next((a["bid_amount"] for a in job["applications"] 
                                   if a["freelancer_id"] == freelancer["id"] and a["status"] == "accepted"), job["budget"])
                
                # Calculate platform fee
                platform_fee = accepted_bid * Config.COMMISSION_RATE
                freelancer_payment = accepted_bid - platform_fee
                
                # Update balances
                update_user_balance(freelancer["id"], freelancer_payment)
                
                # Update freelancer stats
                freelancer["completed_jobs"] += 1
                new_rating = ((freelancer["rating"] * (freelancer["completed_jobs"] - 1)) + rating) / freelancer["completed_jobs"]
                freelancer["rating"] = round(new_rating, 1)
                
                # Log transaction
                transaction = {
                    "job_id": job_id,
                    "client_id": client["id"],
                    "freelancer_id": freelancer["id"],
                    "amount": accepted_bid,
                    "platform_fee": platform_fee,
                    "freelancer_payment": freelancer_payment,
                    "timestamp": datetime.now().isoformat()
                }
                log_payment(transaction)
                
                save_data(data)
                return True, transaction
    
    return False, "Job not found or not in awarded status"

def search_freelancers(skills=None, max_rate=None, min_rating=None):
    """Search for freelancers based on criteria"""
    data = load_data()
    results = []
    
    for user in data["users"]:
        if user["user_type"] != "freelancer":
            continue
            
        matches = True
        
        if skills and not any(skill in user.get("skills", []) for skill in skills):
            matches = False
            
        if max_rate is not None and user.get("hourly_rate", 0) > max_rate:
            matches = False
            
        if min_rating is not None and user.get("rating", 0) < min_rating:
            matches = False
            
        if matches:
            results.append(user)
    
    return results

def search_jobs(skills=None, min_budget=None, status="open"):
    """Search for jobs based on criteria"""
    data = load_data()
    results = []
    
    for job in data["jobs"]:
        if job["status"] != status:
            continue
            
        matches = True
        
        if skills and not any(skill in job.get("skills_required", []) for skill in skills):
            matches = False
            
        if min_budget is not None and job.get("budget", 0) < min_budget:
            matches = False
            
        if matches:
            results.append(job)
    
    return results

# Withdrawal system
def request_withdrawal(user_id, amount, payment_method, payment_details):
    """Request withdrawal of funds"""
    data = load_data()
    
    for user in data["users"]:
        if user["id"] == user_id:
            if user["balance"] < amount:
                return False, "Insufficient balance"
            
            if not hasattr(data, "withdrawals"):
                data["withdrawals"] = []
            
            withdrawal_id = len(data.get("withdrawals", [])) + 1
            
            withdrawal = {
                "id": withdrawal_id,
                "user_id": user_id,
                "amount": amount,
                "payment_method": payment_method,
                "payment_details": payment_details,
                "status": "pending",
                "requested_at": datetime.now().isoformat()
            }
            
            if "withdrawals" not in data:
                data["withdrawals"] = []
                
            data["withdrawals"].append(withdrawal)
            
            # Deduct from user balance
            user["balance"] -= amount
            
            save_data(data)
            return True, withdrawal_id
    
    return False, "User not found"

# API Routes
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    success, result = create_user(
        data.get('username'),
        data.get('password'),
        data.get('user_type'),
        data.get('skills'),
        data.get('hourly_rate')
    )
    
    if success:
        return jsonify({"success": True, "user_id": result}), 201
    else:
        return jsonify({"success": False, "error": result}), 400

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = find_user(data.get('username'), data.get('password'))
    
    if user:
        session['user_id'] = user['id']
        return jsonify({"success": True, "user": {k: v for k, v in user.items() if k != 'password_hash'}}), 200
    else:
        return jsonify({"success": False, "error": "Invalid credentials"}), 401

@app.route('/api/jobs', methods=['POST'])
def post_job():
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401
    
    data = request.json
    job_id = create_job(
        session['user_id'],
        data.get('title'),
        data.get('description'),
        data.get('skills_required'),
        data.get('budget'),
        data.get('deadline')
    )
    
    return jsonify({"success": True, "job_id": job_id}), 201

@app.route('/api/jobs/search', methods=['GET'])
def search_jobs_api():
    skills = request.args.get('skills', '').split(',') if request.args.get('skills') else None
    min_budget = float(request.args.get('min_budget')) if request.args.get('min_budget') else None
    status = request.args.get('status', 'open')
    
    results = search_jobs(skills, min_budget, status)
    return jsonify({"success": True, "jobs": results}), 200

@app.route('/api/freelancers/search', methods=['GET'])
def search_freelancers_api():
    skills = request.args.get('skills', '').split(',') if request.args.get('skills') else None
    max_rate = float(request.args.get('max_rate')) if request.args.get('max_rate') else None
    min_rating = float(request.args.get('min_rating')) if request.args.get('min_rating') else None
    
    results = search_freelancers(skills, max_rate, min_rating)
    return jsonify({"success": True, "freelancers": results}), 200

@app.route('/api/jobs/<int:job_id>/apply', methods=['POST'])
def apply_job_api(job_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401
    
    data = request.json
    success = apply_for_job(
        job_id,
        session['user_id'],
        data.get('proposal'),
        data.get('bid_amount')
    )
    
    if success:
        return jsonify({"success": True}), 200
    else:
        return jsonify({"success": False, "error": "Job not found"}), 404

@app.route('/api/jobs/<int:job_id>/award', methods=['POST'])
def award_job_api(job_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401
    
    data = request.json
    success = award_job(job_id, data.get('freelancer_id'))
    
    if success:
        return jsonify({"success": True}), 200
    else:
        return jsonify({"success": False, "error": "Job not found"}), 404

@app.route('/api/jobs/<int:job_id>/complete', methods=['POST'])
def complete_job_api(job_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401
    
    data = request.json
    success, result = complete_job(job_id, data.get('rating'))
    
    if success:
        return jsonify({"success": True, "transaction": result}), 200
    else:
        return jsonify({"success": False, "error": result}), 400

@app.route('/api/withdraw', methods=['POST'])
def withdraw_api():
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401
    
    data = request.json
    success, result = request_withdrawal(
        session['user_id'],
        data.get('amount'),
        data.get('payment_method'),
        data.get('payment_details')
    )
    
    if success:
        return jsonify({"success": True, "withdrawal_id": result}), 200
    else:
        return jsonify({"success": False, "error": result}), 400

@app.route('/api/earnings', methods=['GET'])
def get_earnings():
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401
    
    data = load_data()
    user = next((u for u in data["users"] if u["id"] == session['user_id']), None)
    
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404
    
    # Calculate total earnings
    if os.path.exists(Config.PAYMENT_LOG):
        with open(Config.PAYMENT_LOG, 'r') as f:
            transactions = json.load(f)
            
        user_transactions = [t for t in transactions if t["freelancer_id"] == user["id"]]
        total_earnings = sum(t["freelancer_payment"] for t in user_transactions)
        
        # Get earnings by month for chart data
        earnings_by_month = {}
        for transaction in user_transactions:
            date = datetime.fromisoformat(transaction["timestamp"])
            month_key = f"{date.year}-{date.month:02d}"
            
            if month_key not in earnings_by_month:
                earnings_by_month[month_key] = 0
                
            earnings_by_month[month_key] += transaction["freelancer_payment"]
            
        return jsonify({
            "success": True, 
            "current_balance": user["balance"],
            "total_earnings": total_earnings,
            "earnings_by_month": earnings_by_month
        }), 200
    else:
        return jsonify({
            "success": True, 
            "current_balance": user["balance"],
            "total_earnings": 0,
            "earnings_by_month": {}
        }), 200

# Web UI routes (simplified)
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    data = load_data()
    user = next((u for u in data["users"] if u["id"] == session['user_id']), None)
    
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('home'))
    
    return render_template('dashboard.html', user=user)

# Admin routes
@app.route('/admin/payments')
def admin_payments():
    # Simple admin check
    if 'user_id' not in session or session['user_id'] != 1:  # Assuming admin has ID 1
        return redirect(url_for('home'))
    
    if os.path.exists(Config.PAYMENT_LOG):
        with open(Config.PAYMENT_LOG, 'r') as f:
            transactions = json.load(f)
    else:
        transactions = []
    
    # Calculate platform earnings
    platform_earnings = sum(t["platform_fee"] for t in transactions)
    
    return render_template('admin_payments.html', 
                          transactions=transactions, 
                          platform_earnings=platform_earnings)

@app.route('/admin/withdrawals')
def admin_withdrawals():
    # Simple admin check
    if 'user_id' not in session or session['user_id'] != 1:  # Assuming admin has ID 1
        return redirect(url_for('home'))
    
    data = load_data()
    withdrawals = data.get("withdrawals", [])
    
    return render_template('admin_withdrawals.html', withdrawals=withdrawals)

@app.route('/admin/withdrawals/<int:withdrawal_id>/process', methods=['POST'])
def process_withdrawal(withdrawal_id):
    # Simple admin check
    if 'user_id' not in session or session['user_id'] != 1:  # Assuming admin has ID 1
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    data = load_data()
    
    for withdrawal in data.get("withdrawals", []):
        if withdrawal["id"] == withdrawal_id:
            withdrawal["status"] = "processed"
            withdrawal["processed_at"] = datetime.now().isoformat()
            withdrawal["processed_by"] = session['user_id']
            
            save_data(data)
            return jsonify({"success": True}), 200
    
    return jsonify({"success": False, "error": "Withdrawal not found"}), 404

# Job listing and management
@app.route('/jobs')
def jobs_page():
    """Render the jobs page with search functionality"""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    data = load_data()
    user = next((u for u in data["users"] if u["id"] == session['user_id']), None)
    
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('home'))
    
    # Get all open jobs
    open_jobs = search_jobs(status="open")
    
    # Get user's jobs based on type
    if user["user_type"] == "client":
        my_jobs = [job for job in data["jobs"] if job["client_id"] == user["id"]]
    else:  # freelancer
        # Get jobs the freelancer has applied to
        my_jobs = []
        for job in data["jobs"]:
            for app in job.get("applications", []):
                if app["freelancer_id"] == user["id"]:
                    job_copy = job.copy()
                    job_copy["my_application"] = app
                    my_jobs.append(job_copy)
                    break
    
    return render_template('jobs.html', 
                          user=user, 
                          open_jobs=open_jobs, 
                          my_jobs=my_jobs)

@app.route('/jobs/<int:job_id>')
def job_details(job_id):
    """Render the job details page"""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    data = load_data()
    user = next((u for u in data["users"] if u["id"] == session['user_id']), None)
    job = next((j for j in data["jobs"] if j["id"] == job_id), None)
    
    if not user or not job:
        return redirect(url_for('jobs_page'))
    
    # Get client info
    client = next((u for u in data["users"] if u["id"] == job["client_id"]), None)
    
    # Check if user has applied
    user_application = None
    if user["user_type"] == "freelancer":
        for app in job.get("applications", []):
            if app["freelancer_id"] == user["id"]:
                user_application = app
                break
    
    # Get freelancer info if job is awarded
    awarded_freelancer = None
    if job.get("awarded_to"):
        awarded_freelancer = next((u for u in data["users"] if u["id"] == job["awarded_to"]), None)
    
    return render_template('job_details.html', 
                          user=user, 
                          job=job, 
                          client=client,
                          user_application=user_application,
                          awarded_freelancer=awarded_freelancer)

# Dashboard functionality
@app.route('/dashboard')
def dashboard_page():
    """Render the user dashboard with relevant stats"""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    data = load_data()
    user = next((u for u in data["users"] if u["id"] == session['user_id']), None)
    
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('home'))
    
    stats = {}
    
    if user["user_type"] == "client":
        # Client stats
        my_jobs = [j for j in data["jobs"] if j["client_id"] == user["id"]]
        stats["total_jobs"] = len(my_jobs)
        stats["active_jobs"] = len([j for j in my_jobs if j["status"] in ["open", "awarded"]])
        stats["completed_jobs"] = len([j for j in my_jobs if j["status"] == "completed"])
        
        # Calculate total spent
        if os.path.exists(Config.PAYMENT_LOG):
            with open(Config.PAYMENT_LOG, 'r') as f:
                transactions = json.load(f)
            
            client_transactions = [t for t in transactions if t["client_id"] == user["id"]]
            stats["total_spent"] = sum(t["amount"] for t in client_transactions)
        else:
            stats["total_spent"] = 0
            
    else:  # freelancer
        # Freelancer stats
        stats["completed_jobs"] = user["completed_jobs"]
        stats["rating"] = user["rating"]
        stats["current_balance"] = user["balance"]
        
        # Get active jobs (applications that are accepted but not completed)
        active_jobs = []
        for job in data["jobs"]:
            if job["status"] == "awarded" and job.get("awarded_to") == user["id"]:
                active_jobs.append(job)
        
        stats["active_jobs"] = len(active_jobs)
        
        # Calculate earnings
        if os.path.exists(Config.PAYMENT_LOG):
            with open(Config.PAYMENT_LOG, 'r') as f:
                transactions = json.load(f)
            
            freelancer_transactions = [t for t in transactions if t["freelancer_id"] == user["id"]]
            stats["total_earnings"] = sum(t["freelancer_payment"] for t in freelancer_transactions)
            
            # Get earnings by month for chart
            earnings_by_month = {}
            for transaction in freelancer_transactions:
                date = datetime.fromisoformat(transaction["timestamp"])
                month_key = f"{date.year}-{date.month:02d}"
                
                if month_key not in earnings_by_month:
                    earnings_by_month[month_key] = 0
                    
                earnings_by_month[month_key] += transaction["freelancer_payment"]
                
            stats["earnings_by_month"] = earnings_by_month
        else:
            stats["total_earnings"] = 0
            stats["earnings_by_month"] = {}
    
    return render_template('dashboard.html', user=user, stats=stats)

# Withdrawal functionality
@app.route('/withdrawal')
def withdrawal_page():
    """Render the withdrawal page"""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    data = load_data()
    user = next((u for u in data["users"] if u["id"] == session['user_id']), None)
    
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('home'))
    
    # Get user's withdrawal history
    withdrawals = [w for w in data.get("withdrawals", []) if w["user_id"] == user["id"]]
    
    return render_template('withdrawal.html', 
                          user=user, 
                          withdrawals=withdrawals)

@app.route('/api/withdraw', methods=['POST'])
def withdraw_funds():
    """API endpoint to process withdrawal requests"""
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401
    
    data = request.json
    
    amount = float(data.get('amount', 0))
    payment_method = data.get('payment_method')
    payment_details = data.get('payment_details')
    
    if not amount or amount <= 0:
        return jsonify({"success": False, "error": "Invalid amount"}), 400
    
    if not payment_method or not payment_details:
        return jsonify({"success": False, "error": "Payment details required"}), 400
    
    success, result = request_withdrawal(
        session['user_id'],
        amount,
        payment_method,
        payment_details
    )
    
    if success:
        return jsonify({"success": True, "withdrawal_id": result}), 200
    else:
        return jsonify({"success": False, "error": result}), 400

# Freelancer search and management
@app.route('/freelancers')
def freelancer_page():
    """Render the freelancer search page"""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    data = load_data()
    user = next((u for u in data["users"] if u["id"] == session['user_id']), None)
    
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('home'))
    
    # Get all freelancers
    freelancers = [u for u in data["users"] if u["user_type"] == "freelancer"]
    
    # Get skill tags for filtering
    all_skills = set()
    for freelancer in freelancers:
        for skill in freelancer.get("skills", []):
            all_skills.add(skill)
    
    return render_template('freelancer.html', 
                          user=user, 
                          freelancers=freelancers,
                          all_skills=sorted(list(all_skills)))

@app.route('/freelancers/<int:freelancer_id>')
def freelancer_profile(freelancer_id):
    """Render the freelancer profile page"""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    data = load_data()
    user = next((u for u in data["users"] if u["id"] == session['user_id']), None)
    freelancer = next((u for u in data["users"] if u["id"] == freelancer_id and u["user_type"] == "freelancer"), None)
    
    if not user or not freelancer:
        return redirect(url_for('freelancer_page'))
    
    # Get freelancer's completed jobs
    completed_jobs = []
    for job in data["jobs"]:
        if job["status"] == "completed" and job.get("awarded_to") == freelancer_id:
            # Get client info
            client = next((u for u in data["users"] if u["id"] == job["client_id"]), None)
            job_copy = job.copy()
            job_copy["client"] = client
            completed_jobs.append(job_copy)
    
    return render_template('freelancer_profile.html', 
                          user=user, 
                          freelancer=freelancer,
                          completed_jobs=completed_jobs)

# Create additional templates routes
@app.route('/create_job')
def create_job_page():
    """Render the create job page"""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    data = load_data()
    user = next((u for u in data["users"] if u["id"] == session['user_id']), None)
    
    if not user or user["user_type"] != "client":
        return redirect(url_for('dashboard'))
    
    return render_template('create_job.html', user=user)

@app.route('/api/create_job', methods=['POST'])
def api_create_job():
    """API endpoint to create a new job"""
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401
    
    data = request.json
    
    title = data.get('title')
    description = data.get('description')
    skills_required = data.get('skills_required', [])
    budget = float(data.get('budget', 0))
    deadline = data.get('deadline')
    
    if not title or not description:
        return jsonify({"success": False, "error": "Title and description are required"}), 400
    
    if budget <= 0:
        return jsonify({"success": False, "error": "Budget must be greater than zero"}), 400
    
    if not deadline:
        return jsonify({"success": False, "error": "Deadline is required"}), 400
    
    job_id = create_job(
        session['user_id'],
        title,
        description,
        skills_required,
        budget,
        deadline
    )
    
    return jsonify({"success": True, "job_id": job_id}), 201

# Update profile route
@app.route('/profile')
def profile_page():
    """Render the user profile page"""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    data = load_data()
    user = next((u for u in data["users"] if u["id"] == session['user_id']), None)
    
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('home'))
    
    return render_template('profile.html', user=user)

@app.route('/api/update_profile', methods=['POST'])
def update_profile():
    """API endpoint to update user profile"""
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401
    
    data = request.json
    user_data = load_data()
    
    for user in user_data["users"]:
        if user["id"] == session['user_id']:
            # Update allowed fields
            if user["user_type"] == "freelancer":
                user["skills"] = data.get('skills', user.get("skills", []))
                user["hourly_rate"] = float(data.get('hourly_rate', user.get("hourly_rate", 0)))
            
            # Update common fields
            if "bio" in data:
                user["bio"] = data["bio"]
            
            if "email" in data:
                user["email"] = data["email"]
                
            if "phone" in data:
                user["phone"] = data["phone"]
            
            save_data(user_data)
            return jsonify({"success": True}), 200
    
    return jsonify({"success": False, "error": "User not found"}), 404

# Update these routes to match the .html extensions in your links
@app.route('/dashboard.html')
def dashboard_html():
    """Redirect to the dashboard route or render the dashboard directly"""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    data = load_data()
    user = next((u for u in data["users"] if u["id"] == session['user_id']), None)
    
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('home'))
    
    stats = {}
    
    if user["user_type"] == "client":
        # Client stats
        my_jobs = [j for j in data["jobs"] if j["client_id"] == user["id"]]
        stats["total_jobs"] = len(my_jobs)
        stats["active_jobs"] = len([j for j in my_jobs if j["status"] in ["open", "awarded"]])
        stats["completed_jobs"] = len([j for j in my_jobs if j["status"] == "completed"])
        
        # Calculate total spent
        if os.path.exists(Config.PAYMENT_LOG):
            with open(Config.PAYMENT_LOG, 'r') as f:
                transactions = json.load(f)
            
            client_transactions = [t for t in transactions if t["client_id"] == user["id"]]
            stats["total_spent"] = sum(t["amount"] for t in client_transactions)
        else:
            stats["total_spent"] = 0
            
    else:  # freelancer
        # Freelancer stats
        stats["completed_jobs"] = user["completed_jobs"]
        stats["rating"] = user["rating"]
        stats["current_balance"] = user["balance"]
        
        # Get active jobs
        active_jobs = []
        for job in data["jobs"]:
            if job["status"] == "awarded" and job.get("awarded_to") == user["id"]:
                active_jobs.append(job)
        
        stats["active_jobs"] = len(active_jobs)
        
        # Calculate earnings
        if os.path.exists(Config.PAYMENT_LOG):
            with open(Config.PAYMENT_LOG, 'r') as f:
                transactions = json.load(f)
            
            freelancer_transactions = [t for t in transactions if t["freelancer_id"] == user["id"]]
            stats["total_earnings"] = sum(t["freelancer_payment"] for t in freelancer_transactions)
            
            # Get earnings by month for chart
            earnings_by_month = {}
            for transaction in freelancer_transactions:
                date = datetime.fromisoformat(transaction["timestamp"])
                month_key = f"{date.year}-{date.month:02d}"
                
                if month_key not in earnings_by_month:
                    earnings_by_month[month_key] = 0
                    
                earnings_by_month[month_key] += transaction["freelancer_payment"]
                
            stats["earnings_by_month"] = earnings_by_month
        else:
            stats["total_earnings"] = 0
            stats["earnings_by_month"] = {}
    
    return render_template('dashboard.html', user=user, stats=stats)

@app.route('/jobs.html')
def jobs_html():
    """Render the jobs page with search functionality"""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    data = load_data()
    user = next((u for u in data["users"] if u["id"] == session['user_id']), None)
    
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('home'))
    
    # Get all open jobs
    open_jobs = search_jobs(status="open")
    
    # Get user's jobs based on type
    if user["user_type"] == "client":
        my_jobs = [job for job in data["jobs"] if job["client_id"] == user["id"]]
    else:  # freelancer
        # Get jobs the freelancer has applied to
        my_jobs = []
        for job in data["jobs"]:
            for app in job.get("applications", []):
                if app["freelancer_id"] == user["id"]:
                    job_copy = job.copy()
                    job_copy["my_application"] = app
                    my_jobs.append(job_copy)
                    break
    
    return render_template('jobs.html', 
                          user=user, 
                          open_jobs=open_jobs, 
                          my_jobs=my_jobs)

@app.route('/freelancer.html')
def freelancer_html():
    """Render the freelancer search page"""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    data = load_data()
    user = next((u for u in data["users"] if u["id"] == session['user_id']), None)
    
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('home'))
    
    # Get all freelancers
    freelancers = [u for u in data["users"] if u["user_type"] == "freelancer"]
    
    # Get skill tags for filtering
    all_skills = set()
    for freelancer in freelancers:
        for skill in freelancer.get("skills", []):
            all_skills.add(skill)
    
    return render_template('freelancer.html', 
                          user=user, 
                          freelancers=freelancers,
                          all_skills=sorted(list(all_skills)))

@app.route('/withdrawal.html')
def withdrawal_html():
    """Render the withdrawal page"""
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    data = load_data()
    user = next((u for u in data["users"] if u["id"] == session['user_id']), None)
    
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('home'))
    
    # Get user's withdrawal history
    withdrawals = [w for w in data.get("withdrawals", []) if w["user_id"] == user["id"]]
    
    return render_template('withdrawal.html', 
                          user=user, 
                          withdrawals=withdrawals)

if __name__ == '__main__':
    # Ensure the database file exists
    if not os.path.exists(Config.DATABASE_FILE):
        initial_data = {"users": [], "jobs": [], "matches": []}
        with open(Config.DATABASE_FILE, 'w') as f:
            json.dump(initial_data, f, indent=2)
    
    # Create admin user if not exists
    data = load_data()
    if not any(user["username"] == "admin" for user in data["users"]):
        create_user("admin", "admin123", "admin")
    
    app.run(debug=True)
