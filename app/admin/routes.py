from email import message
from flask import render_template, redirect, request, session, url_for, flash, current_app
from flask_login import login_required, current_user
from dateutil import relativedelta
from datetime import datetime
from collections import Counter
from . import admin
from ..models import db, User, Messages, Role, Resident, ActivityGroup, Activity, Kitchen, Maintenance, Timeline
from ..methods import send_email, delete_item, trash_item, upload_photo, remove_photo

import math

@admin.route('/index')
@login_required
def index():
    from_login = request.args.get('logged_in')
    #get distribuion of staff by role
    users = User.query.all()
    jobs = [user.role.name for user in users]
    role_dist = Counter(jobs)

    #get distribuion of Residents by registration date in the form Year Q#
    residents = Resident.query.all()
    admission_YQ = [str(resident.admission_date.year)+" Q"+str(math.ceil(resident.admission_date.month/3)) for resident in residents]
    admission_YQ_dist = Counter(admission_YQ)

    num_staff=User.query.count()  
    num_residents=Resident.query.count()  
    repairs_count = Maintenance.query.count() 
    repairs_completed = Maintenance.query.filter(Maintenance.status=='Fixed').count() 
    repairs_completion_rate = round((repairs_completed/repairs_count)*100, 1)
    low_kitchen_items = Kitchen.query.filter(Kitchen.quantity_left<Kitchen.safe_quantity).count()
    return render_template('admin/index.html', user=current_user, from_login=from_login, low_kitchen_items=low_kitchen_items,
            num_staff=num_staff, num_residents=num_residents, repairs_completion_rate=repairs_completion_rate,
            role_dist=role_dist, admission_YQ_dist=admission_YQ_dist)

@admin.route('/compose', methods=['GET', 'POST'])
@login_required
def compose():
    if request.method == 'POST':
        users =  User.query.filter().order_by(User.name)
        message_target = request.form.get('recipients')
        subject = request.form.get('subject')
        content = request.form.get('content')
        if message_target=="Select":
            recipient_ids = request.form.getlist('multi_recipients')
            recipient_names =[user.name for user in users if str(user.id) in recipient_ids]

        else:
            recipient_ids =[user.id for user in users if user!= current_user]
            recipient_names =[user.name for user in users if user!= current_user]
        recipient_ids = '|'+'|'.join(map(str, recipient_ids))+'|'
        recipient_names = '|'.join(recipient_names)
        message = Messages(
        subject=subject, message=content, sender_id=current_user.id, recipients=recipient_names, recipient_ids=recipient_ids)
        db.session.add(message)
        db.session.commit()
        flash('Message sent successfully', category='success')
        return redirect(url_for('.compose'))
    users =  User.query.filter().order_by(User.name)
    return render_template('admin/pages/mailbox/compose.html', user=current_user, users=users)

@admin.route('/inbox', methods=['GET', 'POST'])
@login_required
def inbox():
    if request.method == 'POST':
        msg_ids = request.form.get('msgIDs')
        if msg_ids:
            for id in msg_ids:
                trash_msg=Messages.query.get(id)
                trash_msg.is_trashed = True
                trash_msg.trashed_by_id = '|'+current_user.get_id()+'|' if trash_msg.trashed_by_id== '' else trash_msg.trashed_by_id+current_user.get_id()+'|'
                db.session.add(trash_msg)
                db.session.commit()
            flash('Message moved to trash')
            return redirect(url_for('.inbox'))
            
        else:
            flash('No Messages Selected', category='error')
        return redirect(url_for('.inbox'))
    page = request.args.get('page', 1, type=int)
    in_messages = Messages.query.filter(~Messages.deleted_by_id.contains('|'+current_user.get_id()+'|'), ~Messages.trashed_by_id.contains('|'+current_user.get_id()+'|'), Messages.recipient_ids.contains('|'+current_user.get_id()+'|')).order_by(Messages.date_time.desc()).paginate(
        page,  current_app.config['ITEMS_PER_PAGE'], True
    )
    prev_url = None
    if in_messages.has_prev:
        prev_url = url_for('admin.inbox', page=page-1)
    next_url = None
    if in_messages.has_next:
        next_url = url_for('admin.inbox', page=page+1)
    users =  User.query
    return render_template('admin/pages/mailbox/inbox.html', user=current_user, users=users,
                           in_messages=in_messages, next_url=next_url, prev_url=prev_url, curr_page=page
                           )


@admin.route('/sent', methods=['GET', 'POST'])
@login_required
def sent():
    if request.method == 'POST':
        msg_ids = request.form.get('msgIDs')
        if msg_ids:
            for id in msg_ids:
                trash_msg=Messages.query.get(id)
                trash_msg.is_trashed = True
                trash_msg.trashed_by_id = '|'+current_user.get_id()+'|' if trash_msg.trashed_by_id== '' else trash_msg.trashed_by_id+current_user.get_id()+'|'
                db.session.add(trash_msg)
                db.session.commit()
            flash('Messages moved to trash')
            return redirect(url_for('.sent'))

        else:
            flash('No Message Selected')
        return redirect(url_for('.sent'))
    page = request.args.get('page', 1, type=int)
    out_messages = Messages.query.filter(~Messages.deleted_by_id.contains('|'+current_user.get_id()+'|'), ~Messages.trashed_by_id.contains('|'+current_user.get_id()+'|'), Messages.sender_id==current_user.id).order_by(Messages.date_time.desc()).paginate(
        page,  current_app.config['ITEMS_PER_PAGE'], True
    )
    prev_url = None
    if out_messages.has_prev:
        prev_url = url_for('.sent', page=page-1)
    next_url = None
    if out_messages.has_next:
        next_url = url_for('.sent', page=page+1)
    users =  User.query.filter().order_by(User.name)
    return render_template('admin/pages/mailbox/sent_mail.html', user=current_user, users=users,
                           out_messages=out_messages, next_url=next_url, prev_url=prev_url, curr_page=page
                           )


@admin.route('/trash/<msg_id>')
@admin.route('/trash', methods=['GET', 'POST'])
@login_required
def trash(msg_id=None):
    if msg_id:
        delete = delete_item(msg_id, 'messages')
        if delete == True:
            flash('Message Successfully Deleted')
        else:
            flash(f'Messages cannot be deleted', category='error')
        return redirect(url_for('.trash'))        

    if request.method == 'POST':
        msg_ids = request.form.get('msgIDs', None)
        if msg_ids:
            for id in msg_ids:
                msg = Messages.query.get(id)
                if msg.deleted_by_id=='':
                    msg.deleted_by_id = "|"+current_user.get_id()+"|"
                else:
                    msg.deleted_by_id = msg.trashed_by_id + current_user.get_id() + "|"
                    
                db.session.add(msg)
                db.session.commit()
            flash('Message successfully deleted')

        restore_msg_ids = request.form.get('restore_msgIDs', None)
        if restore_msg_ids:
            for id in restore_msg_ids:
                msg = Messages.query.get(id)
                msg.trashed_by_id = msg.trashed_by_id.replace("|"+current_user.get_id()+"|", "|")
                db.session.add(msg)
                db.session.commit()
            flash('Messages successfully moved from trash')
        return redirect(url_for('.trash'))
    page = request.args.get('page', 1, type=int)
    in_messages = Messages.query.filter(Messages.is_trashed == True, Messages.trashed_by_id.contains('|'+current_user.get_id()+'|'), 
    ~Messages.deleted_by_id.contains('|'+current_user.get_id()+'|')).order_by(Messages.date_time.desc()).paginate(
        page,  current_app.config['ITEMS_PER_PAGE'], True
    )
    prev_url = None
    if in_messages.has_prev:
        prev_url = url_for('admin.inbox', page=page-1)
    next_url = None
    if in_messages.has_next:
        next_url = url_for('admin.inbox', page=page+1)
    users = User.query
    return render_template('admin/pages/mailbox/trash.html', user=current_user, users=users,
                           in_messages=in_messages, next_url=next_url, prev_url=prev_url, curr_page=page
                           )


@admin.route('/reply/<msg_id>', methods=['GET', 'POST'])
@login_required
def reply(msg_id=None):
    if request.method == 'POST':
        subject = request.form.get('subject')
        recipient_name = request.form.get('sender_name')
        recipient_id = request.form.get('sender_id')
        content = request.form.get('content')
        message = Messages(
        subject=subject, message=content, sender_id=current_user.id, recipients=recipient_name, recipient_ids=recipient_id)
        db.session.add(message)
        db.session.commit()
        flash(f'Reply Sent to {recipient_name}', category='success')
        
        return redirect(url_for('.inbox'))
    users = User.query
    message = Messages.query.filter_by(id=msg_id).first()
    return render_template('admin/pages/mailbox/reply.html', user=current_user, message=message, users=users)


@admin.route('/read/<delete>/<source>/<del_msg_id>')
@admin.route('/read/<source>/<int:msg_id>')
@login_required
def read(source, delete=None, msg_id=None, del_msg_id=None):
    if del_msg_id:
        if source=='inbox':
            delete = trash_item(del_msg_id, 'messages')
        else:
            delete = trash_item(del_msg_id, 'messages')
        if delete == True:
            flash('Message successfully deleted')
        else:
            flash(f'Unable to delete message due to {delete}', category='error')
        delete = None
        return redirect(url_for('.inbox'))        
    if source == 'inbox':
        message = Messages.query.get_or_404(msg_id)
    elif source=='trash':
        message = Messages.query.get_or_404(msg_id)
    else:
        message = Messages.query.get_or_404(msg_id)
    users = User.query
    return render_template('admin/pages/mailbox/read_mail.html', source=source, user=current_user, message=message, users=users)


@admin.route('register', methods=['GET', 'POST'])
@login_required
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name').title()
        email = request.form.get('email').lower()
        username = request.form.get('username').lower()
        role = Role.query.get(request.form.get('role'))

        email_check = User.query.filter_by(email=email).first()
        if email_check:
            flash('Email already registered')
        uname = User.query.filter_by(username=username).first()
        if uname:
            flash('This username is already taken', category='error')
        
        if email_check or uname:
            return redirect(url_for('.register'))
        
        user = User(email=email, 
        name=full_name, 
        username=username, 
        role=role, 
        password='admin')
        db.session.add(user)
        db.session.commit()

        token = user.generate_confirmation_token()
        send_email(user.email, 'Confirm Your Account',
                   'auth/email/confirm', user=user, token=token)
        flash('A confirmation email has been sent the user by email.')
        return redirect(url_for('.register'))
    roles = Role.query.all()
    return render_template('admin/pages/users/register.html', user=current_user, roles=roles)


@admin.route('view-user', methods=['GET', 'POST'])
@login_required
def view_users():

    page = request.args.get('page', 1, type=int)
    users = User.query.join(Role).paginate(
        page,  current_app.config['ITEMS_PER_PAGE'], True
    )
    prev_url = None
    if users.has_prev:
        prev_url = url_for('admin.view_users', page=page-1)
    next_url = None
    if users.has_next:
        next_url = url_for('admin.view_users', page=page+1)

    return render_template('admin/pages/users/view.html', user=current_user,
                           users=users, next_url=next_url, prev_url=prev_url, curr_page=page
                           )


@admin.route('edit-user/<user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if request.method == 'POST':
        new_role = request.form.get('role')
        name = request.form.get('full_name')
        email = request.form.get('email')
        username = request.form.get('username')
        user = User.query.get_or_404(user_id)
        user.role_id = new_role     
        user.name = name     
        user.email = email     
        user.username = username     
        db.session.add(user)
        db.session.commit()
        flash('Profile successfully updated', category='success')
        return redirect(url_for('.edit_user', user_id=user_id))
    user_profile = User.query.join(Role).filter(User.id == user_id).first()
    roles = Role.query.all()
    return render_template('admin/pages/users/edit_user.html', user=current_user, roles=roles, user_profile=user_profile)


@admin.route('delete-user/<user_id>')
@login_required
def delete_user(user_id):
    if user_id!=current_user.id:
        user_del = User.query.get_or_404(user_id)
        db.session.delete(user_del)
        db.session.commit()
        flash('User successfully deleted')
        return redirect(url_for('.view_users'))
    return render_template('admin/pages/users/view.html', user=current_user)


@admin.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_password = request.form.get('old_pass')
        new_password = request.form.get('new_pass')
        confirm_password = request.form.get('confirm_pass')
        if current_user.verify_password(old_password):
            if new_password == confirm_password:
                current_user.password = new_password
                db.session.add(current_user)
                db.session.commit()
                flash('Your password has been updated. Login!')
                return redirect(url_for('auth.login'))
            else:
                flash('New password and confirmation mismatch.', category='error')
        else:
            flash('Invalid password.', category='error')
        return redirect(url_for('.change_password'))
    return render_template("admin/change-password.html", user=current_user)

@admin.route('/change-user-photo/<user_id>', methods=['GET','POST'])
@login_required
def change_user_photo(user_id):
    photo = request.files['photo']
    file_upload = upload_photo(photo)
    if file_upload["status"]== "failed":
        flash(f"File does not meet requirement{file_upload['file']}", category='error')
        return redirect(url_for('.index'))  
    file_name = file_upload["file"]
    user = User.query.get_or_404(user_id)
    remove_photo(user.profile_photo) #remove old photo
    user.profile_photo = file_name
    db.session.add(user)
    db.session.commit()
    return render_template('admin/index.html', user=current_user)

@admin.route('add_resident', methods=['GET', 'POST'])
@login_required
def add_resident():
    if request.method == 'POST':
        full_name = request.form.get('full_name').title()
        gender = request.form.get('gender')
        marital_status = request.form.get('marital_status')
        dob = datetime.strptime(request.form.get('dob'), '%d/%m/%Y')
        biography = request.form.get('biography')
        ethnicity = request.form.get('ethnicity')
        photo = request.files['photo']
        abilities = request.form.get('abilities')
        allergies = request.form.get('allergies')
        diet = request.form.get('diet')
        medical_condition = request.form.get('medical_condition')
        nok_name = request.form.get('nok_name').title()
        nok_email = request.form.get('nok_email').lower()
        nok_phone = request.form.get('nok_phone')
        care_address = request.form.get('care_address')
        admission_date = datetime.strptime(request.form.get('doa'), '%d/%m/%Y')
        residence_type = request.form.get('residence_type')
        file_upload = upload_photo(photo)
        if file_upload["status"]== "failed":
            flash(f"File does not meet requirement{file_upload['file']}", category='error')
            return redirect(url_for('.add_resident'))  
        file_name = file_upload["file"]          
        resident = Resident(name=full_name, gender=gender, marital_status=marital_status, dob=dob,
                            biography=biography, ethnicity=ethnicity, profile_photo=file_name, abilities=abilities, allergies=allergies,
                            diet=diet, medical_condition=medical_condition, nok_name=nok_name, nok_email=nok_email,
                             nok_phone=nok_phone, care_address=care_address, admission_date=admission_date, resident_type=residence_type
                            )
        db.session.add(resident)
        db.session.commit()

    return render_template('admin/pages/residents/add_resident.html', user=current_user)

@admin.route('view-residents', methods=['GET'])
@login_required
def view_residents():

    page = request.args.get('page', 1, type=int)
    residents = Resident.query.paginate(
        page,  current_app.config['ITEMS_PER_PAGE'], True
    )
    prev_url = None
    if residents.has_prev:
        prev_url = url_for('admin.view_residents', page=page-1)
    next_url = None
    if residents.has_next:
        next_url = url_for('admin.view_residents', page=page+1)

    return render_template('admin/pages/residents/view_residents.html', user=current_user,
                           residents=residents, next_url=next_url, prev_url=prev_url, curr_page=page
                           )

@admin.route('view-resident-profile/<resident_id>', methods=['GET'])
@login_required
def view_resident_profile(resident_id):
    resident = Resident.query.get_or_404(resident_id)
    age = relativedelta.relativedelta(datetime.now().date(), resident.dob).years
    groups =  ActivityGroup.query.filter().order_by(ActivityGroup.time)
    return render_template('admin/pages/residents/view_resident_profile.html', user=current_user, resident=resident, age=age, groups=groups)

@admin.route('edit-resident/<resident_id>', methods=['GET', 'POST'])
@login_required
def edit_resident(resident_id):
    resident = Resident.query.get_or_404(resident_id)
    if request.method == 'POST':
        full_name = request.form.get('full_name').title()
        gender = request.form.get('gender')
        marital_status = request.form.get('marital_status')
        dob = datetime.strptime(request.form.get('dob'), '%d/%m/%Y')
        biography = request.form.get('biography')
        ethnicity = request.form.get('ethnicity')
        abilities = request.form.get('abilities')
        allergies = request.form.get('allergies')
        diet = request.form.get('diet')
        medical_condition = request.form.get('medical_condition')
        nok_name = request.form.get('nok_name').title()
        nok_email = request.form.get('nok_email').lower()
        nok_phone = request.form.get('nok_phone')
        care_address = request.form.get('care_address')
        admission_date = datetime.strptime(request.form.get('doa'), '%d/%m/%Y')
        residence_type = request.form.get('residence_type')

        resident.name = full_name
        resident.gender = gender 
        resident.marital_status = marital_status
        resident.dob = dob
        resident.biography = biography
        resident.ethnicity = ethnicity
        resident.abilities = abilities 
        resident.allergies = allergies
        resident.diet = diet
        resident.medical_condition = medical_condition
        resident.nok_name = nok_name
        resident.nok_email = nok_email
        resident.nok_phone = nok_phone
        resident.care_address = care_address
        resident.admission_date = admission_date
        resident.residence_type = residence_type

        db.session.add(resident)
        db.session.commit()
        flash('Profile successfully updated', category='success')
        return redirect(url_for('.edit_resident', resident_id=resident_id))

    return render_template('admin/pages/residents/edit_resident.html', user=current_user, resident=resident)

@admin.route('/change-resident-photo/<resident_id>', methods=['GET','POST'])
@login_required
def change_resident_photo(resident_id):
    photo = request.files['new_photo']
    file_upload = upload_photo(photo)
    if file_upload["status"]== "failed":
        flash(f"File does not meet requirement{file_upload['file']}", category='error')
        return redirect(url_for('.view_resident_profile'))  
    file_name = file_upload["file"]
    resident = Resident.query.get_or_404(resident_id)
    remove_photo(resident.profile_photo) #remove old photo
    resident.profile_photo = file_name
    db.session.add(resident)
    db.session.commit()
    groups =  ActivityGroup.query.filter().order_by(ActivityGroup.time)
    age = relativedelta.relativedelta(datetime.now().date(), resident.dob).years
    return render_template('admin/pages/residents/view_resident_profile.html', user=current_user, resident=resident, age=age, groups=groups)

@admin.route('/app-settings', methods=['GET', 'POST'])
@login_required
def app_settings():
    if request.method=='POST':
        new_group = request.form.get('new_group', None)
        if new_group:
            new_group =new_group.title()
            time = request.form.get('time')
            group_check = ActivityGroup.query.filter_by(group_name=new_group).first()
            time_check = ActivityGroup.query.filter_by(time=time).first()
            
            if group_check:
                flash(f'The Group name <b>{new_group}</b> already exists', category='error')
            elif time_check:
                flash(f'An activity group is already created for the time <b>{time}</b>', category='error')
            else:
                group = ActivityGroup(group_name=new_group, time=time)            
                db.session.add(group)
                db.session.commit()
                flash(f'Added new group {new_group}', category='success')
            return redirect(url_for('.app_settings'))

        delete_group_id = request.form.get('delete_group_id', None)
        if delete_group_id:
            group = ActivityGroup.query.filter(ActivityGroup.id==int(delete_group_id))
            group.delete()
            db.session.commit()
            flash('Group successfully deleted', category='success')
            return redirect(url_for('.app_settings'))

        edit_group_id = request.form.get('edit_group_id', None)
        if edit_group_id:
            group = ActivityGroup.query.get_or_404(edit_group_id)
            group.group_name = request.form.get('edit_group_name').title()
            group.time = request.form.get('edit_group_time')
            db.session.add(group)
            db.session.commit()
            flash('Group successfully edited', category='success')
            return redirect(url_for('.app_settings'))
        
        new_activity_name = request.form.get('new_activity', None)
        if new_activity_name:
            new_activity_name = new_activity_name.title()
            options_type = request.form.get('options_type')
            groups_id = request.form.getlist('multi_groups')
            options = request.form.getlist('option[]')
            options = "|".join(options)
            new_activity = Activity(act_name=new_activity_name, selection_type=options_type, options=options)
            db.session.add(new_activity)
            db.session.commit()

            for id in groups_id:
                group = ActivityGroup.query.get_or_404(id)
                new_activity.act_group.append(group)
                db.session.add(new_activity)
                db.session.commit()
            flash('Activity added succefully', category='success')
            return redirect(url_for('.app_settings'))

        activity_id_edit = request.form.get('edit_activity_id', None)
        if activity_id_edit:
            activity_name_edit = request.form.get('edit_activity_name').title()
            options_type = request.form.get('edit_options_type')
            groups_id = request.form.getlist('edit_multi_groups')
            options = request.form.getlist('option[]')
            options = "|".join(options)

            activity_edit = Activity.query.get_or_404(activity_id_edit)
            activity_edit.selection_type = options_type
            activity_edit.act_name = activity_name_edit
            activity_edit.options = options
            activity_edit.act_group.all().clear()#remove all groups
            for id in groups_id:
                group = ActivityGroup.query.get_or_404(id)                
                activity_edit.act_group.append(group)
            
            db.session.add(activity_edit)
            db.session.commit()
            flash('Activity Edited Succefully', category='success')
            return redirect(url_for('.app_settings'))

        delete_activity_id = request.form.get('delete_activity_id', None)
        if delete_activity_id:
            activity = Activity.query.filter(Activity.id==delete_activity_id)
            activity.delete()
            db.session.commit()
            flash('Activity Successfully Deleted', category='success')
            return redirect(url_for('.app_settings'))

    title = "App Settings"
    groups =  ActivityGroup.query.filter().order_by(ActivityGroup.time)
    activities = Activity.query.filter()
    return render_template('admin/pages/settings/app_settings.html', user=current_user, title=title, groups=groups, activities=activities)

@admin.route('/timeline/<group_id>/<resident_id>', methods=['GET', 'POST'])
@login_required
def timeline(group_id, resident_id):
    group =  ActivityGroup.query.get(group_id)
    resident = Resident.query.get(resident_id)
    if request.method == 'POST':
        date_submit = request.form.get('decoy_dok', None)
        if date_submit:
            entry_date = datetime.date(datetime.strptime(request.form.get('dok'), '%d-%m-%Y'))
            timeline_today = Timeline.query.filter(Timeline.activity_group_id==group_id,  
                                Timeline.date==entry_date, Timeline.resident_id==resident_id).first()
            return render_template('admin/pages/residents/timeline.html', user=current_user, resident=resident, group=group, entry_timeline=timeline_today, entry_date=entry_date)
        
        form_submit = request.form.get('decoy_dob', None)
        if form_submit:
            entry_date = request.form.get('dob')
            #make date today if no date picked
            entry_date = datetime.date(datetime.now())if entry_date=='' else datetime.date(datetime.strptime(entry_date, '%Y-%m-%d'))
            group_activities = group.activity.all()
            activity_ids = [activity.id for activity in group_activities]
            activity_ids = "|".join(map(str, activity_ids))
            results = request.form.getlist('act_name')
            results= "|".join(results)

            timeline_exists = Timeline.query.filter(Timeline.activity_group_id==group_id,  
                                Timeline.date==entry_date, Timeline.resident_id==resident_id).first()
            if timeline_exists:
                timeline_exists.activity_id = activity_ids
                timeline_exists.action=results
                timeline_exists.user_entry_id = current_user.id
                db.session.add(timeline_exists)
                db.session.commit()
            else:
                new_timeline = Timeline(activity_group_id=group_id, activity_id=activity_ids, date=entry_date,
                                    action=results, resident_id=resident.id, user_entry_id=current_user.id)
                db.session.add(new_timeline)
                db.session.commit()
            age = relativedelta.relativedelta(datetime.now().date(), resident.dob).years
            groups =  ActivityGroup.query.filter().order_by(ActivityGroup.time)
        return render_template('admin/pages/residents/view_resident_profile.html', user=current_user, resident=resident, age=age, groups=groups)
   
    timeline_today = Timeline.query.filter(Timeline.date==datetime.date(datetime.now()),
                    Timeline.activity_group_id==group_id, Timeline.resident_id==resident_id).first()
    return render_template('admin/pages/residents/timeline.html', user=current_user, resident=resident, group=group, entry_timeline=timeline_today)

@admin.route('/maintenance', methods=['GET', 'POST'])
@login_required
def maintenance():
    if request.method == "POST":
        location = request.form.get('loc_name', None)
        if location:
            issue = request.form.get('issue')
            maintenance = Maintenance(location=location, issue=issue, reported_by=current_user.id, status="Submitted")
            db.session.add(maintenance)
            db.session.commit()
            flash(f'Issue at <b>{location}</b> successfully submitted')
            return redirect(url_for('.maintenance')) 
        
    title = "Maintenance"
    requests = Maintenance.query.filter(Maintenance.reported_by==current_user.id).order_by(Maintenance.report_date)
    return render_template('admin/pages/maintenance/request.html', user=current_user, requests=requests, title=title)

@admin.route('/maintenance-view', methods=['GET', 'POST'])
@login_required
def maintenance_view():
    if request.method == "POST":
        issue_id = request.form.get('request_id', None)
        if issue_id:
            status = request.form.get('status')
            issue = Maintenance.query.get(issue_id)
            issue.status = status
            db.session.add(issue)
            db.session.commit()
            flash(f'Issue status successfully updated')
            return redirect(url_for('.maintenance_view')) 
        
    title = "Maintenance Requests"
    requests = Maintenance.query.join(User, Maintenance.reported_by==User.id).filter().order_by(Maintenance.report_date)
    return render_template('admin/pages/maintenance/all_requests.html', user=current_user, requests=requests, title=title)

@admin.route('/kitchen', methods=['GET', 'POST'])
@login_required
def kitchen(): 
    if request.method=='POST':
        new_item = request.form.get('new_item', None)
        if new_item:
            name_check = Kitchen.query.filter_by(item=new_item).first()
            
            if name_check:
                flash(f'The item name <b>{new_item}</b> already exists', category='error')
            
            else:
                quantity = request.form.get('quantity')
                ideal_quantity = request.form.get('ideal_quantity')
                location = request.form.get('location')
                kitchen = Kitchen(item=new_item, quantity_left=quantity, safe_quantity=ideal_quantity, location=location)            
                db.session.add(kitchen)
                db.session.commit()
                flash(f'Added new item {new_item}', category='success')
            return redirect(url_for('.kitchen'))

        edit_item_id = request.form.get('edit_item_id', None)
        if edit_item_id:
            kitchen_item = Kitchen.query.get_or_404(edit_item_id)
            quantity = request.form.get('quantity')
            ideal_quantity = request.form.get('ideal_quantity')
            location = request.form.get('location')
            
            new_item_name = request.form.get('new_item_name', None)
            name_check = Kitchen.query.filter_by(item=new_item_name).first()
            if name_check:
                flash(f'The item name <b>{new_item_name}</b> already exists', category='error')
                return redirect(url_for('.kitchen'))
            
            kitchen_item.item = new_item_name
            kitchen_item.quantity = quantity
            kitchen_item.safe_quantity = ideal_quantity
            kitchen_item.location = location

            db.session.add(kitchen_item)
            db.session.commit()
            flash('Item successfully edited', category='success')
            return redirect(url_for('.kitchen'))
        
        delete_item_id = request.form.get('delete_item_id', None)
        if delete_item_id:
            item = Kitchen.query.filter(Kitchen.id==int(delete_item_id))
            item.delete()
            db.session.commit()
            flash('Item successfully deleted', category='success')
            return redirect(url_for('.kitchen'))
    title = "Kitchen"
    items = Kitchen.query.filter().order_by(Kitchen.item)
    return render_template('admin/pages/kitchen/kitchen.html', user=current_user, items=items, title=title)