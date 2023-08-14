import os
import time

from db_config import connection_pool
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, make_response, redirect, render_template, request, session, url_for
from helpers import apology, check_amount, check_projects_action, format_date, freighter_required, search_donations_history, search_projects, search_refund_operations, search_supported_projects, update_database_status, update_transactions_database, upload_image, validate_input
from stellar_sdk import Asset, Network, Server, TransactionBuilder
from stellar_sdk.exceptions import NotFoundError, BadResponseError, BadRequestError


# Configure flask
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')

load_dotenv()

# All testnet Stellar accounts reset periodically (https://developers.stellar.org/docs/fundamentals-and-concepts/testnet-and-pubnet)
admin_account = "GCLMA7L4TWKF2NZYKT3W5OZCJ6IBLLPN3P7Q5JRFRTV3FRMCR3BEGYQR"

# Set Horizon 
server = Server("https://horizon-testnet.stellar.org")


# Variables used on templates
@app.context_processor
def global_variables():
    admin_account = "GCLMA7L4TWKF2NZYKT3W5OZCJ6IBLLPN3P7Q5JRFRTV3FRMCR3BEGYQR"
    categories_list = ["Books", "Games", "Music", "Technology"]
    status_list = ["Active", "Fund", "Refund", "Successful", "Unsuccessful"]
    return dict(categories_list=categories_list, status_list=status_list, admin_account=admin_account)

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET", "POST"])
def index():
    """ Homepage """

    # Timing
    start_time_total = time.time()

    # Handle connect wallet
    if request.method == "POST":

        # Forget any user_id
        session.clear()

        try:
            # Get public key and store within session
            public_key = request.data.decode("utf-8")
            session["public_key"] = public_key
            return make_response("OK", 200)

        except Exception as e:
            print(str(e))
            return apology("Internal server error", 500)

    # Get active projects from database
    projects_list = search_projects(status="active")

    end_time_total = time.time()
    print(f"Time tracking: {end_time_total - start_time_total} sec")

    return render_template("index.html", projects_list=projects_list)

@app.route("/logout")
def logout():
    """ Disconnect Wallet """

    # Forget any user_id
    session.clear()

    return redirect("/")


@app.route("/about", methods=["GET", "POST"])
def about():
    return render_template("about.html")


@app.route("/projects", methods=["GET", "POST"])
def projects():
    """ Show active projects """

    projects_list = []

    # Handles search
    if request.method == "POST":
        project_search = {
            "category": request.form.get("searchProjectCategory"),
        }

        if validate_input(project_search) != True:
            return apology(validate_input(project_search), 400)

        projects_list = search_projects(request.form.get("searchProjectName"), project_search["category"], "active")

    else:
        projects_list = search_projects(status="active")

    return render_template("projects.html", projects_list=projects_list)



@app.route("/project/<int:project_id>", methods=["GET", "POST"])
def project_page(project_id):
    """ Show and edit project page """

    # Edit project data
    if request.method == "POST":

        expire_date = format_date(request.form.get("newExpireDate"), "long_datetime_db")
        project = {
            "category": request.form.get("newCategory"),
            "goal": request.form.get("newGoal"),
            "name": request.form.get("newName"),
            "expire_date": expire_date,
            "description": request.form.get("newDescription")
        }

        if validate_input(project) != True:
            return apology(validate_input(project), 400)

        # Update table projects and return project page refreshed
        connection = connection_pool.get_connection()
        db = connection.cursor()

        try:
            query = ("UPDATE projects SET name = %s, category = %s, goal = %s, expire_date = %s, description = %s WHERE id = %s")
            params = (project["name"], project["category"], project["goal"], project["expire_date"], project["description"], project_id)
            db.execute(query, params)
            connection.commit()
        
        except Exception as e:
            connection.rollback()
            print(str(e))
            return apology("Error editing project.", 500)
        
        finally:
            if connection.is_connected():
                db.close()
                connection.close()
        
        return redirect(url_for("project_page", project_id=project_id))

    # Get project info from database
    project = search_projects(id=project_id)[0]

    return render_template('project.html', project=project)


@app.route("/donate", methods=["POST"])
def donate():
    """ Make a donation """

    # Get project data
    data = request.get_json()
    project_id = data.get("project_id")

    # Open pool connection
    connection = connection_pool.get_connection()
    db = connection.cursor(dictionary=True)

    query = "SELECT status, public_key FROM projects WHERE id = %s"
    params = (project_id,)
    db.execute(query, params)
    project_data = db.fetchone()

    if connection.is_connected():
        db.close()
        connection.close()

    # Check if project is valid for user to donate
    if project_data["status"] != "active":
        msg = "Expired projects can't receive donations."
        print(msg)
        return apology("msg", 400)

    if project_data["public_key"] == session["public_key"]:
        msg = "Self donations are not allowed."
        print(msg)
        return apology("msg", 400)

    amount = data.get("amount")
    if not check_amount(amount):
        msg = "Invalid amount."
        print(msg)
        return apology(msg, 400)

    operation_data = [{
        "project_id": project_id,
        "amount": amount,
        "source_account": session["public_key"],
        "destination_account": admin_account,
    }]

    try:
        transaction_xdr = build_payment_transaction(operation_data, "donation")
        return jsonify(transaction_xdr=str(transaction_xdr))
    
    except Exception as e:
        print(str(e))
        return apology("Something went wrong building payment transaction.", 500)
    

@app.route("/myaccount", methods=["GET", "POST"])
@freighter_required
def my_account():
    """ Personal user page with all projects and donations info """

    # If admin tries to access myaccount, redirect to control panel
    if session["public_key"] == admin_account:
        return redirect("/controlpanel")

    projects_list = []

    # Handle search
    if request.method == "POST":
        project_search = {
            "category": request.form.get("searchProjectCategory"),
            "status": request.form.get("searchProjectStatus"),
        }

        if validate_input(project_search) != True:
            return apology(validate_input(project_search), 400)

        # Get projects data (with filters)
        projects_list = search_projects(request.form.get("searchProjectName"), project_search["category"], project_search["status"])

        # Get donation data (with filters)
        supported_projects = search_supported_projects()
        user_donations_list = search_donations_history(request.form.get("searchProjectName"), project_search["category"], project_search["status"])

    else:
         # Get donations full data
        projects_list = search_projects()

         # Get projects full data
        supported_projects = search_supported_projects()
        user_donations_list = search_donations_history()

    # Filter only user's projects
    user_projects_list = [project for project in projects_list if project["public_key"] == session["public_key"]]

    return render_template("myaccount.html", user_projects_list=user_projects_list, supported_projects=supported_projects, user_donations_list=user_donations_list)


@app.route("/newproject", methods=["GET", "POST"])
@freighter_required
def new_project():
    """ Save a new project """

    if request.method == "POST":

        expire_date = format_date(request.form.get("projectExpireDate"), "long_datetime_db")

        project = {
            "category": request.form.get("projectCategory"),
            "goal": request.form.get("projectGoal"),
            "name": request.form.get("projectName"),
            "expire_date": expire_date,
            "description": request.form.get("projectDescription"),
            "image": request.form.get("base64Image")
        }

        if validate_input(project) != True:
            return apology(validate_input(project), 400)
        
        file_url = None
        try:
            file_url = upload_image(project["image"])
        
        except Exception as e:
            print(str(e))
            return apology("Image upload failed.", 500)

        # Start pool connection
        connection = connection_pool.get_connection()
        db = connection.cursor()

        try:
            # Update table projects
            query = ("INSERT INTO projects (public_key, name, category, goal, expire_date, status, image_path, description) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)")
            params = (session["public_key"], project["name"], project["category"], project["goal"], project["expire_date"], "active", file_url, project["description"])
            db.execute(query, params)
            connection.commit()

            # Get project id
            db.execute("SELECT id FROM projects ORDER BY created_at DESC LIMIT 1")
            rows = db.fetchone()
            project_id = rows[0]
        
        except Exception as e:
            connection.rollback()
            print(str(e))
            return apology(f"An error occurred inserting your project on database: {str(e)}", 500)
        
        finally:
            if connection.is_connected():
                db.close()
                connection.close()

        # Get project ID
        return redirect(url_for("project_page", project_id=project_id))

    filename = "theo.jpg"

    return render_template("newproject.html", filename=filename)


""" ADMIN ROUTES """

@app.route("/controlpanel", methods=["GET", "POST"])
@freighter_required
def control_panel():
    """ Control page for admin to fund and refund expired projects """

    # If user tries to access control panel, redirect to my account page
    if session["public_key"] != admin_account:
        return redirect("/myaccount")

    # Get all projects from database
    admin_projects_list = search_projects()

    # Handle fund and refund transactions
    if request.method == "POST":
        admin_action_projects = []

        # Get operation type and selected projects list
        operation_type = request.headers.get("Operation-Type")
        request_data = request.get_json()
        selected_project_ids = [int(id) for id in request_data.get("selected_project_ids")]

        # Discart projects not fundable or refundable
        admin_action_projects = check_projects_action(admin_projects_list, selected_project_ids, operation_type)

        if operation_type == "refund":

            # Get refund amount from transactions table
            admin_action_projects = search_refund_operations(admin_action_projects)

        return jsonify(admin_action_projects=admin_action_projects)

    return render_template("controlpanel.html", admin_projects_list=admin_projects_list)



@app.route("/statusupdate", methods=["POST"])
@freighter_required
def status_update():
    # TO DO: Change this to a scheduled task

    try:
        update_database_status()
        return make_response("OK", 200)
    
    except Exception as e:
        print(str(e))
        return apology("Error updating projects status on database", 500)



@app.route("/filter_projects", methods=["POST"])
def filter_projects():
    """ Filter searched projects in controlpanel.html """

    project_search = {
        "category": request.form.get("searchProjectCategory"),
        "status": request.form.get("searchProjectStatus")
    }

    if validate_input(project_search) != True:
        return apology(validate_input(project_search), 400)

    try:
        admin_projects_list = search_projects(request.form.get("searchProjectName"), project_search["category"], project_search["status"])
        return render_template("controlpanel.html", admin_projects_list=admin_projects_list)
    
    except Exception as e:
        print(str(e))
        return apology("Error filtering projects.", 500)


@app.route("/build_admin_transaction", methods=["POST"])
@freighter_required
def build_admin_transaction():
    """ Prepares data and builds xdr admin transactions """

    operation_type = request.headers.get("Operation-Type")
    request_data = request.get_json()
    data = request_data.get("admin_operations")

    admin_operations = [
        {
            "project_id": project["project_id"],
            "amount": project["total_donations"],
            "source_account": admin_account,
            "destination_account": project["public_key"],
        }
        for project in data
    ]

    try:
        transaction_xdr = build_payment_transaction(admin_operations, operation_type)
        return jsonify(transaction_xdr=str(transaction_xdr))
    
    except Exception as e:
        print(str(e))
        return apology("Something went wrong building payment transaction.", 500)

  
def build_payment_transaction(operations_list, operation_type):
    """ Builds one operation per project, grouping into one transaction.
    Each transaction has it's own operation type (donation for users and fund/refund for admin)"""

    # Check if destination account exists
    for operation in operations_list:
        try:
            server.load_account(operation["destination_account"])
        except NotFoundError:
            raise Exception("This destination account doesn't exists.")

    # For donating, receiver = admin and sender = user
    if operation_type == "donation":
        public_key_sender = operations_list[0]["source_account"]

    # For fundings and refunds, sender = admin
    else:
        public_key_sender = admin_account

     # Get transaction fee from Stellar Network
    base_fee = server.fetch_base_fee()

    # Cast source account to proper type (stellar_sdk.account.Account)
    source_account = server.load_account(public_key_sender)

    # Build transaction
    transaction = (
        TransactionBuilder(
            source_account=source_account,
            network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
            base_fee=base_fee,
        )
    )

    # Get temporary transactions table (stored in the temp database)
    connection = connection_pool.get_connection()
    db = connection.cursor(dictionary=True)

    db.execute("SELECT * FROM temp_operations")
    temp_transactions_list = db.fetchall()

    # Reset table if it's not empty
    if temp_transactions_list:
        db.execute("DELETE FROM temp_operations")

    # Append payment operations for each project
    for operation in operations_list:
        transaction.append_payment_op(destination=operation["destination_account"], asset=Asset.native(), amount=str(operation["amount"]))

        # Save operations temporarily to update database after submitting transaction
        db.execute("INSERT INTO temp_operations (project_id, amount, destination_account, type) VALUES(%s, %s, %s, %s)", (operation["project_id"], operation["amount"], operation["destination_account"], operation_type))

    connection.commit()
    if connection.is_connected():
        db.close()
        connection.close()

    # Set max timelimit (in seconds) to process transaction
    transaction.set_timeout(30)
    transaction = transaction.build()

    # Convert transaction to XDR format and return for signing
    transaction_xdr = transaction.to_xdr()

    return transaction_xdr


@app.route("/send_transaction", methods=["POST"])
@freighter_required
def send_transaction():
    """Submit transaction to Stellar"""

    try:
        # Get signed transaction and submit
        signed_transaction = request.get_json()
        submit_response = server.submit_transaction(signed_transaction)

        # Get hash and update database with new transaction
        if submit_response["successful"] == True:

            try:
                hash = submit_response["hash"]
                update_transactions_database(hash)
                return jsonify(submit_response)
            
            except Exception as e:
                print(str(e))
                return apology("Error updating transactions into database", 500)

    # Handle default Stellar errors
    except (BadRequestError, BadResponseError) as e:
        print(str(e))
        return apology("Error submitting transaction to Stellar", 500)


@app.route("/test", methods=["GET", "POST"])
def test():
    return render_template("test.html")