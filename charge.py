#!./.venv/bin/python3
#coding: utf-8

import json
import cgi
import os
import secrets
from dotenv import load_dotenv
from datetime import datetime, timezone
import mysql.connector
from logger import logger
import time

load_dotenv()

db = mysql.connector.connect(
    host=os.getenv("DB_URL"),
    user=os.getenv("DB_USERNAME"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    auth_plugin="mysql_native_password"
)

NEW_USER = 0
REGISTERED_USER = 1

def handle():
    try:
        start = time.time()
        form = cgi.FieldStorage()
        command = form.getfirst("command", "").strip()
        # Log the incoming request
        log_id = logger.log_request(form)
        if command == "deposit": 
            result = do_charge(target=REGISTERED_USER, form=form)
        elif command == "new":
            result = do_charge(target=NEW_USER, form=form)
        elif command == "withdrawal":
            result = withdraw(form=form)
        else:
            result = { "success": False, "data": "Invalid command" }
        end = time.time()
        result["time"] = end - start
    except Exception as e:
        result = { "success": False, "data": str(e) }
    # Log the response
    logger.log_response(log_id, result)
    print ("Access-Control-Allow-Headers: Origin, Content-Type\r\nAccess-Control-Allow-Origin: *\r\nAccess-Control-Allow-Methods: GET, POST, PATCH, PUT, DELETE, OPTIONS\r\nContent-Type: application/json\r\n")
    print(json.dumps(result, default=str)) 
    
    
def do_charge(target, form):
    try:
        amount = form.getfirst("amount", "0").strip()
        cursor = db.cursor(dictionary=True)
        if target == REGISTERED_USER:
            uid = form.getfirst("uid", "").strip()
            sql = f"SELECT amount FROM users WHERE uid = '{uid}'"
            cursor.execute(sql)
            result = cursor.fetchall()
            sql = f"UPDATE users SET amount = amount + {float(amount)} WHERE uid = '{uid}'"
            cursor.execute(sql)
            db.commit()
            new_amount = result[0]["amount"] + float(amount)
        elif target == NEW_USER:
            uid = secrets.token_hex(5)
            sql = f"INSERT INTO users(uid, amount, created_at, updated_at, last_access) VALUES('{ uid }', { amount }, '{ datetime.now() }', '{ datetime.now() }', '{ datetime.now() }')"
            cursor.execute(sql)
            db.commit()
            new_amount = float(amount)
        return { "success": True, "uid": uid, "message": "Credit charge successful", "credit_limit": new_amount, "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") }

    except Exception as e:
        return { "success": False, "message": "User Id not found.", "error_code": "USER_NOT_FOUND", "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "details": str(e) }


def withdraw(form):
    try:
        uid = form.getfirst("uid", "")
        cursor = db.cursor(dictionary=True)
        sql = f"DELETE FROM users WHERE uid = '{uid}'"
        cursor.execute(sql)
        db.commit()
        return { "success": True}
    except Exception as e:
        return { "success": False, "data": str(e)}

handle()