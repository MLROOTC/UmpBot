import configparser
import sqlite3
from sqlite3 import Error

config = configparser.ConfigParser()
config.read('config.ini')
db_name = config['Database']['database_name']


def create_connection(db_file):
    this_connection = None
    try:
        this_connection = sqlite3.connect(db_file, isolation_level=None)
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


connection = create_connection(db_name)
