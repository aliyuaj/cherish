from flask import render_template, redirect, request, url_for, flash, current_app
from flask_mail import Message
from . import main
from ..models import db, Messages
from ..methods import send_email

@main.route('/')
@main.route('/index')
def home():
    title = "Home"
    return render_template('index.html', title=title)

@main.route('/contact', methods=['GET', 'POST'])
def contact():
    title = "Contact Us"
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        subject = request.form.get('subject')
        message = request.form.get('message')
        category = request.form.get('category')
        body = message + "\n" + name + "\n" + phone + "\n" + email
        send = send_email('CherishCare@gmail.com', 
            subject.upper(),
            'email/contact_form_mail',
            name=name.title(),
            email=email.lower(),
            phone=phone,
            message=message,
            )
        if send == 'sent':
            app_msg = Messages(subject= subject.upper(),
                            category = category,
                            name=name.title(),
                            email=email.lower(),
                            phone=phone,
                            message=message,
                            )
            db.session.add(app_msg)
            db.session.commit()
            flash('Thank you for your message. We\'ll get back to you shortly')
        else:
            flash(f'Unable to send your message due to {send}', category='error')
        return redirect(url_for('main.contact', title=title))
    else:
        return render_template('contact.html', title=title)

