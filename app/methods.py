from threading import Thread
from flask import current_app, render_template, abort
from flask_mail import Message
from queue import Queue
from werkzeug.utils import secure_filename
from datetime import datetime
from . import mail
from .models import db, Messages, User, Role, ActivityGroup, Activity
import os


tables_dict = {
    'messages': Messages,
        'User': User,
        'roles': Role,
    'group': ActivityGroup
}


def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
            return 'sent'
        except Exception as e:
            return str(e)


def send_email(to, subject, template=None, **kwargs):
    app = current_app._get_current_object()
    msg = Message(app.config['CHERISH_MAIL_SUBJECT_PREFIX'] + '-' + subject,
                  sender=app.config['CHERISH_MAIL_SENDER'], recipients=[to])
    if template == None:
        msg.html = kwargs['html']
    else:
        msg.body = render_template(template + '.txt', **kwargs)
        msg.html = render_template(template + '.html', **kwargs)
    que = Queue()
    thr = Thread(target=lambda q, arg1, arg2:
                 q.put(send_async_email(arg1, arg2)),
                 args=(que, app, msg)
                 )
    thr.start()
    thr.join()
    result = que.get()
    return result


def delete_item(item, target_table, **kwargs):
    table = tables_dict[target_table]
    try:
        table.query.filter(table.id.in_(item)).delete(
            synchronize_session=False)
        db.session.commit()
        return True
    except Exception as e:
        return str(e)


def trash_item(item, target_table, **kwargs):
    table = tables_dict[target_table]
    try:
        table.query.filter(table.id.in_(item)).update({"is_trashed": True}, synchronize_session=False)
        db.session.commit()
        return True
    except Exception as e:
        return str(e)
def upload_photo(uploaded_file):
    filename = secure_filename(uploaded_file.filename)
    if filename != '':
        file_ext = os.path.splitext(filename)[1]
        app = current_app._get_current_object()
        if file_ext not in app.config['ALLOWED_EXTENSIONS']:
            return {'status':'failed'}
        filename = str(int(datetime.now().timestamp()))+"_"+filename
        uploaded_file.save(os.path.join(app.config['UPLOAD_DEST'], filename))
        return {'status':'success', 'file':filename}
    return {'status': 'failed'}

def remove_photo(photo):
    if photo and photo != 'avatar.png':
        try:
            app = current_app._get_current_object()
            os.remove(os.path.join(app.config.get('UPLOAD_DEST'), photo))
            return {'status':'success'}
        except Exception as e:
            print(e)
    return {'status':'failed'}

def upload_pdf(uploaded_file):
    filename = secure_filename(uploaded_file.filename)
    if filename != '':
        file_ext = os.path.splitext(filename)[1]
        app = current_app._get_current_object()
        if file_ext != '.pdf':
            return {'status':'failed'}
        filename = str(int(datetime.now().timestamp()))+"_"+filename
        uploaded_file.save(os.path.join(app.config['PDF_UPLOAD_DEST'], filename))
        return {'status':'success', 'file':filename}
    return {'status': 'failed'}

def remove_pdf(file):
    if file and file != 'careplan.pdf':
        try:
            app = current_app._get_current_object()
            os.remove(os.path.join(app.config.get('PDF_UPLOAD_DEST'), file))
            return {'status':'success'}
        except Exception as e:
            print(e)
    return {'status':'failed'}