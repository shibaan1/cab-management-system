from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cabs.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


db = SQLAlchemy(app)


# ==================== DATABASE MODELS ====================


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    role = db.Column(db.String(20), nullable=False)  # customer, driver, admin
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


    bookings = db.relationship('Booking', foreign_keys='Booking.customer_id', backref='customer', lazy=True)
    driver_profile = db.relationship('Driver', backref='user', uselist=False)


class Driver(db.Model):
    __tablename__ = 'drivers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    license_no = db.Column(db.String(50), unique=True, nullable=False)
    rating = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='available')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


    bookings = db.relationship('Booking', backref='driver', lazy=True)
    cab = db.relationship('Cab', backref='assigned_driver', uselist=False)


class Cab(db.Model):
    __tablename__ = 'cabs'
    id = db.Column(db.Integer, primary_key=True)
    registration_no = db.Column(db.String(50), unique=True, nullable=False)
    model = db.Column(db.String(100), nullable=False)
    capacity = db.Column(db.Integer, default=4)
    status = db.Column(db.String(20), default='available')
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


    bookings = db.relationship('Booking', backref='cab', lazy=True)


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'))
    cab_id = db.Column(db.Integer, db.ForeignKey('cabs.id'))
    pickup_address = db.Column(db.String(255), nullable=False)
    dropoff_address = db.Column(db.String(255), nullable=False)
    scheduled_time = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')
    distance_km = db.Column(db.Float, default=0.0)
    fare_estimate = db.Column(db.Float, default=0.0)
    fare_final = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)


# ==================== DECORATORS ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if session.get('role') not in roles:
                flash('Unauthorized access', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ==================== AUTHENTICATION ROUTES ====================
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username, is_active=True).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['first_name'] = user.first_name
            flash(f'Welcome back, {user.first_name}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        role = 'customer'
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password)
        new_user = User(
            username=username, email=email,
            password=hashed_password, first_name=first_name,
            last_name=last_name, phone=phone, role=role
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif role == 'driver':
        return redirect(url_for('driver_dashboard'))
    else:
        return redirect(url_for('customer_dashboard'))


# ============ CUSTOMER ROUTES ============
@app.route('/customer/dashboard')
@role_required('customer')
def customer_dashboard():
    user_id = session['user_id']
    pending = Booking.query.filter_by(customer_id=user_id, status='pending').count()
    active = Booking.query.filter(Booking.customer_id==user_id, Booking.status.in_(['assigned','en_route'])).count()
    completed = Booking.query.filter_by(customer_id=user_id, status='completed').count()
    recent = Booking.query.filter_by(customer_id=user_id).order_by(Booking.created_at.desc()).limit(5).all()
    return render_template('customer/dashboard.html', pending=pending, active=active, completed=completed, recent=recent)


@app.route('/customer/create-booking', methods=['GET', 'POST'])
@role_required('customer')
def create_booking():
    if request.method == 'POST':
        pickup = request.form.get('pickup_address')
        dropoff = request.form.get('dropoff_address')
        distance = float(request.form.get('distance_km', 5.0))
        fare_estimate = 50 + (distance * 15)
        new_booking = Booking(
            customer_id=session['user_id'],
            pickup_address=pickup, dropoff_address=dropoff,
            distance_km=distance, fare_estimate=fare_estimate, status='pending'
        )
        db.session.add(new_booking)
        db.session.commit()
        flash('Booking created!', 'success')
        return redirect(url_for('my_bookings'))
    
    return render_template('customer/create_booking.html')


@app.route('/customer/my-bookings')
@role_required('customer')
def my_bookings():
    bookings = Booking.query.filter_by(customer_id=session['user_id']).order_by(Booking.created_at.desc()).all()
    return render_template('customer/my_bookings.html', bookings=bookings)


@app.route('/customer/booking/<int:booking_id>')
@role_required('customer')
def booking_details(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.customer_id != session['user_id']:
        flash('Unauthorized', 'danger')
        return redirect(url_for('customer_dashboard'))
    return render_template('customer/booking_details.html', booking=booking)


@app.route('/customer/cancel-booking/<int:booking_id>', methods=['POST'])
@role_required('customer')
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.customer_id != session['user_id'] or booking.status not in ['pending', 'assigned']:
        return jsonify({'success': False}), 403
    booking.status = 'cancelled'
    if booking.driver_id:
        driver = Driver.query.get(booking.driver_id)
        driver.status = 'available'
    if booking.cab_id:
        cab = Cab.query.get(booking.cab_id)
        cab.status = 'available'
    db.session.commit()
    return jsonify({'success': True})


# ============ DRIVER ROUTES ============
@app.route('/driver/dashboard')
@role_required('driver')
def driver_dashboard():
    driver = Driver.query.filter_by(user_id=session['user_id']).first()
    assigned = Booking.query.filter_by(driver_id=driver.id, status='assigned').count()
    active = Booking.query.filter_by(driver_id=driver.id, status='en_route').count()
    completed = Booking.query.filter_by(driver_id=driver.id, status='completed').count()
    upcoming = Booking.query.filter(
        Booking.driver_id==driver.id, Booking.status.in_(['assigned','en_route'])
    ).all()
    return render_template('driver/dashboard.html', driver=driver, assigned=assigned, active=active, completed=completed, upcoming=upcoming)


@app.route('/driver/assigned-trips')
@role_required('driver')
def assigned_trips():
    driver = Driver.query.filter_by(user_id=session['user_id']).first()
    trips = Booking.query.filter(Booking.driver_id==driver.id, Booking.status.in_(['assigned','en_route'])).all()
    return render_template('driver/assigned_trips.html', trips=trips)


@app.route('/driver/trip-history')
@role_required('driver')
def trip_history():
    driver = Driver.query.filter_by(user_id=session['user_id']).first()
    trips = Booking.query.filter_by(driver_id=driver.id, status='completed').order_by(Booking.completed_at.desc()).all()
    return render_template('driver/trip_history.html', trips=trips)


@app.route('/driver/start-trip/<int:booking_id>', methods=['POST'])
@role_required('driver')
def start_trip(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    driver = Driver.query.filter_by(user_id=session['user_id']).first()
    if booking.driver_id != driver.id:
        return jsonify({'success': False}), 403
    booking.status = 'en_route'
    driver.status = 'on_trip'
    if booking.cab_id:
        booking.cab.status = 'on_trip'
    db.session.commit()
    return jsonify({'success': True})


@app.route('/driver/complete-trip/<int:booking_id>', methods=['POST'])
@role_required('driver')
def complete_trip(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    driver = Driver.query.filter_by(user_id=session['user_id']).first()
    if booking.driver_id != driver.id:
        return jsonify({'success': False}), 403
    booking.status = 'completed'
    booking.completed_at = datetime.utcnow()
    booking.fare_final = booking.fare_estimate
    driver.status = 'available'
    if booking.cab_id:
        booking.cab.status = 'available'
    db.session.commit()
    return jsonify({'success': True, 'fare': booking.fare_final})


# ============ ADMIN ROUTES ============
@app.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    total_bookings = Booking.query.count()
    pending = Booking.query.filter_by(status='pending').count()
    active = Booking.query.filter(Booking.status.in_(['assigned','en_route'])).count()
    completed = Booking.query.filter_by(status='completed').count()
    total_drivers = Driver.query.count()
    available_drivers = Driver.query.filter_by(status='available').count()
    total_cabs = Cab.query.count()
    available_cabs = Cab.query.filter_by(status='available').count()
    recent = Booking.query.order_by(Booking.created_at.desc()).limit(10).all()
    return render_template('admin/dashboard.html', total_bookings=total_bookings, pending=pending, 
                         active=active, completed=completed, total_drivers=total_drivers,
                         available_drivers=available_drivers, total_cabs=total_cabs,
                         available_cabs=available_cabs, recent=recent)


@app.route('/admin/manage-drivers')
@role_required('admin')
def manage_drivers():
    drivers = Driver.query.options(db.joinedload(Driver.user)).all()
    return render_template('admin/manage_drivers.html', drivers=drivers)


@app.route('/admin/add-driver', methods=['GET', 'POST'])
@role_required('admin')
def add_driver():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        license_no = request.form.get('license_no')
        if User.query.filter_by(username=username).first():
            flash('Username exists', 'danger')
            return redirect(url_for('add_driver'))
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_password,
                       first_name=first_name, last_name=last_name, phone=phone, role='driver')
        db.session.add(new_user)
        db.session.flush()
        new_driver = Driver(user_id=new_user.id, license_no=license_no, status='available')
        db.session.add(new_driver)
        db.session.commit()
        flash('Driver added!', 'success')
        return redirect(url_for('manage_drivers'))
    return render_template('admin/add_driver.html')


@app.route('/admin/manage-cabs')
@role_required('admin')
def manage_cabs():
    cabs = Cab.query.all()
    drivers = Driver.query.filter_by(status='available').all()
    return render_template('admin/manage_cabs.html', cabs=cabs, drivers=drivers)


@app.route('/admin/add-cab', methods=['POST'])
@role_required('admin')
def add_cab():
    reg_no = request.form.get('registration_no')
    model = request.form.get('model')
    capacity = int(request.form.get('capacity', 4))
    driver_id = request.form.get('driver_id')
    if Cab.query.filter_by(registration_no=reg_no).first():
        flash('Registration exists', 'danger')
        return redirect(url_for('manage_cabs'))
    new_cab = Cab(registration_no=reg_no, model=model, capacity=capacity,
                 driver_id=int(driver_id) if driver_id else None, status='available')
    db.session.add(new_cab)
    db.session.commit()
    flash('Cab added!', 'success')
    return redirect(url_for('manage_cabs'))


@app.route('/admin/manage-bookings')
@role_required('admin')
def manage_bookings():
    status_filter = request.args.get('status', 'all')
    bookings = Booking.query.filter_by(status=status_filter).all() if status_filter != 'all' else Booking.query.all()
    drivers = Driver.query.filter_by(status='available').all()
    cabs = Cab.query.filter_by(status='available').all()
    return render_template('admin/manage_bookings.html', bookings=bookings, drivers=drivers, cabs=cabs)


@app.route('/admin/assign-booking/<int:booking_id>', methods=['POST'])
@role_required('admin')
def assign_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    driver_id = request.form.get('driver_id')
    cab_id = request.form.get('cab_id')
    
    if not driver_id or not cab_id:
        flash('Please select both driver and cab', 'danger')
        return redirect(url_for('manage_bookings'))
    
    driver = Driver.query.get(driver_id)
    cab = Cab.query.get(cab_id)
    
    booking.driver_id = driver_id
    booking.cab_id = cab_id
    booking.status = 'assigned'
    driver.status = 'on_trip'
    cab.status = 'on_trip'
    
    db.session.commit()
    
    flash('Booking assigned successfully!', 'success')
    return redirect(url_for('manage_bookings'))



@app.route('/admin/reports')
@role_required('admin')
def reports():
    total_revenue = db.session.query(db.func.sum(Booking.fare_final)).scalar() or 0
    total_trips = Booking.query.filter_by(status='completed').count()
    avg_fare = total_revenue / total_trips if total_trips > 0 else 0
    return render_template('admin/reports.html', revenue=total_revenue, trips=total_trips, avg=avg_fare)


def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', email='admin@cab.com',
                        password=generate_password_hash('admin123'),
                        first_name='Admin', last_name='User', phone='9876543210', role='admin')
            db.session.add(admin)
            driver_user = User(username='driver1', email='driver1@cab.com',
                              password=generate_password_hash('driver123'),
                              first_name='John', last_name='Driver', phone='9876543211', role='driver')
            db.session.add(driver_user)
            db.session.flush()
            driver = Driver(user_id=driver_user.id, license_no='DL001', rating=4.5, status='available')
            db.session.add(driver)
            customer = User(username='customer1', email='customer1@cab.com',
                           password=generate_password_hash('cust123'),
                           first_name='Jane', last_name='Customer', phone='9876543212', role='customer')
            db.session.add(customer)
            cab1 = Cab(registration_no='KA-01-AB-1234', model='Toyota Innova', capacity=7, status='available', driver_id=1)
            cab2 = Cab(registration_no='KA-01-CD-5678', model='Maruti Swift', capacity=4, status='available')
            db.session.add_all([cab1, cab2])
            db.session.commit()
            print('✅ Database initialized successfully!')


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
