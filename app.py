from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    issues = db.relationship('Issue', backref='user', lazy=True)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    isbn = db.Column(db.String(50), unique=True, nullable=False)
    category = db.Column(db.String(50))
    quantity = db.Column(db.Integer, default=1)
    available = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    issues = db.relationship('Issue', backref='book', lazy=True)

class Issue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=False)
    return_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='issued')
    fine = db.Column(db.Float, default=0.0)

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
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash(f'Welcome {user.name}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        role = request.form.get('role', 'student')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        new_user = User(name=name, username=username, email=email, phone=phone, password=hashed_password, role=role)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    now = datetime.utcnow()
    
    if user.role == 'admin':
        total_users = User.query.count()
        total_books = Book.query.count()
        total_issues = Issue.query.filter_by(status='issued').count()
        total_fines = db.session.query(db.func.sum(Issue.fine)).scalar() or 0
        recent_issues = Issue.query.order_by(Issue.issue_date.desc()).limit(5).all()
        
        return render_template('admin_dashboard.html', user=user, total_users=total_users, 
                             total_books=total_books, total_issues=total_issues, 
                             total_fines=total_fines, recent_issues=recent_issues)
    
    elif user.role == 'staff':
        pending_issues = Issue.query.filter_by(status='issued').all()
        overdue_issues = [issue for issue in pending_issues if now > issue.due_date]
        
        return render_template('staff_dashboard.html', user=user, pending_issues=pending_issues,
                             overdue_issues=overdue_issues, now=now)
    
    else:
        my_issues = Issue.query.filter_by(user_id=user.id, status='issued').all()
        my_history = Issue.query.filter_by(user_id=user.id, status='returned').order_by(Issue.return_date.desc()).limit(5).all()
        my_fines = db.session.query(db.func.sum(Issue.fine)).filter(Issue.user_id==user.id).scalar() or 0
        
        return render_template('student_dashboard.html', user=user, my_issues=my_issues, 
                             my_history=my_history, my_fines=my_fines, now=now)

@app.route('/books')
def books():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    all_books = Book.query.all()
    user = User.query.get(session['user_id'])
    return render_template('books.html', books=all_books, user=user)

@app.route('/books/add', methods=['GET', 'POST'])
def add_book():
    if 'user_id' not in session or session['role'] not in ['admin', 'staff']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        author = request.form.get('author')
        isbn = request.form.get('isbn')
        category = request.form.get('category')
        quantity = int(request.form.get('quantity', 1))
        
        if Book.query.filter_by(isbn=isbn).first():
            flash('Book with this ISBN already exists', 'danger')
            return redirect(url_for('add_book'))
        
        new_book = Book(title=title, author=author, isbn=isbn, category=category, quantity=quantity, available=quantity)
        db.session.add(new_book)
        db.session.commit()
        
        flash('Book added successfully!', 'success')
        return redirect(url_for('books'))
    
    user = User.query.get(session['user_id'])
    return render_template('add_book.html', user=user)

@app.route('/books/edit/<int:book_id>', methods=['GET', 'POST'])
def edit_book(book_id):
    if 'user_id' not in session or session['role'] not in ['admin', 'staff']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    book = Book.query.get_or_404(book_id)
    
    if request.method == 'POST':
        book.title = request.form.get('title')
        book.author = request.form.get('author')
        book.isbn = request.form.get('isbn')
        book.category = request.form.get('category')
        
        new_quantity = int(request.form.get('quantity'))
        diff = new_quantity - book.quantity
        book.quantity = new_quantity
        book.available += diff
        
        db.session.commit()
        flash('Book updated successfully!', 'success')
        return redirect(url_for('books'))
    
    user = User.query.get(session['user_id'])
    return render_template('edit_book.html', book=book, user=user)

@app.route('/books/delete/<int:book_id>')
def delete_book(book_id):
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    book = Book.query.get_or_404(book_id)
    active_issues = Issue.query.filter_by(book_id=book_id, status='issued').count()
    
    if active_issues > 0:
        flash('Cannot delete book with active issues', 'danger')
        return redirect(url_for('books'))
    
    db.session.delete(book)
    db.session.commit()
    flash('Book deleted successfully!', 'success')
    return redirect(url_for('books'))

@app.route('/issue-book/<int:book_id>', methods=['POST'])
def issue_book(book_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    book = Book.query.get_or_404(book_id)
    
    if book.available <= 0:
        return jsonify({'success': False, 'message': 'Book not available'}), 400
    
    existing_issue = Issue.query.filter_by(book_id=book_id, user_id=session['user_id'], status='issued').first()
    
    if existing_issue:
        return jsonify({'success': False, 'message': 'You already have this book issued'}), 400
    
    due_date = datetime.utcnow() + timedelta(days=14)
    new_issue = Issue(book_id=book_id, user_id=session['user_id'], due_date=due_date)
    
    book.available -= 1
    db.session.add(new_issue)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Book issued successfully'})

@app.route('/return-book/<int:issue_id>', methods=['POST'])
def return_book(issue_id):
    if 'user_id' not in session or session['role'] not in ['admin', 'staff']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    issue = Issue.query.get_or_404(issue_id)
    
    if issue.status == 'returned':
        return jsonify({'success': False, 'message': 'Book already returned'}), 400
    
    issue.return_date = datetime.utcnow()
    issue.status = 'returned'
    
    if issue.return_date > issue.due_date:
        days_overdue = (issue.return_date - issue.due_date).days
        issue.fine = days_overdue * 10
    
    issue.book.available += 1
    db.session.commit()
    
    message = f'Book returned successfully! Fine: Rs. {issue.fine}' if issue.fine > 0 else 'Book returned successfully!'
    return jsonify({'success': True, 'message': message, 'fine': issue.fine})

@app.route('/users')
def users():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    all_users = User.query.all()
    user = User.query.get(session['user_id'])
    return render_template('users.html', users=all_users, user=user)

@app.route('/reports')
def reports():
    if 'user_id' not in session or session['role'] not in ['admin', 'staff']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    user = User.query.get(session['user_id'])
    all_issues = Issue.query.order_by(Issue.issue_date.desc()).all()
    return render_template('reports.html', user=user, issues=all_issues)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

def init_db():
    with app.app_context():
        db.create_all()
        
        if not User.query.filter_by(username='admin').first():
            admin = User(name='Admin User', username='admin', email='admin@library.com', 
                        phone='1234567890', password=generate_password_hash('admin123'), role='admin')
            staff = User(name='Staff Member', username='staff', email='staff@library.com', 
                        phone='1234567891', password=generate_password_hash('staff123'), role='staff')
            student = User(name='John Student', username='john', email='john@student.com', 
                          phone='1234567892', password=generate_password_hash('john123'), role='student')
            
            db.session.add_all([admin, staff, student])
            
            books = [
                Book(title='The Great Gatsby', author='F. Scott Fitzgerald', isbn='9780743273565', 
                     category='Fiction', quantity=5, available=5),
                Book(title='To Kill a Mockingbird', author='Harper Lee', isbn='9780061120084', 
                     category='Fiction', quantity=3, available=3),
                Book(title='Introduction to Algorithms', author='Thomas H. Cormen', 
                     isbn='9780262033848', category='Technology', quantity=4, available=4),
                Book(title='A Brief History of Time', author='Stephen Hawking', 
                     isbn='9780553380163', category='Science', quantity=6, available=6),
                Book(title='1984', author='George Orwell', isbn='9780451524935', 
                     category='Fiction', quantity=5, available=5)
            ]
            
            db.session.add_all(books)
            db.session.commit()
            print('Database initialized with sample data!')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
