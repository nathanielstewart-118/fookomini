#!./venv/bin/python3
#coding: utf-8

import json
import secrets
from dotenv import load_dotenv
import os
import sys
import cgi
from datetime import datetime, timezone
import mysql.connector
from logger import logger  # Import the centralized logger

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../', 'shared')))
from state import State
from utils import gen_sun

load_dotenv()

db = mysql.connector.connect(
    host=os.getenv("DB_URL"),
    user=os.getenv("DB_USERNAME"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    auth_plugin="mysql_native_password"
)

delay_hour = float(os.getenv("DELAY_HOUR"))




def handle():
    form = cgi.FieldStorage()
    command = form["command"].value
    
    # Log the incoming request
    log_id = logger.log_request(form)
    
    # Process the command
    if command == "init":
        result = init(form, db)
    elif command == "reqtoken":
        result = req_token(form, db)
    elif command == 'req_sun':
        result = req_sun(form, db)
    elif command == 'reqconfig':
        result = req_config()
    elif command == 'service_in':
        result = service_in(form, db)
    elif command == 'service_out':
        result = service_out(form, db)
    elif command == 'service_togo':
        result = service_togo(form, db)
    elif command == 'refresh_db':
        result = refresh_db(db)
    elif command == 'lifesignal':
        result = life_signal(form, db)
    elif command == 'certification':
        result = certificate(form, db)
    
    # Log the response
    logger.log_response(log_id, result)

    print("Access-Control-Allow-Headers: Origin, Content-Type\r\nAccess-Control-Allow-Origin: *\r\nAccess-Control-Allow-Methods: GET, POST, PATCH, PUT, DELETE, OPTIONS\r\nContent-Type: application/json\r\n")
    print(json.dumps(result, default=str))  
    
    
def init(form, db):
    try:
        data = {
            "success": True,
        }
        tid = form['tid'].value
        token = form['token'].value
        cursor = db.cursor(dictionary=True)
        sql = f"select tid, area, product_name, key_string, token from terminals where tid='{tid}'"
        cursor.execute(sql)
        terminals = cursor.fetchall()
        if len(terminals) == 0:
            data = {
                "success": False,
                "data": "no matching terminal"
            }
        elif len(terminals) > 1:
            data = {
                "success": False,
                "data": "duplicated terminals"
            } 
        elif terminals[0].get("token") != token:
                data = {
                    "success": False,
                    "data": "token mismatch"
                }
        else:
            sql = f"SELECT tid, current_weight, max_sales_amount, created_at, updated_at FROM restocks where tid='{tid}'"
            cursor.execute(sql)
            total_values = cursor.fetchall()
            
            sql = "select id, unit, name, url, description from currencies" 
            cursor.execute(sql)
            currencies = cursor.fetchall()
            
            sql = """
            SELECT o.*, a.cur_sys_id, a.uid
            FROM owners o
            JOIN accounts a
            ON JSON_CONTAINS(o.accounts, JSON_QUOTE(CAST(a.id AS CHAR))) WHERE JSON_CONTAINS(terminals, %s)
            """
            cursor.execute(sql, (json.dumps(tid),))
            owners = cursor.fetchall()
            
            if len(owners) > 0:
                owner = {
                    "owner_name": owners[0]["owner_name"],
                    "owner_sun": owners[0]["owner_sun"],
                    "accounts": [],
                    "terminals": owners[0]["terminals"]
                }
                accounts = []
                for a in owners:
                    accounts.append({
                        "cur_sys_id": a["cur_sys_id"],
                        "uid": a["uid"]
                    })
                owner["accounts"] = accounts
            else:
                owner = {}
            data["data"] = {
                "total_values": total_values,
                "currencies": currencies,
                "owner": owner 
            }
    except Exception as e:
        data = {
            "success": False,
            "data": str(e)
        }
    return data
        
def req_token(form, db):
    try:
        tid = form["tid"].value
        cursor = db.cursor(dictionary=True)
        sql = f"SELECT tid, area, product_name, key_string, token FROM terminals where tid = '{tid}'"
        cursor.execute(sql)
        records = cursor.fetchall()
        if len(records) == 0:
            data = {
                "data": "no terminal with that id"
            }
        elif len(records) == 1:
            key = form["key"].value
            if key == records[0]["key_string"]:
                token = secrets.token_hex(16)
                data = { 
                    "success": True,
                    "token": token,
                }
            else:
                data = {
                    "success": False,
                    "data": "The key field doesn't match!"
                }
        else:
            data = {
                "success": False,
                "data": "duplicated terminal id"
            }
    except Exception as e:
        data = {
            "success": False,
            "data": str(e)
        }
    return data
        

def req_config():
    try:
        data = {
            "success": True,
            "data": {
                "mains": "https://www.48v.me/~mains",
                "controlSUNNumber": "99993",
                "ifservernoreaction": "",
                "servicetype": "",
                "serviceprice": "",
            }
        }
    except Exception as e:
        data["success"] = False
        data["data"] = str(e)
    return data
        
def req_sun(form, db):
    try:
        cur_sys_id = form["CurSysID"].value
        uid = form["uid"].value
        tid = form["tid"].value
        cursor = db.cursor(dictionary=True)
        sql = f"select * from suns where cur_sys_id = '{cur_sys_id}' and uid = '{uid}' and tid = '{tid}'"
        cursor.execute(sql)
        suns = cursor.fetchall()
        if len(suns) == 0:
            new_sun = gen_sun(1, cur_sys_id)
            data = {
                "success": True,
                "sun": new_sun,
                "message": "new",
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            }
            sql = f"insert into suns(cur_sys_id, uid, tid, sun, gram, max_sales_amount, created_at, updated_at) values({cur_sys_id}, '{uid}', '{tid}', '{new_sun}', 0, 0, '{datetime.now()}', '{datetime.now()}')"
        else:
            sun = suns[-1]
            diff_hours = (datetime.now() - sun.get("updated_at")).total_seconds() / 3600
            if diff_hours < delay_hour:
                data = {
                    "success": True,
                    "sun": sun["sun"],
                    "message": "registered",
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                }
                sql = f"""Update suns set updated_at = '{datetime.now()}' where id = {sun["id"]}"""
            else:
                new_sun = gen_sun(1, cur_sys_id)
                data = {
                    "success": True,
                    "sun": new_sun,
                    "message": "new",
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                }
                sql = f"insert into suns(cur_sys_id, uid, tid, sun, created_at, updated_at) values({cur_sys_id}, '{uid}', '{tid}', '{new_sun}', '{datetime.now()}', '{datetime.now()}')"
        cursor.execute(sql)
        db.commit()        
            
    except Exception as e:
        data["success"] = False
        data["data"] = str(e)
    return data
        
def service_in(form, db):
    state = State()
    try:
        sun = form["sun"].value
        cursor = db.cursor(dictionary=True)
        sql = f"select * from suns where sun = '{sun}'"
        cursor.execute(sql)
        suns = cursor.fetchall()
        if len(suns) == 0:
            data = {
                "success": False,
                "error_code": "USER_NOT_FOUND"
            }
        else:
            sun = suns[-1]
            if (datetime.now() - sun.get("updated_at")).total_seconds() / 3600 < delay_hour:
                if state.service_semaphore:
                    data = {
                        "success": False,
                        "error_code": "INUSE"
                    }
                else:
                    sql = f"update suns set updated_at = '{datetime.now()}' where id={sun["id"]}"
                    cursor.execute(sql)
                    db.commit()
                    state.service_semaphore = True
                    data = {
                        "success": True,
                        "uid": sun["uid"],
                        "curSysID": sun["cur_sys_id"]
                    }
            else:
                data = {
                    "success": False,
                    "error_code": "USER_NOT_FOUND"
                }
                
        
    except Exception as e:
        data = {
            "success": False,
            "data": str(e)
        }
    return data
        
def service_out(form, db):
    try:
        sun = form["sun"].value
        gram = form["gram"].value
        max_sales_amount = form["max_sales_amount"].value
        cur_sys_id = form["currency_id"].value
        cursor = db.cursor(dictionary=True)
        sql = f"select * from suns where sun = '{sun}'"
        cursor.execute(sql)
        suns = cursor.fetchall()
        if len(suns) == 0:
            data = {
                "success": False,
                "error_code": "INVALID_REQUEST"
            }
        else:
            sun = suns[-1]
            if (datetime.now() - sun.get("updated_at")).total_seconds() / 3600 < delay_hour:
                # update the total value
                
                sql = f"update suns set updated_at = '{datetime.now()}', cur_sys_id = {cur_sys_id}, gram = {gram}, max_sales_amount = {max_sales_amount} where id = {sun["id"]}"
                cursor.execute(sql)
                db.commit()
                state = State()
                if state.service_semaphore:
                    state.service_semaphore = False
                data = {
                    "success": True
                }
                
            else:
                data = {
                    "success": False,
                    "data": "Time exceeds from the last access"
                }
    except Exception as e:
        data = {
            "success": False,
            "data": str(e)
        }
    return data
        
def service_togo(form, db):
    try:
        sun = form["sun"].value
        gram = form["gram"].value
        cur_sys_id = form["currency_id"].value
        max_sales_amount = form["max_sales_amount"].value
        cursor = db.cursor(dictionary=True)
        sql = f"select * from suns where sun = '{sun}'"
        cursor.execute(sql)
        suns = cursor.fetchall()
        if len(suns) == 0:
            data = {
                "success": False,
                "error_code": "INVALID_REQUEST"
            }
        else:
            sun = suns[-1]
            if (datetime.now() - sun.get("updated_at")).total_seconds() / 3600 < delay_hour:
                state = State()
                if state.service_togo_semaphore:
                    data = {
                        "success": False,
                        "error_code": "INUSE"
                    }
                else:
                    # update total value with currency_id and max_sales_amount
                    sql = f"update suns set updated_at = '{datetime.now()}', cur_sys_id={cur_sys_id}, gram = {gram}, max_sales_amount = {max_sales_amount} WHERE id = {sun["id"]}"
                    cursor.execute(sql)
                    db.commit()
                    
                    sql = f"SELECT cur_sys_id, uid FROM suns where id = {sun["id"]}"
                    cursor.execute(sql)
                    results = cursor.fetchall()
                    uid = results[0]["uid"] if len(results) == 1 else ""
                    cur_sys_id = results[0]["cur_sys_id"] if len(results) == 1 else ""
                    state = State()
                    if state.service_togo_semaphore:
                        state.service_togo_semaphore = False
                    data = {
                        "success": True,
                        "uid": uid,
                        "cur_sys_id": cur_sys_id
                    }
            else:
                data = {
                    "success": False,
                    "data": "time exceeds from the last access"
                }
    except Exception as e:
        data = {
            "success": False,
            "data": str(e)
        }
    return data
        
def refresh_db(db):
    try:
        cursor = db.cursor(dictionary = True)
        sql = f"DELETE FROM suns WHERE updated_at <= DATE_SUB(NOW(), INTERVAL {os.getenv("REFRESH_MONTH")} MONTH)"
        cursor.execute(sql)
        db.commit()
        
        sql = f"DELETE FROM onetime_suns WHERE updated_at <= DATE_SUB(NOW(), INTERVAL {os.getenv("REFRESH_MONTH")} MONTH)"
        cursor.execute(sql)
        db.commit()
    except Exception as e:
        print(e)
        return { "success": False }
    return { 
            "success": True 
    }

def life_signal(form, db):
    try:
        cursor = db.cursor(dictionary=True)
        ip_address = os.environ.get('REMOTE_ADDR', 'Unknown')
        tid = form["tid"].value or ""
        sql = f"INSERT into logs(ip_address, tid, command, received_json, sent_json, created_at, updated_at) VALUES('{ip_address}', '{tid}', 'life_signal', '', '', '{datetime.now()}', '{datetime.now()}')"
        cursor.execute(sql)
        db.commit()
        return { "success": True }
    except Exception as e:
        return { "success": False, "message": str(e) }

def certificate(form, db):
    target_tid = form.getfirst("target_tid", "").strip()
    target_auth = form.getfirst("target_auth", "").strip()
    sql = f"SELECT * FROM terminals WHERE tid = '{target_tid}'"
    cursor = db.cursor(dictionary=True)
    cursor.execute(sql)
    terminals = cursor.fetchall()
    if len(terminals) == 0:
        return { "success": False, "data": "No target terminal id!" }
    elif len(terminals) > 1:
        return { "success": False, "data": "Duplicate target terminal id" }
    else:
        auth = terminals[0]["token"]
        if target_auth == auth:
            return { "success": True }
        else:
            return { "success": False }


handle()
