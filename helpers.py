import os
import base64
import requests
import urllib.parse
import sys
import secrets

import time
import math
import werkzeug.exceptions as ex

from datetime import datetime, timedelta
from flask import Flask, redirect, render_template, request, session
from functools import wraps
from io import BytesIO
from PIL import Image

from stellar_sdk import Asset, Keypair, Network, Server, TransactionBuilder
from stellar_sdk.exceptions import NotFoundError, BadResponseError, BadRequestError

UPLOAD_FOLDER = "./static/uploads"
ALLOWED_EXTENSIONS = set(["jpg", "png", "jpeg"])

# Configure application
app = Flask(__name__)

# Configure CS50 Library to use SQLite database
from cs50 import SQL
db = SQL("sqlite:///crowdfunding.db")

admin_account = "GCLMA7L4TWKF2NZYKT3W5OZCJ6IBLLPN3P7Q5JRFRTV3FRMCR3BEGYQR"
categories_list = ["Books", "Games", "Music", "Technology", "All"]
status_list = ["Active", "Fund", "Refund", "Successful", "Unsuccessful"]
sort_list = ["Category", "Name", "Status", "All"]


def format_date(date, date_type):

    # Dates with time are inserted on database
    if date_type == "long_datetime_db":
        dt = datetime.strptime(date, "%Y-%m-%d")
        new_date = dt.replace(hour=23, minute=59, second=59)

    # Medium dates are shown on client side
    elif date_type == "medium_string":
        new_date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y")
    elif date_type == "long_datetime":
        new_date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")

    return new_date


def calculate_project_progress(projects_list):
    """ Calculate percentage of funding progress """

    for project in projects_list:

        # Get total amount of donations
        amount_donations = db.execute("SELECT SUM(amount) as donations FROM transactions WHERE project_id = ? AND type = ?", project["project_id"], "donation")[0]
        if not amount_donations["donations"]:
            amount_donations["donations"] = 0
        project["total_donations"] = amount_donations["donations"]

        # Calculate percentage
        project["funding_progress"] = f'{math.floor(project["total_donations"] / project["goal"] * 100)}%'

    return projects_list


def get_const_list(const_list):
    """ Get constant list os default values """
    if const_list == "category":
        const_list = categories_list
    elif const_list == "status":
        const_list = status_list

    return const_list


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
    projects_list = db.execute(
        "SELECT t.project_id, p.name, p.category, t.amount, t.timestamp, t.hash FROM transactions t "
        "JOIN projects p ON t.project_id = p.id "
        "WHERE t.public_key_sender = ? AND type = ? AND name LIKE ? AND category LIKE ? AND status LIKE ?",
        session["public_key"], "donation",  "%" + name + "%", "%" + category + "%", "%" + status + "%"
        )

    for project in projects_list:
        project["timestamp"] = format_date(project["timestamp"], "medium_string")

    return projects_list


def search_projects(name="", category="", status="", id=""):
    """ Search projects data and total donations.
     Parameters are optional, returning all projects if none is passed """

    projects_list = []

    if category in ["All", "all"]:
        category = ""
    if status in ["All", "all"]:
        status = ""

    if not id:
        projects_list = db.execute("SELECT id AS project_id, name, category, status, public_key, expire_date, goal, image_path, description FROM projects WHERE name LIKE ? AND category LIKE ? AND status LIKE ? ORDER BY status", "%" + name + "%", "%" + category + "%", "%" + status + "%")
    else:
        projects_list = db.execute("SELECT id AS project_id, name, category, status, public_key, expire_date, goal, image_path, description FROM projects WHERE name LIKE ? AND category LIKE ? AND status LIKE ? AND id = ? ORDER BY status", "%" + name + "%", "%" + category + "%", "%" + status + "%", id)

    for project in projects_list:

        # Format proper date type
        expire_date = format_date(project["expire_date"], "long_datetime")
        project["expire_date"] = format_date(project["expire_date"], "medium_string")

        # Calculate remaining active project days
        if project["status"] == "active":

            days_remaining = expire_date - datetime.today()
            days_left = days_remaining.days
            if days_left == 0:
                project["days_left"] = "last day"
            elif days_left == 1:
                project["days_left"] = "{} day left".format(days_left)
            else:
                project["days_left"] = "{} days left".format(days_left)
        else:
            project["days_left"] = 0

    return calculate_project_progress(projects_list)


def search_refund_operations(projects_list):

    refundable_projects = []
    for project in projects_list:
        doners_operations = db.execute("SELECT project_id, public_key_sender AS public_key, SUM(amount) AS total_donations FROM transactions WHERE project_id = ? AND type = ? GROUP BY public_key_sender", project["project_id"], "donation")
        for operation in doners_operations:
            operation["name"] = project["name"]
        refundable_projects.extend(doners_operations)

    return refundable_projects


def search_supported_projects():

    # Search for projects supported by user
    projects_list = db.execute(
        "SELECT t.project_id, p.name, p.category, p.status, p.goal, SUM(amount) AS your_donations FROM transactions t "
         "JOIN projects p ON t.project_id = p.id "
         "WHERE t.public_key_sender = ? AND t.type = ? GROUP BY t.project_id ORDER BY status", session["public_key"], "donation")

    return calculate_project_progress(projects_list)


""" UPDATE DB """

def update_database_status():
    """ Updates project's status when expired.
    From active to: fund, refund or unsuccessful """

    # Get all projects
    projects_list = calculate_project_progress(db.execute("SELECT id AS project_id, expire_date, goal FROM projects"))

    for project in projects_list:
        project["expire_date"] = format_date(project["expire_date"], "long_datetime")

        # Update status of expired projects
        if project["expire_date"] < datetime.today():

            # Projects that achieved their funding goal will be funded by admin
            if project["total_donations"] >= project["goal"]:
                db.execute("UPDATE projects SET status = ? WHERE id = ?", "fund", project["project_id"])

            # Projects with no amount of donations pass directly to unsuccessful
            elif project["total_donations"] == 0:
                db.execute("UPDATE projects SET status = ? WHERE id = ?", "unsuccessful", project["project_id"])

            # Projects that didn't achieve their funding goal will have their donations returned to backers
            else:
                db.execute("UPDATE projects SET status = ? WHERE id = ?", "refund", project["project_id"])


def update_transactions_database(temp_table, hash):
    """ Updates transactions table with donation data and project status after admin fund / refund projects"""

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
            db.execute("UPDATE projects SET status = ? WHERE id = ?", operation["new_status"], operation["project_id"])

        db.execute("INSERT INTO transactions (project_id, amount, public_key_sender, public_key_receiver, hash, type) VALUES(?, ?, ?, ?, ?, ?)", operation["project_id"], operation["amount"], public_key_sender, public_key_receiver, hash, operation["type"])


def apology(message, code=400):
    """Render message as an apology to user."""
    return render_template("apology.html", top=code, bottom=message)


def freighter_required(f):
    """ Decorate routes to require user's connection with freighter."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("public_key") is None:
            return redirect("/")
        return f(*args, **kwargs)
    return decorated_function


def upload_image(base64_img):

    # Decode to bytes avoiding padding error
    try:
        image_str = base64_img.split(",")[1]
        image_bytes = base64.b64decode(image_str + "==")

        # Generate a secure filename
        random_hex = secrets.token_hex(8)
        filename = random_hex + ".png"

        image = Image.open(BytesIO(image_bytes))
        image_path = os.path.join(UPLOAD_FOLDER, filename)
        image.save(image_path, "PNG")
        return filename

    except Exception as e:
        print(e)
        return e