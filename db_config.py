import mysql.connector, mysql.connector.pooling
import os

db_host = os.environ['DB_HOST']
db_port = os.environ['DB_PORT']
db_user = os.environ['DB_USER']
db_password = os.environ['DB_PASSWORD']
db_name = os.environ['DB_NAME']

db_config = {
    "host": db_host,
    "user": db_user,
    "password": db_password,
    "database": db_name,
    "port": db_port
}

connection_pool = mysql.connector.pooling.MySQLConnectionPool(pool_name="mypool", pool_size=5, **db_config)
