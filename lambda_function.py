"""
Currently this is used on AWS Lambda to update projects status.
To test it in a Flask environment, you can create a new route on app.py and trigger it.
"""

import traceback

from datetime import datetime
from db_config import connection_pool
from helpers import get_total_donations


def fetch_active_projects():

    connection = connection_pool.get_connection()
    db = connection.cursor(dictionary=True)

    try:    
        db.execute("SELECT id AS project_id, expire_date, goal FROM projects WHERE status = 'active'")
        active_projects = db.fetchall()
        return active_projects
    
    except Exception as e:
        connection.rollback()
        raise Exception("Error on fetch active projects: ", str(e))
    
    finally:
        if connection.is_connected():
            db.close()
            connection.close()


def change_status(projects_list):

    projects_list = [project for project in projects_list if project is not None]
    
    connection = connection_pool.get_connection()
    db = connection.cursor(buffered=True, dictionary=True)

    try:
        for project in projects_list:

            if project == None:
                continue
   
            # Update status of expired projects
            if project["expire_date"] < datetime.today():

                new_status = None
                # Projects that achieved their funding goal will be funded by admin
                if project["total_donations"] >= project["goal"]:
                    new_status = "fund"
                
                # Projects with no amount of donations pass directly to unsuccessful
                elif project["total_donations"] == 0:
                    new_status = "unsuccessful"
                
                # Projects that didn't achieve their funding goal will have their donations returned to backers
                else:
                    new_status = "refund"

                query = "UPDATE projects SET status = %s WHERE id = %s"
                params = (new_status, project["project_id"])
                db.execute(query, params)
                connection.commit()

    except Exception as e:
        connection.rollback()
        print("Error on change status: ", str(e))
        return False
    
    finally:
        if connection.is_connected():
            db.close()
            connection.close()
    
    return True


def update_database_status():
    """
    Updates project's status when expired.
    From active to: fund, refund or unsuccessful
    """

    # Select all active projects
    try:
        projects_list = fetch_active_projects()
        if not projects_list:
            return

        # Get total donations and update 'project' on database
        projects_list = get_total_donations(projects_list)
        change_status(projects_list)

    except Exception as e:
        error_msg = "Error on update database status: " + str(e)
        traceback_msg = traceback.format_exc()
        full_error_msg = error_msg + "\nTraceback:\n" + traceback_msg
        print(full_error_msg)
        return error_msg
       