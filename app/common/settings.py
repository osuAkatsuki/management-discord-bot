import os

from dotenv import load_dotenv


def read_bool(value: str) -> bool:
    return value.lower() == "true"  # keep it simple


load_dotenv()


APP_ENV = os.environ["APP_ENV"]
APP_COMPONENT = os.environ["APP_COMPONENT"]

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]

READ_DB_SCHEME = os.environ["READ_DB_SCHEME"]
READ_DB_HOST = os.environ["READ_DB_HOST"]
READ_DB_PORT = int(os.environ["READ_DB_PORT"])
READ_DB_USER = os.environ["READ_DB_USER"]
READ_DB_PASS = os.environ["READ_DB_PASS"]
READ_DB_NAME = os.environ["READ_DB_NAME"]
READ_DB_USE_SSL = read_bool(os.environ["READ_DB_USE_SSL"])
READ_DB_CA_CERTIFICATE = os.environ["READ_DB_CA_CERTIFICATE"]
INITIALLY_AVAILABLE_READ_DB = os.environ["INITIALLY_AVAILABLE_READ_DB"]

WRITE_DB_SCHEME = os.environ["WRITE_DB_SCHEME"]
WRITE_DB_HOST = os.environ["WRITE_DB_HOST"]
WRITE_DB_PORT = int(os.environ["WRITE_DB_PORT"])
WRITE_DB_USER = os.environ["WRITE_DB_USER"]
WRITE_DB_PASS = os.environ["WRITE_DB_PASS"]
WRITE_DB_NAME = os.environ["WRITE_DB_NAME"]
WRITE_DB_USE_SSL = read_bool(os.environ["WRITE_DB_USE_SSL"])
WRITE_DB_CA_CERTIFICATE = os.environ["WRITE_DB_CA_CERTIFICATE"]
INITIALLY_AVAILABLE_WRITE_DB = os.environ["INITIALLY_AVAILABLE_WRITE_DB"]

# TODO: per-database settings?
DB_POOL_MIN_SIZE = int(os.environ["DB_POOL_MIN_SIZE"])
DB_POOL_MAX_SIZE = int(os.environ["DB_POOL_MAX_SIZE"])

SERVICE_READINESS_TIMEOUT = int(os.environ["SERVICE_READINESS_TIMEOUT"])

SCOREWATCH_CHANNEL_ID = int(os.environ["SCOREWATCH_CHANNEL_ID"])
ADMIN_SCOREWATCH_CHANNEL_ID = int(os.environ["ADMIN_SCOREWATCH_CHANNEL_ID"])

REPORT_CHANNEL_ID = int(os.environ["REPORT_CHANNEL_ID"])
ADMIN_REPORT_CHANNEL_ID = int(os.environ["ADMIN_REPORT_CHANNEL_ID"])

AKATSUKI_GUILD_ID = int(os.environ["AKATSUKI_GUILD_ID"])

AKATSUKI_SCOREWATCH_ROLE_ID = int(os.environ["AKATSUKI_SCOREWATCH_ROLE_ID"])

AWS_S3_REGION_NAME = os.environ["AWS_S3_REGION_NAME"]
AWS_S3_ACCESS_KEY_ID = os.environ["AWS_S3_ACCESS_KEY_ID"]
AWS_S3_SECRET_ACCESS_KEY = os.environ["AWS_S3_SECRET_ACCESS_KEY"]
AWS_S3_BUCKET_NAME = os.environ["AWS_S3_BUCKET_NAME"]
AWS_S3_ENDPOINT_URL = os.environ["AWS_S3_ENDPOINT_URL"]
