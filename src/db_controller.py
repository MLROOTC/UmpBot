import configparser
import mysql.connector

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
    except mysql.connector.Error as e:
        print(e)
    return this_connection


def fetch_data(sql_query, data):
    try:
        cursor = get_cursor(connection)
        cursor.execute(sql_query, data)
        return cursor.fetchall()
    except mysql.connector.Error as e:
        print(e)


def get_cursor(this_connection):
    try:
        this_connection.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.Error as err:
        this_connection = create_connection()
    return this_connection.cursor()


def update_database(sql_string, data):
    try:
        cursor = get_cursor(connection)
        cursor.execute(sql_string, data)
        connection.commit()
    except mysql.connector.Error as e:
        print(e)


connection = create_connection()
