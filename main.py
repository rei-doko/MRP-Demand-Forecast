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
        FOREIGN KEY (child_product_id) REFERENCES material_master(product_id) ON DELETE CASCADE,
    )
    """

    cursor.execute(create_material_master)
    cursor.execute(create_inventory)
    cursor.execute(create_bill_of_materials)

    connection.commit()
    connection.close()
    
    return

create_database()

def material_master_insert(product_id, product_name):
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    try:
        cursor.execute("""
         INSERT INTO material_master(product_id, product_name)
        VALUES (?, ?)                  
        """, (product_id, product_name))
        connection.commit()
        print(f"Added {product_name} with ID {product_id} to material_master.")
    except sqlite3.IntegrityError as e:
        print(f"Error adding product: {e}")
    finally:
        connection.close()

def inventory_insert(product_id, quantity):
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    try:
        cursor.execute("""
            INSERT INTO inventory(product_id, quantity)
            VALUES (?, ?)
        """, (product_id, quantity))
        connection.commit()
    except sqlite3.IntegrityError as e:
        print(f"Error adding product: {e}")
    finally:
        connection.close()

def bill_of_materials_insert(parent_id, child_id, quantity_required):
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    try:
        cursor.execute("""
            INSERT INTO bom(parent_product_id, child_product_id, quantity_required)
            VALUES (?, ?, ?)
        """, (parent_id, child_id, quantity_required))
        connection.commit()
        print(f"Added BOM entry: parent {parent_id}, child {child_id}, quantity {quantity_required}.")
    except sqlite3.IntegrityError as e:
        print(f"Error adding product: {e}")
    finally:
        connection.close()

@app.route('/main')
def main():
    print("Welcome! Enter data into database. \n")
    while True:
        print("\n Choose action:")
        print("1 - Add product to material_master")
        print("2 - Add inventory")
        print("3 - Add BOM entry")
        print("q - Quit")

        choice = input("Enter choice: ").strip().lower()
        if choice == '1':
            product_id = int(input("Enter product ID (integer): "))
            product_name = input("Enter product name: ").strip()
            material_master_insert(product_id, product_name)
        elif choice == '2':
            product_id = int(input("Enter product ID (must exist in material_master): "))
            quantity = int(input("Enter quantity: "))
            inventory_insert(product_id, quantity)
        elif choice == '3':
            parent_id = int(input("Enter parent product ID: "))
            child_id = int(input("Enter child product ID: "))
            quantity_required = int(input("Enter quantity required: "))
            bill_of_materials_insert(parent_id, child_id, quantity_required)
        elif choice == 'q':
            print("Goodbye!")
            break
        else:
            print("Invalid choice, try again.")

if __name__ == "__main__":
    app.run(debug=True)
    #gui.run()