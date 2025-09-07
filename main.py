#Import dependecies and libraries
from flask import Flask, render_template, Response, jsonify, request
from datetime import datetime
import numpy as py
import flaskwebgui
import sqlite3
import pandas as pd
import math
import time
import os

app = Flask(__name__)
gui = flaskwebgui.FlaskUI(app=app, server="flask", width=1920, height=1080)

# define folder and file
db_folder = os.path.join(app.root_path, "data")
os.makedirs(db_folder, exist_ok = True)
db_path = os.path.join(db_folder, "database.db")

@app.route("/")
def index():
    return render_template("index.html")

def create_database():
    # define connection and cursor
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    # enable foreign key support
    cursor.execute("PRAGMA foreign_keys = ON")

    # create tables

    create_material_master = """
    CREATE TABLE IF NOT EXISTS material_master(
        product_id INTEGER PRIMARY KEY UNIQUE NOT NULL,
        product_name TEXT NOT NULL
        );
    """
    
    create_inventory = """
    CREATE TABLE IF NOT EXISTS inventory(
        inventory_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (product_id) REFERENCES material_master(product_id) ON DELETE CASCADE
        );
    """

    create_bill_of_materials = """
    CREATE TABLE IF NOT EXISTS bom(
        bom_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
        parent_product_id INTEGER NOT NULL,
        child_product_id INTEGER NOT NULL,
        quantity_required INTEGER NOT NULL,
        FOREIGN KEY (parent_product_id) REFERENCES material_master(product_id) ON DELETE CASCADE,
        FOREIGN KEY (child_product_id) REFERENCES material_master(product_id) ON DELETE CASCADE
        );
    """

    cursor.execute(create_material_master)
    cursor.execute(create_inventory)
    cursor.execute(create_bill_of_materials)

    connection.commit()
    connection.close()
    
    return

create_database()    

@app.route("/materials", methods=["GET", "POST"])
def material_master():
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    if request.method == "POST":
        product_id = int(request.form["product_id"])
        product_name = str(request.form["product_name"])
        cursor.execute("INSERT OR IGNORE INTO material_master(product_id, product_name) VALUES (?, ?)",
                       (product_id, product_name))
        connection.commit()
    materials_rows = cursor.execute("SELECT * FROM material_master").fetchall()
    connection.close()
    return render_template("materials_master.html", materials=materials_rows)
        
@app.route("/inventory", methods=["GET", "POST"])
def inventory():
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    if request.method == "POST":
        product_id = int(request.form["product_id"])
        quantity = int(request.form["quantity"])
        cursor.execute("INSERT INTO inventory(product_id, quantity) VALUES (?, ?)",
                       (product_id, quantity))
        connection.commit()
    inventory_rows = cursor.execute("SELECT * FROM inventory").fetchall()
    connection.close()
    return render_template("inventory.html", inventory=inventory_rows)

@app.route("/bom", methods=["GET", "POST"])
def bom():
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    if request.method == "POST":
        parent_id = int(request.form["parent_id"])
        child_id = int(request.form["child_id"])
        quantity_required = int(request.form["quantity_required"])
        cursor.execute("""INSERT INTO bom(parent_product_id, child_product_id, quantity_required)
                          VALUES (?, ?, ?)""",
                       (parent_id, child_id, quantity_required))
        connection.commit()
    bom_rows = cursor.execute("SELECT * FROM bom").fetchall()
    connection.close()
    return render_template("bom.html", bom=bom_rows)

if __name__ == "__main__":
    app.run(debug=True)
    #gui.run()