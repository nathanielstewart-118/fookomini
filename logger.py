import os
import json
from datetime import datetime
import sys
import cgi
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

class Logger:
    def __init__(self):
        try:
            self.db = mysql.connector.connect(
                host=os.getenv("DB_URL"),
                user=os.getenv("DB_USERNAME"),
                password=os.getenv("DB_PASSWORD"),
                database=os.getenv("DB_NAME"),
                auth_plugin="mysql_native_password"
            )
        except Exception as e:
            print(f"Database connection error: {str(e)}", file=sys.stderr)
            self.db = None

    def log_request(self, form: cgi.FieldStorage) -> int:
        """
        Log an incoming request and return the log ID
        """
        try:
            if not self.db:
                return None
                
            cursor = self.db.cursor(dictionary=True)
            ip_address = os.environ.get('REMOTE_ADDR', 'Unknown')
            command = form.getfirst('command', '').strip()
            tid = form.getfirst('tid', '').strip()
            
            # Convert form data to JSON
            received_json = json.dumps(dict((key, form.getfirst(key)) for key in form.keys()))
            
            sql = """INSERT INTO logs
                    (ip_address, tid, command, received_json, sent_json, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)"""
            current_time = datetime.now()
            cursor.execute(sql, (ip_address, tid, command, received_json, "", current_time, current_time))
            self.db.commit()
            
            return cursor.lastrowid
            
        except Exception as e:
            print(f"Request logging error: {str(e)}", file=sys.stderr)
            return None

    def log_response(self, log_id: int, response_data: dict, tid: str = '', command: str = '') -> None:
        """
        Log the response for a given request
        """
        try:
            if not self.db or not log_id:
                return
                
            cursor = self.db.cursor(dictionary=True)
            response_json = json.dumps(response_data, default=str)
            
            sql = "UPDATE logs SET sent_json = %s, updated_at = %s WHERE id = %s"
            cursor.execute(sql, (response_json, datetime.now(), log_id))
            self.db.commit()
            
        except Exception as e:
            print(f"Response logging error: {str(e)}", file=sys.stderr)


# Create a singleton instance
logger = Logger()