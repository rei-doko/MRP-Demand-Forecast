#Import dependencies and libraries
from flask import Flask, render_template, Response, jsonify, request, redirect, url_for
from datetime import datetime
import numpy as py # Currently unused, but available if needed
import flaskwebgui # GUI mode
import sqlite3
import pandas as pd # Currently unused, but available if needed
import math # Currently unused, but available if needed
import time # Currently unused, but available if needed
import os

# Initialize Flask app
app = Flask(__name__)
# Initialize Flask GUI wrapper
gui = flaskwebgui.FlaskUI(app=app, server="flask", width=800, height=600)

# Define folder and file path for SQLite database
db_folder = os.path.join(app.root_path, "data")
os.makedirs(db_folder, exist_ok=True)
db_path = os.path.join(db_folder, "database.db")

@app.route("/")
def index():
    # Renders homepage
    return render_template("index.html")

def ensure_database():
    # Create file + folder if missing
    if not os.path.exists(db_path):
        os.makedirs(db_folder, exist_ok=True)
        connection = sqlite3.connect(db_path)
        connection.close()

    # Connectd and ensured tables exist
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    cursor.execute("PRAGMA foreign_keys = ON")

    # Material master table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS material_master(
            product_id INTEGER PRIMARY KEY UNIQUE NOT NULL,
            product_name TEXT NOT NULL
        )
    """)

    # Inventory table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory(
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES material_master(product_id) ON DELETE CASCADE
        )
    """)

    # BOM table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bom(
            bom_id INTEGER NOT NULL,
            parent_product_id INTEGER NOT NULL,
            child_product_id INTEGER NOT NULL,
            quantity_required INTEGER NOT NULL,
            FOREIGN KEY (parent_product_id) REFERENCES material_master(product_id) ON DELETE CASCADE,
            FOREIGN KEY (child_product_id) REFERENCES material_master(product_id) ON DELETE CASCADE
        )
    """)

    # Sales table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales(
            product_id INTEGER NOT NULL,
            week INTEGER NOT NULL,
            amount INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES material_master(product_id) ON DELETE CASCADE,
            PRIMARY KEY (product_id, week)
        )
    """)

    connection.commit()
    connection.close()

# Ensure DB and tables exist
ensure_database()   

@app.route("/materials", methods=["GET", "POST"])
def material_master():
    # View and add materials to the material master
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    message = None

    # Adding new material entry
    if request.method == "POST":
        product_id = int(request.form["product_id"])
        product_name = str(request.form["product_name"])
        
        # ID must be >= 0
        if product_id < 0:
            return "Product ID cannot be negative", 400 # 400 means bad request
        
        # Check if product_id exists
        cursor.execute("SELECT 1 FROM material_master WHERE product_id = ?", (product_id,))
        exists = cursor.fetchone()

        if exists:
            materials_rows = cursor.execute("SELECT * FROM material_master").fetchall()
            connection.close()
            return render_template("materials_master.html",
                                   materials=materials_rows,
                                   message=f"Product ID {product_id} already exists!" # Error message
                                   )
        else:
            cursor.execute("INSERT INTO material_master(product_id, product_name) VALUES (?, ?)", # Insert material
                           (product_id, product_name)
                           )
            connection.commit()
            connection.close()
            return redirect(url_for("material_master"))

    # Fetch all materials for display
    materials_rows = cursor.execute("SELECT * FROM material_master").fetchall()
    connection.close()
    return render_template("materials_master.html", materials=materials_rows, message=message)

@app.route("/materials/delete", methods=["POST"])
def delete_materials():
    # Delete selected materials from material master
    ids_to_delete = request.form.getlist("delete_ids[]")
    if ids_to_delete:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        
        # Delete all selected IDs
        placeholders = ",".join("?" for _ in ids_to_delete)
        cursor.execute(
            f"DELETE FROM material_master WHERE product_id IN ({placeholders})",
            ids_to_delete
        )
        
        connection.commit()
        connection.close()
    
    # Redirect back to material master after deletion
    return redirect(url_for("material_master"))

@app.route("/inventory", methods=["GET", "POST"])
def inventory():
    # View, add, and update inventory
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    # Adding new inventory entry
    if request.method == "POST":
        product_id = int(request.form["product_id"])
        quantity = int(request.form["quantity"])
        
        # ID and quantity must be >= 0
        if product_id < 0 or quantity < 0:
            return "Product ID and quantity cannot be negative!", 400 # 400 means bad request
        
        # Check if the product already exists in inventory
        cursor.execute("SELECT quantity FROM inventory WHERE product_id = ?", (product_id,))
        result = cursor.fetchone()

        if result: 
            # Product exists, update quantity
            new_quantity = result["quantity"] + quantity
            cursor.execute("UPDATE inventory SET quantity = ? WHERE product_id = ?", (new_quantity, product_id))
        else: 
            # Product does not exist, create insert new row
            cursor.execute("INSERT INTO inventory(product_id, quantity) VALUES (?, ?)",
                           (product_id, quantity)
                           )
        
        connection.commit()
        connection.close()
        return redirect(url_for("inventory"))

    # Fetch inventory with product names
    inventory_rows = cursor.execute("""
        SELECT m.product_id, m.product_name, i.quantity
        FROM inventory i
        JOIN material_master m ON i.product_id = m.product_id
    """).fetchall()

    connection.close()
    return render_template("inventory.html", inventory=inventory_rows)

@app.route("/inventory/delete", methods=["POST"])
def delete_inventory():
    ids_to_delete = request.form.getlist("delete_ids[]")
    if ids_to_delete:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        
        # Delete each selected inventory row
        placeholders = ",".join("?" for _ in ids_to_delete)
        cursor.execute(
            f"DELETE FROM inventory WHERE product_id IN ({placeholders})",
            ids_to_delete
        )

        connection.commit()
        connection.close()

    # Redirect back to inventory after deletion
    return redirect(url_for("inventory"))

@app.route("/bom", methods=["GET", "POST"])
def bom():
    # View and add BOM entries
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    # Adding new BOM entry
    if request.method == "POST":
        parent_id = int(request.form["parent_id"])
        child_ids = request.form.getlist("child_id[]")
        quantities = request.form.getlist("quantity_required[]")
        
        # IDs and quantities must be >= 0
        if parent_id < 0:
            return "Parent ID cannot be negative", 400
        
        for child_id, qty in zip(child_ids, quantities):
            if int(child_id) < 0 or int(qty) < 0:
                return "Child IDs and quantities cannot be negative", 400

        # Generate new BOM ID
        cursor.execute("SELECT COALESCE(MAX(bom_id), 0) + 1 FROM bom")
        new_bom_id = cursor.fetchone()[0]

        # Insert each child for the new BOM
        for child_id, qty in zip(child_ids, quantities):
            cursor.execute("""
                INSERT INTO bom(bom_id, parent_product_id, child_product_id, quantity_required)
                VALUES (?, ?, ?, ?)
            """, 
                (new_bom_id, parent_id, int(child_id), int(qty)),
            )
        connection.commit()
        connection.close()
        return redirect(url_for("bom"))

    # Fetch BOM table with product names
    bom_rows = cursor.execute("""
        SELECT b.bom_id,
               b.parent_product_id,
               m_parent.product_name AS parent_name,
               b.child_product_id,
               m_child.product_name AS child_name,
               b.quantity_required
        FROM bom b
        JOIN material_master m_parent ON b.parent_product_id = m_parent.product_id
        JOIN material_master m_child ON b.child_product_id = m_child.product_id
        ORDER by b.bom_id, b.parent_product_id
    """).fetchall()

    connection.close()

    # Group children under each BOM ID
    grouped_bom = {}
    for row in bom_rows:
        bom_key = (row["bom_id"], row["parent_product_id"], row["parent_name"])
        if bom_key not in grouped_bom:
           grouped_bom[bom_key] = []
        grouped_bom[bom_key].append(
            f"{row['child_product_id']} - {row['child_name']} (x{row['quantity_required']})"
        ) 

    # Format BOM list for template
    bom_list = [
        { 
            "bom_id": k[0],
            "parent_product_id": k[1], 
            "parent_name": k[2], 
            "children": ", ".join(v)
        }
        for k, v in grouped_bom.items()
    ]

    return render_template("bom.html", bom=bom_list)

@app.route("/bom/delete", methods=["POST"])
def delete_bom():
    ids_to_delete = request.form.getlist("delete_ids[]")
    if ids_to_delete:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        
        # Delete all selected bom_id
        placeholders = ",".join("?" for _ in ids_to_delete)
        cursor.execute(
            f"DELETE FROM bom WHERE bom_id IN ({placeholders})",
            ids_to_delete
        )

        connection.commit()
        connection.close()

    # Redirect back to bom after deletion
    return redirect(url_for("bom"))

@app.route("/sales", methods=["GET", "POST"])
def sales():
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    message = None
    selected_product = None
    sales_data = []

    # Step 1: Handle POST for adding/updating sales
    if request.method == "POST":
        try:
            product_id = int(request.form["product_id"])
            week = int(request.form["week"])
            amount = int(request.form["amount"])
        except (KeyError, ValueError):
            connection.close()
            message = "All fields are required and must be valid numbers!"
            product_id = None

        if product_id is not None:
            # Check product exists in material master
            cursor.execute("SELECT * FROM material_master WHERE product_id = ?", (product_id,))
            product_row = cursor.fetchone()
            if not product_row:
                connection.close()
                message = f"Product ID {product_id} does not exist."
            else:
                # Insert or update weekly sales
                cursor.execute("""
                    INSERT INTO sales(product_id, week, amount)
                    VALUES (?, ?, ?)
                    ON CONFLICT(product_id, week) DO UPDATE SET amount=excluded.amount
                """, (product_id, week, amount))
                connection.commit()
                return redirect(url_for("sales", product_id=product_id))

    # Step 2: Handle GET to display selected folder
    product_id_param = request.args.get("product_id", type=int)
    if product_id_param:
        cursor.execute("SELECT * FROM material_master WHERE product_id = ?", (product_id_param,))
        selected_product = cursor.fetchone()
        if selected_product:
            cursor.execute("SELECT week, amount FROM sales WHERE product_id = ? ORDER BY week", (product_id_param,))
            sales_data = cursor.fetchall()

    # Fetch all products for dropdown
    cursor.execute("SELECT * FROM material_master ORDER BY product_id")
    products = cursor.fetchall()

    connection.close()

    return render_template(
        "sales.html",
        products=products,
        selected_product=selected_product,
        sales_data=sales_data,
        message=message
    )

@app.route("/sales/add", methods=["POST"])
def add_sales():
    product_id = int(request.form["product_id"])
    week = int(request.form["week"])
    amount = int(request.form["amount"])

    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute("""
        INSERT INTO sales(product_id, week, amount)
        VALUES (?, ?, ?)
        ON CONFLICT(product_id, week) DO UPDATE SET amount=excluded.amount
    """, (product_id, week, amount))
    connection.commit()
    connection.close()
    return redirect(url_for("sales"))

@app.route("/sales/delete", methods=["POST"])
def delete_sales():
    product_id = request.form.get("product_id")
    delete_weeks = request.form.getlist("delete_weeks[]")

    if not product_id or not delete_weeks:
        # Redirect back to same folder if nothing selected
        return redirect(url_for("sales", product_id=product_id))

    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    # Delete selected weeks for this product
    placeholders = ",".join("?" for _ in delete_weeks)
    cursor.execute(
        f"DELETE FROM sales WHERE product_id = ? AND week IN ({placeholders})",
        [product_id] + delete_weeks
    )

    connection.commit()
    connection.close()

    # Redirect to same folder after deletion (GET)
    return redirect(url_for("sales", product_id=product_id))

# Helper to get all products
def get_products():
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM material_master ORDER BY product_id")
    products = cursor.fetchall()
    connection.close()
    return products

# Run Flask
if __name__ == "__main__":
    USE_GUI = False
    if USE_GUI:
        gui.run()
    else:
        app.run(debug=True)