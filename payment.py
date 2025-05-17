#!C:/Users/1/AppData/Local/Programs/Python/Python313/python3.13.exe
import json
import cgi
import os
import secrets
from dotenv import load_dotenv
from datetime import datetime, timezone
import mysql.connector
import requests
from logger import logger
load_dotenv()

MAINS_SERVER_ADDRESS = "https://48v.me/~mains/cgi-bin/com.py"

db = mysql.connector.connect(
    host=os.getenv("DB_URL"),
    user=os.getenv("DB_USERNAME"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    auth_plugin="mysql_native_password"
)

def handle():
    try:
        form = cgi.FieldStorage()
        command = form.getfirst("command", "").strip()
        # Log the incoming request
        log_id = logger.log_request(form)
        if command == "inquiry": 
            result = get_credit_limit(form=form)
        elif command == "transfer":
            result = transfer(form=form)
    except Exception as e:
        result = { "success": False, "data": str(e) }
    # Log the response
    logger.log_response(log_id, result)
    print ("Access-Control-Allow-Headers: Origin, Content-Type\r\nAccess-Control-Allow-Origin: *\r\nAccess-Control-Allow-Methods: GET, POST, PATCH, PUT, DELETE, OPTIONS\r\nContent-Type: application/json\r\n")
    print(json.dumps(result, default=str)) 
    
    
def get_credit_limit(form):
    try:
        target_tid = form.getfirst("target_tid", "")
        target_auth = form.getfirst("target_auth", "")
        auth_data = { "command":"certification", "target_tid": target_tid, "target_auth": target_auth }
        response = requests.post(MAINS_SERVER_ADDRESS, data = auth_data)
        if response.status_code == 200:
            cursor = db.cursor(dictionary=True)
            uid = form.getfirst("uid", "").strip()
            sql = f"SELECT * FROM users WHERE uid = '{uid}'"
            cursor.execute(sql)
            users = cursor.fetchall()
            if len(users) == 1:
                amount = users[0]["amount"]
                sql = f"UPDATE users SET last_access = '{ datetime.now() }' WHERE uid = '{uid}'"
                cursor.execute(sql)
                db.commit()
                return { "success": True, "message": "Credit inquiry successful", "credit_limit": amount, "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") }    
            else:
                return { "success": False, "message": "User ID not found", "error_code": "USER_NOT_FOUND", "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") }
        else:
            return { "success": False, "data": "Certification Failed" }
    except Exception as e:
        return { "success": False, "data": str(e) }
    
def transfer(form):
    try:
        tid = form.getfirst("tid", "").strip()
        auth = form.getfirst("auth", "").strip()
        amount = float(form.getfirst("amount", "0").strip())
        response = requests.post(MAINS_SERVER_ADDRESS, data = { "command":"certification", "target_tid": tid, "target_auth": auth})
        cursor = db.cursor(dictionary=True)
        if response.status_code == 200:
            uid = form.getfirst("uid", "").strip()
            dist_uid = form.getfirst("dist_uid", "").strip()
            sql = f"SELECT * FROM users WHERE uid = '{uid}'"
            cursor.execute(sql)
            users = cursor.fetchall()
            if len(users) == 0:
                return { "success": False, "data": "No user id" }
            elif len(users) > 1:
                return { "success": False, "data": "Duplicate user id" }
            else:
                user_amount = float(users[0]["amount"])
                if(user_amount < amount):
                    sql = f"UPDATE users SET amount = 0, last_access = '{ datetime.now() } WHERE uid = '{uid}'"
                    cursor.execute(sql)
                    db.commit()
                    return { "success": False, "error_code": "Insufficient balance", "balance": 0, "defict": amount - user_amount }
                else:
                    sql = f"UPDATE users SET last_access = { datetime.now() }, amount = amount - {amount} WHERE uid='{uid}'"
                    cursor.execute(sql)
                    db.commit()
                    sql = f"UPDATE owners SET amount = amount + {amount}, last_access = { datetime.now() } WHERE owner_id='{dist_uid}'"
                    cursor.execute(sql)
                    db.commit()
                    return { "success": True, "balance": user_amount - amount }
        else:
            return { "success": False, "data": "USER_NOT_FOUND." }
    except Exception as e:
        return { "success": False, "data": "USER_NOT_FOUND", "details": str(e) }

handle()     
    
    
    