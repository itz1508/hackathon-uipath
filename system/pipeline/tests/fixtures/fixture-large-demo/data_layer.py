"""Data layer with private connector."""

from private_db_connector import Connection

def get_data():
    return Connection().query("SELECT 1")
