import os
from app import create_app, db
from app.models import User, Role, Resident, ActivityGroup, Activity, Messages, Maintenance, Timeline, Medication

app = create_app(os.getenv('FLASK_CONFIG') or 'default')

@app.shell_context_processor
def make_shell_context():
    return dict(db=db, User=User, Role=Role, Resident=Resident, Timeline=Timeline, Group=ActivityGroup, Activity=Activity, Messages=Messages, Maintenance=Maintenance, Med=Medication)