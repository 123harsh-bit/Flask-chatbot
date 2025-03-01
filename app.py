from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import openai
import os
from dotenv import load_dotenv

# ------------------ INITIAL SETUP ------------------

# Initialize Flask app
app = Flask(__name__)
load_dotenv()  # Load environment variables from .env

# Secret Key & OpenAI Key
app.secret_key = os.getenv("FLASK_SECRET_KEY")
openai.api_key = os.getenv("OPENAI_API_KEY")

# PostgreSQL Config
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# ------------------ DATABASE MODELS ------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    chats = db.relationship('ChatHistory', backref='user', lazy=True)

class ChatHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_input = db.Column(db.Text, nullable=False)
    bot_response = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# ------------------ HEART KEYWORDS ------------------

HEART_KEYWORDS = [
    "heart","for","continue","cardiac", "week", "month", "day", "blood pressure", "cholesterol", 
    "heart attack", "stroke", "arrhythmia", "hypertension", "pulse", "artery", 
    "coronary", "circulation", "table","ECG", "EKG", "aorta", "cardiovascular", 
    "angioplasty", "bypass surgery"
]

def is_heart_related(user_input):
    """Check if the user input contains heart-related keywords."""
    user_input = user_input.lower()
    return any(keyword in user_input for keyword in HEART_KEYWORDS)

# ------------------ ROUTES ------------------

# ---------- Home ----------
@app.route('/')
def home():
    if 'user_id' in session:
        return render_template('index.html')
    return redirect(url_for('login'))

# ---------- Sign Up ----------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if username exists
        if User.query.filter_by(username=username).first():
            return render_template('signup.html', error_message="⚠️ Username already exists. Please try another.")

        # Hash password and add user
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))
    return render_template('signup.html')

# ---------- Login ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if not user:
            return render_template('login.html', error_message="⚠️ Username does not exist.")

        if not check_password_hash(user.password, password):
            return render_template('login.html', error_message="⚠️ Invalid password. Please try again.")

        session['user_id'] = user.id
        return redirect(url_for('home'))

    return render_template('login.html')

# ---------- Logout ----------
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

# ---------- Chat ----------
@app.route('/chat', methods=['POST'])
def chat():
    if 'user_id' not in session:
        return jsonify({"response": "Please log in first.", "type": "text"})

    user_input = request.json.get('message', '')

    # Check if heart-related
    if not is_heart_related(user_input):
        return jsonify({"response": "I can only answer heart health-related questions.", "type": "text"})

    # Fetch previous chat history for context
    previous_chats = ChatHistory.query.filter_by(user_id=session['user_id']).all()
    conversation_history = [{"role": "system", "content": "You are a heart health expert."}]

    for chat in previous_chats:
        conversation_history.append({"role": "user", "content": chat.user_input})
        conversation_history.append({"role": "assistant", "content": chat.bot_response})

    conversation_history.append({"role": "user", "content": user_input})

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=conversation_history
        )

        chatbot_response = response['choices'][0]['message']['content']

        # Save chat history
        new_chat = ChatHistory(user_input=user_input, bot_response=chatbot_response, user_id=session['user_id'])
        db.session.add(new_chat)
        db.session.commit()

        return jsonify({"response": chatbot_response, "type": "text"})

    except Exception as e:
        return jsonify({"response": f"Error: {str(e)}", "type": "text"}), 500

# ---------- Chat History ----------
@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    chats = ChatHistory.query.filter_by(user_id=session['user_id']).all()
    return render_template('history.html', chats=chats)

# ------------------ MAIN ------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Create tables if they don't exist
    app.run(debug=True, host="0.0.0.0", port=5000)
