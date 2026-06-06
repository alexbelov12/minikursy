import secrets
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, PasswordResetToken

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
        user.generate_referral_code()

        ref_code = request.args.get('ref') or request.form.get('ref', '').strip()
        referrer = None
        if ref_code:
            referrer = User.query.filter_by(referral_code=ref_code).first()
            if referrer and referrer.email != email:
                user.referred_by_id = referrer.id

        db.session.add(user)
        db.session.commit()

        if referrer and user.referred_by_id:
            from app.models import award_badges
            award_badges(referrer)
            db.session.commit()

        login_user(user)
        flash('Регистрация прошла успешно! Добро пожаловать!', 'success')
        return redirect(url_for('main.index'))

    ref = request.args.get('ref', '')
    return render_template('auth/register.html', ref=ref)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    reset_url = None
    email_sent = False

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        user = User.query.filter_by(email=email).first()
        if user:
            token_str = secrets.token_urlsafe(48)
            token = PasswordResetToken(
                user_id=user.id,
                token=token_str,
                expires_at=datetime.utcnow() + timedelta(hours=1)
            )
            db.session.add(token)
            db.session.commit()
            reset_url = url_for('auth.reset_password', token=token_str, _external=True)

            # Try to send via email; fall back to showing the link on page
            from app.email import send_email
            html_body = f'''
            <p>Здравствуйте, {user.username}!</p>
            <p>Для сброса пароля перейдите по ссылке:</p>
            <p><a href="{reset_url}">{reset_url}</a></p>
            <p>Ссылка действительна 1 час.</p>
            '''
            email_sent = send_email(user.email, 'Сброс пароля — МиниКурсы', html_body)
            if email_sent:
                reset_url = None  # hide link when email sent successfully
        else:
            flash('Если такой email зарегистрирован, вы получите ссылку для сброса', 'info')

    return render_template('auth/forgot_password.html',
                           reset_url=reset_url,
                           email_sent=email_sent)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    record = PasswordResetToken.query.filter_by(token=token, used=False).first()
    if not record or record.expires_at < datetime.utcnow():
        flash('Ссылка для сброса пароля недействительна или истекла', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if len(password) < 6:
            flash('Пароль должен содержать не менее 6 символов', 'danger')
            return render_template('auth/reset_password.html', token=token)

        if password != confirm:
            flash('Пароли не совпадают', 'danger')
            return render_template('auth/reset_password.html', token=token)

        record.user.set_password(password)
        record.used = True
        db.session.commit()
        flash('Пароль успешно изменён. Теперь вы можете войти.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)
