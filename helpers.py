import os
import base64
import boto3
import math
import mysql.connector
import schedule
import secrets
import time

from datetime import datetime
from flask import Flask, redirect, render_template, request, session
from functools import wraps

# Configure flask
app = Flask(__name__)

admin_account = "GCLMA7L4TWKF2NZYKT3W5OZCJ6IBLLPN3P7Q5JRFRTV3FRMCR3BEGYQR"
categories_list = ["Books", "Games", "Music", "Technology", "All"]
status_list = ["Active", "Fund", "Refund", "Successful", "Unsuccessful"]
sort_list = ["Category", "Name", "Status", "All"]

db_host = os.environ['DB_HOST']
db_port = os.environ['DB_PORT']
db_user = os.environ['DB_USER']
db_password = os.environ['DB_PASSWORD']
db_name = os.environ['DB_NAME']


conn = mysql.connector.connect(
    host=db_host,
    user=db_user,
    password=db_password,
    database=db_name,
    port=db_port
)


def format_date(date, date_type):

    # Dates with time are inserted on database
    if date_type == "long_datetime_db":
        dt = datetime.strptime(date, "%Y-%m-%d")
        new_date = dt.replace(hour=23, minute=59, second=59)

    # Medium dates are shown on client side
    elif date_type == "medium_string":
        new_date = date.strftime("%d/%m/%Y")
    elif date_type == "long_datetime":
        new_date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")

    return new_date


def calculate_project_progress(projects_list):
    """ Calculate percentage of funding progress """
    
    try:
        projects_list = get_total_donations(projects_list)
        for project in projects_list:
            project["funding_progress"] = f'{math.floor(project["total_donations"] / project["goal"] * 100)}%'
        
        return projects_list

    except Exception as e:
        print("An error occurred calculating project progress:", str(e))
        return None


def get_total_donations(projects_list):

    db = conn.cursor(dictionary=True)

    try:
        for project in projects_list:

            # Get total amount of donations
            query = "SELECT SUM(amount) as donations FROM transactions WHERE project_id = %s AND type = %s"
            params = (project["project_id"], "donation")
            db.execute(query, params)

            total_donations = db.fetchone()["donations"] or 0
            project["total_donations"] = total_donations

    except Exception as e:
        print("An error occurred searching total donations:", str(e))
    
    finally:
        db.close()
    
    return projects_list
    


def get_const_list(const_list):
    """ Get constant list os default values """

    if const_list == "category":
        const_list = categories_list
    
    elif const_list == "status":
        const_list = status_list

    return const_list


def generate_project_id():

    db = conn.cursor()
    project_id = 1

    try:
        db.execute("SELECT id FROM projects")
        results = db.fetchall()
        ids_list = [row[0] for row in results]
        while project_id in ids_list:
            project_id += 1
    
    except Exception as e:
        print(f"Error trying to generate new id: {e}")
    
    finally:
        db.close()
    
    return project_id


def run_schedule():
    # TO DO: Finish

    schedule.every().day.at("02:00").do(update_database_status)

    while True:
        schedule.run_pending()
        time.sleep(60)


""" VALIDATION """

def check_amount(value):
    """ Check for valid amount input"""

    try:
        int_value = int(value)
    
    except:
        return False
    
    if not isinstance(int_value, int) or (int_value <= 0):
        return False
    
    return True


def check_projects_action(projects_list, project_ids, operation_type):
    """ Check if projects selected by admin have the same status as operation required """

    projects_checked = []
    for project in projects_list:
        if project["project_id"] in project_ids and project["status"] == operation_type:
            projects_checked.append(project)

    return projects_checked


def validate_input(project):
    # TO DO: Change it, too many if's 

    for key, value in project.items():
        if not value:
            return f"Field {key} is empty."
        
        if key in ["category", "status"]:
            accepted_values = get_const_list(key)
            if value not in accepted_values:
                return f"Value '{value}' is not a valid  {key}."

        if key == "goal" and not check_amount(value):
            return f"Value '{value}' is not a valid {key}."

        if key == "expire_date" and value < datetime.today():
            return f"Please provide an expiration date that has not passed yet."

    return True


""" SEARCH """

def search_donations_history(name="", category="", status=""):
    """ Search for detailed donatioapologns history to display on myaccount """

    db = conn.cursor(dictionary=True)
    
    query = (
        "SELECT t.project_id, p.name, p.category, t.amount, t.timestamp, t.hash FROM transactions t "
        "JOIN projects p ON t.project_id = p.id "
        "WHERE t.public_key_sender = %s AND type = %s AND name LIKE %s AND category LIKE %s AND status LIKE %s"
    )
    params = (session["public_key"], "donation", "%" + name + "%", "%" + category + "%", "%" + status + "%")
    db.execute(query, params)

    projects_list = db.fetchall()
    db.close()

    for project in projects_list:
        project["timestamp"] = format_date(project["timestamp"], "medium_string")

    return projects_list


def clean_filter_value(value):
    if value.lower() == "all":
        return ""
    return value

def search_projects(name="", category="", status="", id=""):
    """ Search projects data and total donations.
     Parameters are optional, returning all projects if none is passed """

    # TO DO: Change this, too long

    projects_list = []
    db = conn.cursor(dictionary=True)

    # Clean filter values
    category = clean_filter_value(category)
    status = clean_filter_value(status)

    if not id:
        query = (
            "SELECT id AS project_id, name, category, status, public_key, expire_date, goal, image_path, description FROM projects "
            "WHERE name LIKE %s AND category LIKE %s AND status LIKE %s ORDER BY status"
        )
        params = ("%" + name + "%", "%" + category + "%", "%" + status + "%")
    
    else:
        query = (
            "SELECT id AS project_id, name, category, status, public_key, expire_date, goal, image_path, description FROM projects "
            "WHERE name LIKE %s AND category LIKE %s AND status LIKE %s AND id = %s ORDER BY status"
        )
        params = ("%" + name + "%", "%" + category + "%", "%" + status + "%", id)

    db.execute(query, params)
    
    projects_list = db.fetchall()
    db.close()

    for project in projects_list:

        # Calculate remaining active project days
        if project["status"] == "active":

            days_remaining = project["expire_date"] - datetime.today()
            days_left = days_remaining.days
            if days_left == 0:
                project["days_left"] = "last day"
            elif days_left == 1:
                project["days_left"] = "{} day left".format(days_left)
            else:
                project["days_left"] = "{} days left".format(days_left)
        else:
            project["days_left"] = 0

        project["expire_date"] = format_date(project["expire_date"], "medium_string")

    return calculate_project_progress(projects_list)


def search_refund_operations(projects_list):

    refundable_projects = []
    db = conn.cursor(dictionary=True)
    
    
    for project in projects_list:

        query = (
            "SELECT project_id, public_key_sender AS public_key, SUM(amount) AS total_donations "
            "FROM transactions WHERE project_id = %s AND type = %s GROUP BY public_key_sender"
        )
        params = (project["project_id"], "donation")
        db.execute(query, params)
        doners_operations = db.fetchall()
        
        for operation in doners_operations:
            operation["name"] = project["name"]

        refundable_projects.extend(doners_operations)

    db.close()

    return refundable_projects


def search_supported_projects():
    """ Search for projects supported by user """

    db = conn.cursor(dictionary=True)

    query = (
        "SELECT t.project_id, p.name, p.category, p.status, p.goal, SUM(amount) AS your_donations FROM transactions t "
        "JOIN projects p ON t.project_id = p.id "
        "WHERE t.public_key_sender = %s AND t.type = %s GROUP BY t.project_id ORDER BY status"
    )
    params = (session["public_key"], "donation")
    db.execute(query, params)
    projects_list = db.fetchall()
    
    db.close()

    return calculate_project_progress(projects_list)


""" UPDATE DB """

def update_database_status():
    """ Updates project's status when expired.
    From active to: fund, refund or unsuccessful """

    try:
        db = conn.cursor(dictionary=True)
        db.execute("SELECT id AS project_id, expire_date, goal FROM projects WHERE status = 'active'")
        projects_list = db.fetchall()
        projects_list = get_total_donations(projects_list)

        for project in projects_list:

            # Update status of expired projects
            if project["expire_date"] < datetime.today():

                # Projects that achieved their funding goal will be funded by admin
                if project["total_donations"] >= project["goal"]:
                    db.execute("UPDATE projects SET status = %s WHERE id = %s", ("fund", project["project_id"]))

                # Projects with no amount of donations pass directly to unsuccessful
                elif project["total_donations"] == 0:
                    db.execute("UPDATE projects SET status = %s WHERE id = %s", ("unsuccessful", project["project_id"]))

                # Projects that didn't achieve their funding goal will have their donations returned to backers
                else:
                    db.execute("UPDATE projects SET status = %s WHERE id = %s", ("refund", project["project_id"]))

    except Exception as e:
        conn.rollback()
        print(f"An error occurred trying to update status: {e}")
    
    finally:
        db.close() 


def update_transactions_database(hash):
    """ Updates transactions table with donation data and project status after admin fund / refund projects"""

    try:
        db = conn.cursor(dictionary=True)
        db.execute("SELECT * FROM temp_operations")
        temp_table = db.fetchall()

        for operation in temp_table:
            if operation["type"] == "donation":
                public_key_sender = session["public_key"]
                public_key_receiver = admin_account
            
            else:
                public_key_sender = admin_account
                public_key_receiver = operation["destination_account"]
                
                if operation["type"] == "fund":
                    operation["new_status"] = "successful"
                
                else:
                    operation["new_status"] = "unsuccessful"
                
                query = "UPDATE projects SET status = %s WHERE id = %s"
                params = (operation["new_status"], operation["project_id"])
                db.execute(query, params)

            query = "INSERT INTO transactions (project_id, amount, public_key_sender, public_key_receiver, hash, type) VALUES(%s, %s, %s, %s, %s, %s)"
            params = (operation["project_id"], operation["amount"], public_key_sender, public_key_receiver, hash, operation["type"])
            db.execute(query, params)

        conn.commit()
    
    except Exception as e:
        conn.rollback()
        print(f"An error occurred trying to update transactions: {e}")
    
    finally:
        db.close()


def upload_image(base64_img):
    """ Uploads the image on database """
    
    # Decode to bytes avoiding padding error
    try:
        image_str = base64_img.split(",")[1]
        image_bytes = base64.b64decode(image_str + "==")

        # Generate a secure filename
        random_hex = secrets.token_hex(8)
        filename = random_hex + ".png"

        bucket_name = 'cf-img-uploads'
        s3_client = boto3.client('s3')
        s3_client.put_object(Bucket='cf-img-uploads', Key=filename, Body=image_bytes, ContentType='image/png')
        file_url = f"https://{bucket_name}.s3.amazonaws.com/{filename}"

        return file_url

    except Exception as e:
        print(e)
        return e


def apology(message, code=400):
    """Render message as an apology to user."""

    referrer = request.headers.get("Referer")
    return render_template("apology.html", top=code, bottom=message, referrer=referrer)


def freighter_required(f):
    """ Decorate routes to require user's connection with freighter."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("public_key") is None:
            return redirect("/")
        return f(*args, **kwargs)
    return decorated_function
