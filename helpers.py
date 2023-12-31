import base64
import boto3
import math
import secrets

from db_config import connection_pool
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session
from functools import wraps


app = Flask(__name__)

admin_account = "GCLMA7L4TWKF2NZYKT3W5OZCJ6IBLLPN3P7Q5JRFRTV3FRMCR3BEGYQR"
categories_list = ["Books", "Games", "Music", "Technology", "All"]
status_list = ["Active", "Fund", "Refund", "Successful", "Unsuccessful", "All"]
sort_list = ["Category", "Name", "Status", "All"]


def clean_filter_value(value):
    if value.lower() == "all":
        return ""
    return value


def format_date(date, date_type):

    # Dates with time are inserted on database
    if date_type == "long_datetime_db":
        dt = datetime.strptime(date, "%Y-%m-%d")
        new_date = dt.replace(hour=23, minute=59, second=59)

    # Medium dates are shown on client side
    elif date_type == "medium_string":
        new_date = date.strftime("%d/%m/%Y")

    return new_date


def get_const_list(const_list):
    """ Get lists of default values """

    if const_list == "category":
        const_list = categories_list
    
    elif const_list == "status":
        const_list = status_list

    return const_list


def get_total_donations(projects_list):

    connection = connection_pool.get_connection()
    db = connection.cursor(dictionary=True)

    total_donations = None
    try:
        query = "SELECT project_id, SUM(amount) as donations FROM transactions WHERE type = %s GROUP BY project_id"
        params = ("donation",)
        db.execute(query, params)
        total_donations = db.fetchall()

    except Exception as e:
        print("Error getting donations: ", str(e))

    finally:
        if connection.is_connected():
            db.close()
            connection.close()

    donations_dict = {item['project_id']: int(item['donations']) for item in total_donations}
    
    for project in projects_list:
        donations_from_transactions = donations_dict.get(project["project_id"], 0)
        project["total_donations"] = donations_from_transactions
    
    # Returns the received project list on exceptions
    return projects_list


def calculate_project_days_left(projects_list):
    """ Calculate remaining active project days """

    for project in projects_list:

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

    return projects_list


def calculate_project_progress(projects_list):
    """ Calculate percentage of funding progress """
    
    try:
        projects_list = get_total_donations(projects_list)
        for project in projects_list:
            project["funding_progress"] = f'{math.floor(project["total_donations"] / project["goal"] * 100)}%'
        
        return projects_list

    except Exception as e:
        print("Error calculating project progress: ", str(e))
        return None


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
    """ Check if projects selected by admin have the same status as operation required
     and return only the ones that fit. """

    projects_checked = []
    for project in projects_list:
        if project["project_id"] in project_ids and project["status"] == operation_type:
            projects_checked.append(project)

    return projects_checked


def validate_input(project):
    # TODO: Change it, too many if's

    for key, value in project.items():
        if not value and key != "name":
            return f"Field {key} is empty."
        
        if key in ["category", "status"]:
            accepted_values = get_const_list(key)
            if value not in accepted_values:
                return f"Value '{value}' is not a valid {key}."

        if key == "goal" and not check_amount(value):
            return f"Value '{value}' is not a valid {key}."

        if key == "expire_date" and value < datetime.today():
            return f"Past expiration dates are not allowed."

    return True


""" SEARCH """

def search_donations_history(name="", category="", status=""):
    """ Search for detailed donation history to display on my_donations """

    connection = connection_pool.get_connection()
    db = connection.cursor(dictionary=True)
    
    query = (
        "SELECT t.project_id, p.name, p.category, t.amount, t.timestamp, t.hash FROM transactions t "
        "JOIN projects p ON t.project_id = p.id "
        "WHERE t.public_key_sender = %s AND type = %s AND name LIKE %s AND category LIKE %s AND status LIKE %s"
    )
    params = (session["public_key"], "donation", "%" + name + "%", "%" + category + "%", "%" + status + "%")
    db.execute(query, params)

    projects_list = db.fetchall()
    if connection.is_connected():
        db.close()
        connection.close()

    # Format friendly date
    for project in projects_list:
        project["timestamp"] = format_date(project["timestamp"], "medium_string")

    return projects_list


def search_projects(name="", category="", status="", id=""):
    """ Search projects data with optional parameters:
     project's name, category, status and project id """

    projects_list = []

    # Start pool connection
    connection = connection_pool.get_connection()
    db = connection.cursor(dictionary=True)

    # Clean filter values
    category = clean_filter_value(category)
    status = clean_filter_value(status)

    query = ("SELECT id AS project_id, name, category, status, public_key, expire_date, goal, image_path, description FROM projects "
            "WHERE name LIKE %s AND category LIKE %s AND status LIKE %s"
    )
    params = ("%" + name + "%", "%" + category + "%", "%" + status + "%")

    print(f"Tipo do id recebido: {type(id)}")
    print(f"Id recebido: {id}")
    if id:
        query = query + " AND id = %s "
        params = params + (id,)
    
    print(query)
    print(params)
    db.execute(query, params)
    projects_list = db.fetchall()
    
    if connection.is_connected():
        db.close()
        connection.close()

    # NOTE: This function assumes expire_date is type datetime. Move with care.
    projects_list = calculate_project_days_left(projects_list)
    
    # Format friendly date
    for project in projects_list:
        print(f"Projeto da lista: {project}")
        project["expire_date"] = format_date(project["expire_date"], "medium_string")

    return calculate_project_progress(projects_list)


def search_refund_operations(projects_list):
    """ Search total donation amount per doner/project for admin to refund """

    refundable_projects = []

    connection = connection_pool.get_connection()
    db = connection.cursor(dictionary=True)
    
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

    if connection.is_connected():
        db.close()
        connection.close()

    return refundable_projects


def search_supported_projects():
    """ Search for projects supported by user """

    connection = connection_pool.get_connection()
    db = connection.cursor(dictionary=True)

    query = (
        "SELECT t.project_id, p.name, p.category, p.status, p.goal, SUM(amount) AS your_donations FROM transactions t "
        "JOIN projects p ON t.project_id = p.id "
        "WHERE t.public_key_sender = %s AND t.type = %s GROUP BY t.project_id ORDER BY status"
    )
    params = (session["public_key"], "donation")
    db.execute(query, params)
    projects_list = db.fetchall()
    
    if connection.is_connected():
        db.close()
        connection.close()

    return calculate_project_progress(projects_list)


""" UPDATE DATABASES """

def update_transactions_database(hash):
    """ Updates transactions table with donation data and project status after admin fund / refund projects"""

    try:
        connection = connection_pool.get_connection()
        db = connection.cursor(dictionary=True)
        
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

        connection.commit()
    
    except Exception as e:
        connection.rollback()
        print(str(e))

    finally:
        if connection.is_connected():
            db.close()
            connection.close()


def upload_image(base64_img, s3_bucket_name):
    """ Uploads the image on database """
    
    # Decode to bytes avoiding padding error
    try:
        image_str = base64_img.split(",")[1]
        image_bytes = base64.b64decode(image_str + "==")

        # Generate a secure filename
        random_hex = secrets.token_hex(8)
        filename = random_hex + ".png"

        s3_client = boto3.client('s3')
        s3_client.put_object(Bucket=s3_bucket_name, Key=filename, Body=image_bytes, ContentType='image/png')
        file_url = f"https://{s3_bucket_name}.s3.amazonaws.com/{filename}"

        return file_url

    except Exception as e:
        print(str(e))
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
