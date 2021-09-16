import configparser
import mysql.connector
from sqlite3 import Error

config = configparser.ConfigParser()
config.read('config.ini')
db_name = config['Database']['database_name']
host = config['MySQL']['host']
username = config['MySQL']['username']
password = config['MySQL']['password']


def create_connection():
    this_connection = None
    try:
        this_connection = mysql.connector.connect(user=username, password=password, host=host, database=db_name)
    except Error as e:
        print(e)
    return this_connection


def fetch_data(sql_query, data):
    try:
        cursor = connection.cursor()
        cursor.execute(sql_query, data)
        return cursor.fetchall()
    except Error as e:
        print(e)


def update_database(sql_string, data):
    try:
        cursor = connection.cursor()
        cursor.execute(sql_string, data)
        connection.commit()
    except Error as e:
        print(e)


connection = create_connection()
