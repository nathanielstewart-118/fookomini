#!./.venv/bin/python3
#coding: utf-8


import json
import cgi
import os
import secrets
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
import mysql.connector
import requests


load_dotenv()

MAINS_SERVER_ADDRESS = "http://www.48v.me/~mains/cgi-bin/com.py"

db = mysql.connector.connect(
    host=os.getenv("DB_URL"),
    user=os.getenv("DB_USERNAME"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    auth_plugin="mysql_native_password"
)
cursor = db.cursor(dictionary=True)
def handle():
    try:
        form = cgi.FieldStorage()
        command = form.getfirst("command", "").strip()
        
        if command == "get_uids": 
            result = get_uids()
        elif command == "get_logs":
            result = get_logs(form)
        elif command == "refresh_db":
            result = refresh()
        else:
            result = { "success": False, "data": "Invalid command" }
    except Exception as e:
        result = { "success": False, "data": str(e) }
    print ("Access-Control-Allow-Headers: Origin, Content-Type\r\nAccess-Control-Allow-Origin: *\r\nAccess-Control-Allow-Methods: GET, POST, PATCH, PUT, DELETE, OPTIONS\r\nContent-Type: application/json\r\n")
    print(json.dumps(result, default=str)) 


def get_uids():
    try:
        sql = "SELECT uid, amount, last_access, created_at FROM users"
        cursor.execute(sql)
        users = cursor.fetchall()
        return { "success": True, "users": users }
    except Exception as e:
        return { "success": False, "data": str(e) }


def get_logs(form):
    try:
        date = form.getfirst("date", "").strip()
        first_day = datetime.strptime(date, "%Y-%m")
        next_month = (first_day.replace(day=28) + timedelta(days=4)).replace(day=1)
        sql = f"SELECT ip_address, received_json, sent_json, created_at FROM logs WHERE created_at BETWEEN '{first_day.strftime("%Y-%m-%d")} 00:00:00' AND '{next_month.strftime("%Y-%m-%d")} 00:00:00'"
        cursor.execute(sql)
        logs = cursor.fetchall()
        return { "success": True, "logs": logs }    
    except Exception as e:
        return { "success": False, "data": str(e) }

def refresh():
    try:
        cursor = db.cursor(dictionary = True)
        sql = f"DELETE FROM users WHERE created_at <= DATE_SUB(NOW(), INTERVAL {os.getenv("REFRESH_MONTH")} MONTH)"
        cursor.execute(sql)
        db.commit()
    except Exception as e:
        return { "success": False, "data": str(e) }
    return { "success": True }

handle()