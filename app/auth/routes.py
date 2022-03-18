from flask import render_template, redirect, request, url_for, flash, Blueprint
from flask_login import login_user, logout_user, login_required, current_user
from . import auth
from .forms import PasswordResetForm, PasswordResetRequestForm
from ..models import db, User
from ..methods import send_email

@auth.before_app_request
def before_request():
    if current_user.is_authenticated \
            and not current_user.confirmed \
            and request.endpoint \
            and request.blueprint != 'auth' \
            and request.blueprint != 'main' \
            and request.endpoint != 'static':
        return redirect(url_for('auth.unconfirmed'))


@auth.route('/unconfirmed')
def unconfirmed():
    if current_user.is_anonymous or current_user.confirmed:
        return redirect(url_for('main.index'))
    return render_template('auth/unconfirmed.html')
@auth.route ('/login', methods=['GET', 'POST'])
def login():
    title = "Login"
    if request.method == 'POST':
        username_email = request.form.get('username').lower()
        user = User.query.filter((User.username==username_email) | (User.email==username_email)).first()
        if user is not None and user.verify_password(request.form['password']):
            remember_me = bool(request.form.get('remember_me', False))
            login_user(user, remember_me)
            next = request.args.get('next')
            if next is None or not next.startswith('/'):
                if user.is_administrator():
                    next = url_for('admin.index', logged_in=True)
                else:
                    next = url_for('admin.view_residents', logged_in=True)
            return redirect(next)
        else:
            flash('Invalid email or password.')
            return redirect(url_for('auth.login'))
    else:
        return render_template('auth/login.html', title=title)

@auth.route ('/reset_password', methods=['GET', 'POST'])
def reset_password():
    title = "Reset Password"
    form = PasswordResetRequestForm()
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email'].lower()).first()
        if user:
            token = user.generate_reset_token()
            send_email(user.email, 'Reset Your Password',
                       'auth/email/reset_password',
                       user=user, token=token)
            flash('An email with instructions to reset your password has been sent to you.')
        else:
            flash('No account registered with this email.', category='error')
        return redirect(url_for('auth.reset_password'))
    else:
        return render_template('auth/reset_password.html', title=title, form=form)

@auth.route('/confirm/<token>')
@login_required
def confirm(token):
    if current_user.confirmed:
        return redirect(url_for('main.index'))
    if current_user.confirm(token):
        db.session.commit()
        flash('You have confirmed your account. Thanks!')
    else:
        flash('The confirmation link is invalid or has expired.', category='error')
    return redirect(url_for('auth.login'))


@auth.route('/confirm')
@login_required
def resend_confirmation():
    token = current_user.generate_confirmation_token()
    send = send_email(current_user.email, 'Confirm Your Account',
               'auth/email/confirm', user=current_user, token=token)
    if send == 'sent':
        flash('A new confirmation email has been sent to you by email.')
    else:
        flash(f'Could not send mail due to {send}', category='success')
    return redirect(url_for('auth.login'))

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('auth.login'))

