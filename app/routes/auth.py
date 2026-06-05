from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            flash(f'Добро пожаловать, {user.username}!', 'success')
            return redirect(next_page or url_for('main.index'))
        else:
            flash('Неверный email или пароль', 'danger')

    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not username or not email or not password:
            flash('Заполните все поля', 'danger')
            return render_template('auth/register.html')

        if password != confirm:
            flash('Пароли не совпадают', 'danger')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash('Пароль должен содержать не менее 6 символов', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(username=username).first():
            flash('Это имя пользователя уже занято', 'danger')
            return render_template('auth/register.html')

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash('Регистрация прошла успешно! Добро пожаловать!', 'success')
        return redirect(url_for('main.index'))

    return render_template('auth/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('main.index'))
