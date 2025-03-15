from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import PyPDF2

app = Flask(__name__)

# Configuration
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'database', 'assessment.db')
os.makedirs(os.path.dirname(db_path), exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this to a secure key
app.config['UPLOADED_PDFS_DEST'] = os.path.join(basedir, 'uploads')  # Folder for uploaded PDFs
os.makedirs(app.config['UPLOADED_PDFS_DEST'], exist_ok=True)  # Ensure the upload directory exists

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False)  # student or teacher
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Question Model
class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.String(500), nullable=False)
    question_type = db.Column(db.String(20), nullable=False)  # mcq or subjective
    marks = db.Column(db.Integer, nullable=False)
    option_a = db.Column(db.String(200))  # For MCQ
    option_b = db.Column(db.String(200))  # For MCQ
    option_c = db.Column(db.String(200))  # For MCQ
    option_d = db.Column(db.String(200))  # For MCQ
    correct_answer = db.Column(db.String(200))  # For MCQ

# Test Model
class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    pdf_filename = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# AnswerKey Model
class AnswerKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    correct_answer = db.Column(db.String(10), nullable=False)  # e.g., 'A', 'B', 'C', 'D'

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

# Function to parse PDF and extract questions
def parse_pdf(file_path):
    questions = []
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            print(f"Number of pages: {len(reader.pages)}")  # Debug: Print number of pages

            for page_num, page in enumerate(reader.pages):
                text = page.extract_text()
                print(f"Raw text from page {page_num + 1}:\n{text}")  # Debug: Print raw text from each page

                if text:
                    lines = text.split('\n')
                    print(f"Lines from page {page_num + 1}: {lines}")  # Debug: Print lines from the page

                    i = 0
                    while i < len(lines):
                        line = lines[i].strip()
                        print(f"Processing line: {line}")  # Debug: Print each line being processed

                        # Detect question (customize this based on your PDF format)
                        if line.startswith('Q') and '.' in line:  # Example: "Q1. What is Python?"
                            question_text = line
                            options = []
                            i += 1
                            # Collect options (A, B, C, D)
                            while i < len(lines) and (lines[i].strip().startswith('A.') or lines[i].strip().startswith('B.') or lines[i].strip().startswith('C.') or lines[i].strip().startswith('D.')):
                                options.append(lines[i].strip())
                                i += 1
                            # Add question and options to the list
                            questions.append({
                                'question_text': question_text,
                                'options': options
                            })
                            print(f"Added question: {question_text} with options: {options}")  # Debug: Print added question
                        else:
                            i += 1
                else:
                    print(f"No text extracted from page {page_num + 1}.")  # Debug: No text found
    except Exception as e:
        print(f"Error parsing PDF: {e}")  # Debug: Print any errors

    print(f"Extracted questions: {questions}")  # Debug: Print extracted questions
    return questions

# Routes for authentication
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role')

        if password != confirm_password:
            flash('Passwords do not match')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))

        user = User(username=username, email=email, role=role)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

# Protected routes
@app.route('/')
def home():
    if current_user.is_authenticated:
        return render_template('index.html')
    return redirect(url_for('login'))

# Add PDF upload route
@app.route('/upload_pdf', methods=['GET', 'POST'])
@login_required
def upload_pdf():
    if current_user.role != 'teacher':
        flash('Access denied. Teachers only.')
        return redirect(url_for('home'))

    if request.method == 'POST':
        if 'pdf' not in request.files:
            flash('No file uploaded')
            return redirect(url_for('upload_pdf'))

        file = request.files['pdf']
        if file.filename == '':
            flash('No file selected')
            return redirect(url_for('upload_pdf'))

        if file and file.filename.endswith('.pdf'):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOADED_PDFS_DEST'], filename)
            file.save(file_path)

            # Parse PDF and extract questions
            questions = parse_pdf(file_path)
            print(f"Extracted questions: {questions}")  # Debug: Print extracted questions

            if not questions:
                flash('No questions found in the PDF.')
                return redirect(url_for('upload_pdf'))

            # Create a new test
            test_name = request.form.get('test_name')
            test_description = request.form.get('test_description')
            new_test = Test(
                name=test_name,
                description=test_description,
                pdf_filename=filename
            )
            db.session.add(new_test)
            db.session.commit()

            # Add questions to the database
            for q in questions:
                new_question = Question(
                    question_text=q['question_text'],
                    question_type='mcq',  # Default to MCQ
                    marks=1,  # Default marks
                    option_a=q['options'][0] if len(q['options']) > 0 else None,
                    option_b=q['options'][1] if len(q['options']) > 1 else None,
                    option_c=q['options'][2] if len(q['options']) > 2 else None,
                    option_d=q['options'][3] if len(q['options']) > 3 else None,
                    correct_answer=None  # Teacher can update this later
                )
                db.session.add(new_question)
                db.session.commit()  # Commit to get the question ID

                # Associate the question with the test
                db.session.flush()  # Ensure the question ID is available
                new_answer_key = AnswerKey(
                    test_id=new_test.id,
                    question_id=new_question.id,
                    correct_answer=None  # Teacher can update this later
                )
                db.session.add(new_answer_key)

            db.session.commit()
            flash('Test and questions added successfully!')
            return redirect(url_for('manage_tests'))

    return render_template('upload_pdf.html')

# Add Answer Key route
@app.route('/add_answer_key/<int:test_id>', methods=['GET', 'POST'])
@login_required
def add_answer_key(test_id):
    if current_user.role != 'teacher':
        flash('Access denied. Teachers only.')
        return redirect(url_for('home'))

    test = Test.query.get_or_404(test_id)
    questions = Question.query.join(AnswerKey).filter(AnswerKey.test_id == test_id).all()

    if request.method == 'POST':
        for question in questions:
            correct_answer = request.form.get(f'correct_answer_{question.id}')
            if correct_answer:
                answer_key = AnswerKey.query.filter_by(test_id=test_id, question_id=question.id).first()
                answer_key.correct_answer = correct_answer
                db.session.commit()

        flash('Answer key updated successfully!')
        return redirect(url_for('manage_tests'))

    return render_template('add_answer_key.html', test=test, questions=questions)

# Manage Tests route
@app.route('/manage_tests', methods=['GET'])
@login_required
def manage_tests():
    if current_user.role != 'teacher':
        flash('Access denied. Teachers only.')
        return redirect(url_for('home'))

    tests = Test.query.all()
    return render_template('manage_tests.html', tests=tests)

# Initialize database
def init_db():
    with app.app_context():
        db.create_all()
        
        # Create a default teacher account if it doesn't exist
        if not User.query.filter_by(username='teacher').first():
            teacher = User(
                username='teacher',
                email='teacher@example.com',
                role='teacher'
            )
            teacher.set_password('teacher123')
            db.session.add(teacher)
            db.session.commit()
            
        print("Database initialized successfully!")

if __name__ == '__main__':
    init_db()
    app.run(debug=True)