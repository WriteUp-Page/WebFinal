import pymysql
import os
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_bcrypt import Bcrypt
from flask_login import current_user, login_required, login_user, logout_user
from flask_migrate import Migrate
from forms import LoginForm, PostForm, RegistrationForm, QuestionForm
from models import db, login_manager, User, Post, Question
from sqlalchemy.sql import text
import logging

# Flask 로거 설정
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config.from_object("config.Config")  # 환경설정 불러오기

db.init_app(app)  # 데이터베이스 초기화
migrate = Migrate(app, db)  # Flask-Migrate 초기화
bcrypt = Bcrypt(app)  # 비밀번호 암호화
login_manager.init_app(app)  # 로그인 매니저 초기화
login_manager.login_view = "login"  # 로그인이 필요한 페이지로 리다이렉트

# 데이터 저장을 위한 간단한 리스트
posts = []

@app.route("/")
@app.route("/home")
def home():
    return render_template("home.html")

@app.route("/project")  # 프로젝트 리스팅 페이지
def project():
    return render_template("project.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    if request.method == "GET":
        return render_template("register.html", form=form)
    else:
        if current_user.is_authenticated:
            return redirect(url_for("home"))
        if form.validate_on_submit():
            existing_user = User.query.filter_by(username=form.username.data).first()
            if existing_user:
                flash("Username already exists. Please choose a different one.", "danger")
                return redirect(url_for("register"))
            else:
                hashed_password = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
                user = User(username=form.username.data, email=form.email.data, password=hashed_password)
                db.session.add(user)
                db.session.commit()
                flash("Your account has been created! You are now able to log in", "success")
                return redirect(url_for("login"))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Error in the {getattr(form, field).label.text} field - {error}", "danger")
            print("Form errors:", form.errors)  # 디버깅용 로그 추가
        return render_template("register.html", form=form)

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get("next")
            return redirect(next_page) if next_page else redirect(url_for("home"))
        else:
            flash("Login Unsuccessful. Please check email and password", "danger")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in the {getattr(form, field).label.text} field - {error}", "danger")
        print("Form errors:", form.errors)  # 디버깅용 로그 추가
    return render_template("login.html", form=form)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

# 게시판 페이지
# 로그인 필요
@app.route("/board", methods=["GET", "POST"])
@login_required
def board():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(
            title=form.title.data, content=form.content.data, user_id=current_user.id
        )
        db.session.add(post)
        db.session.commit()
        flash("Your post has been created!", "success")
        return redirect(url_for("board"))
    posts = Post.query.all()
    return render_template("board.html", title="Board", form=form, posts=posts)

# 동아리 소개 페이지
@app.route("/intro", methods=["GET"])
def intro():
    return render_template("intro.html")

# 에러 발생시 404.html로 리다이렉트
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@app.route("/check_db")
def check_db():
    try:
        # 데이터베이스 연결 확인
        result = db.session.execute(text('SELECT 1'))
        if result:
            return "Database connection successful!"
        else:
            return "Database connection failed!"
    except Exception as e:
        return f"Database connection failed! Error: {str(e)}"

# Q&A 관련 
@app.route("/qa", methods=["GET", "POST"])
def qa():
    form = QuestionForm()
    if form.validate_on_submit():
        question = Question(title=form.title.data, question=form.question.data)
        db.session.add(question)
        db.session.commit()
        flash('Your question has been submitted!', 'success')
        return redirect(url_for('qa'))
    questions = Question.query.all()
    return render_template('qa.html', form=form, questions=questions)

@app.route("/qa/<int:question_id>", methods=["GET", "POST"])
def answer(question_id):
    question = Question.query.get_or_404(question_id)
    if request.method == "POST":
        question.answer = request.form['answer']
        question.is_answered = True
        db.session.commit()
        flash('Your answer has been submitted!', 'success')
        return redirect(url_for('qa'))
    return render_template('answer.html', question=question)

# Q&A 게시판
@app.route('/QAindex')
def index():
    return render_template('QAindex.html', posts=posts)

@app.route('/write', methods=['GET', 'POST'])
def write():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        password = request.form['password']
        post_id = len(posts) + 1
        posts.append({'id': post_id, 'title': title, 'content': content, 'password': password})
        return redirect(url_for('index'))
    return render_template('write.html')

@app.route('/post/<int:post_id>')
def read(post_id):
    post = next((post for post in posts if post['id'] == post_id), None)
    if post is None:
        return "Post not found", 404
    return render_template('read.html', post=post)

@app.route('/edit_password/<int:post_id>', methods=['GET', 'POST'])
def edit_password(post_id):
    post = next((post for post in posts if post['id'] == post_id), None)
    if post is None:
        return "Post not found", 404
    if request.method == 'POST':
        password = request.form['password']
        if post['password'] == password:
            return redirect(url_for('edit', post_id=post_id))
        else:
            return "Incorrect password", 403
    return render_template('edit_password.html', post_id=post_id)

@app.route('/edit/<int:post_id>', methods=['GET', 'POST'])
def edit(post_id):
    post = next((post for post in posts if post['id'] == post_id), None)
    if post is None:
        return "Post not found", 404
    if request.method == 'POST':
        post['title'] = request.form['title']
        post['content'] = request.form['content']
        return redirect(url_for('read', post_id=post_id))
    return render_template('edit.html', post=post)

@app.route('/delete/<int:post_id>')
def delete(post_id):
    global posts
    posts = [post for post in posts if post['id'] != post_id]
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(port=5000, debug=True)
