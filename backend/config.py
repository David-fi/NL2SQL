import os
from dotenv import load_dotenv

load_dotenv()

class MySQLConfig:
    host = os.getenv("DB_HOST", "localhost")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    database = os.getenv("DB_NAME", "nl2sqldatabase")

    @classmethod
    def get_config(cls):
        return {
            "host": cls.host,
            "user": cls.user,
            "password": cls.password,
            "database": cls.database
        }

    @classmethod
    def update_config(cls, host=None, user=None, password=None, database=None):
        if host is not None:
            cls.host = host
        if user is not None:
            cls.user = user
        if password is not None:
            cls.password = password
        if database is not None:
            cls.database = database
