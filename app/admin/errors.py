from flask import render_template, flash, redirect
from . import admin
from flask_login import current_user

@admin.app_errorhandler(403)
def forbidden(e):
    return render_template('403.html', title='403 Error'), 403


@admin.app_errorhandler(404)
def page_not_found(e):
    return render_template('404.html', title='404 Error', user=current_user), 404


@admin.app_errorhandler(500)
def internal_server_error(e):
    return render_template('500.html', title='500 Error'), 500

@admin.app_errorhandler(413)
def request_entity_too_large(error):
    flash('File should be less than 1MB', category='error')
    return render_template('admin/pages/residents/add_resident.html', user=current_user), 413

