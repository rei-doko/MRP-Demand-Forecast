# Dependencies
from flask import Flask, render_template, Response, jsonify, request, redirect, url_for
from datetime import datetime
import flaskwebgui
import sqlite3
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
    # Render homepage
    return render_template("index.html")

def ensure_database():
    # Create file + folder if missing
    if not os.path.exists(db_path):
        os.makedirs(db_folder, exist_ok=True)
        connection = sqlite3.connect(db_path)
        connection.close()

    # Connect and ensure tables exist
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
            product_id INTEGER PRIMARY KEY,
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

    # Trigger to auto-create inventory row when material is added
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS create_inventory_after_material
        AFTER INSERT ON material_master
        BEGIN
            INSERT INTO inventory(product_id, quantity)
            VALUES (NEW.product_id, 0);
        END;
    """)

    connection.commit()
    connection.close()

# Ensure DB and tables exist
ensure_database()   

@app.route("/materials", methods=["GET", "POST"])
def material_master():
    # View and add materials to the material master
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    message = None

    # Adding new material entry
    if request.method == "POST":
        product_id = int(request.form["product_id"])
        product_name = str(request.form["product_name"])
        
        # ID must be >= 0
        if product_id < 0:
            return "Product ID cannot be negative", 400
        
        # Check if product_id exists
        cursor.execute("SELECT 1 FROM material_master WHERE product_id = ?", (product_id,))
        exists = cursor.fetchone()

        if exists:
            materials_rows = cursor.execute("SELECT * FROM material_master").fetchall()
            connection.close()
            return render_template("materials_master.html",
                                   materials=materials_rows,
                                   message=f"Product ID {product_id} already exists!"
                                   )
        else:
            # Insert into material_master (inventory row will be auto-created by trigger)
            cursor.execute(
                "INSERT INTO material_master(product_id, product_name) VALUES (?, ?)",
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
    ids_to_delete = request.form.getlist("delete_ids[]")
    if ids_to_delete:
        connection = sqlite3.connect(db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.cursor()
        
        placeholders = ",".join("?" for _ in ids_to_delete)
        cursor.execute(
            f"DELETE FROM material_master WHERE product_id IN ({placeholders})",
            ids_to_delete
        )
        
        connection.commit()
        connection.close()
    
    return redirect(url_for("material_master"))

@app.route("/inventory", methods=["GET", "POST"])
def inventory():
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    message = request.args.get("message")

    if request.method == "POST":
        updates = {}
        for key, value in request.form.items():
            if key.startswith("update_quantities["):
                pid = int(key.split("[")[1].split("]")[0])
                if value.strip() == "":
                    continue
                qty = int(value)
                if qty < 0:
                    continue
                updates[pid] = qty

        for pid, qty in updates.items():
            cursor.execute(
                "UPDATE inventory SET quantity = ? WHERE product_id = ?",
                (qty, pid)
            )

        if updates:
            connection.commit()
            connection.close()
            return redirect(url_for("inventory", message="Inventory updated successfully."))
        else:
            connection.close()
            return redirect(url_for("inventory", message="No valid updates provided."))

    cursor.execute("""
        SELECT i.product_id, m.product_name, i.quantity
        FROM inventory i
        JOIN material_master m ON i.product_id = m.product_id
        ORDER BY i.product_id
    """)
    inventory_data = cursor.fetchall()
    connection.close()

    return render_template("inventory.html", inventory=inventory_data, message=message)

@app.route("/bom", methods=["GET", "POST"])
def bom():
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    if request.method == "POST":
        parent_id = int(request.form["parent_id"])
        child_ids = request.form.getlist("child_id[]")
        quantities = request.form.getlist("quantity_required[]")
        
        if parent_id < 0:
            return "Parent ID cannot be negative", 400
        
        for child_id, qty in zip(child_ids, quantities):
            if int(child_id) < 0 or int(qty) < 0:
                return "Child IDs and quantities cannot be negative", 400

        cursor.execute("SELECT COALESCE(MAX(bom_id), 0) + 1 FROM bom")
        new_bom_id = cursor.fetchone()[0]

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

    grouped_bom = {}
    for row in bom_rows:
        bom_key = (row["bom_id"], row["parent_product_id"], row["parent_name"])
        if bom_key not in grouped_bom:
            grouped_bom[bom_key] = []
        grouped_bom[bom_key].append(
            f"{row['child_product_id']} - {row['child_name']} (x{row['quantity_required']})"
        ) 

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
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.cursor()

        
        placeholders = ",".join("?" for _ in ids_to_delete)
        cursor.execute(
            f"DELETE FROM bom WHERE bom_id IN ({placeholders})",
            ids_to_delete
        )

        connection.commit()
        connection.close()

    return redirect(url_for("bom"))

@app.route("/sales", methods=["GET", "POST"])
def sales():
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    message = None
    selected_product = None
    weekly_sales = []

    if request.method == "POST":
        try:
            product_id = int(request.form["product_id"])
            week_number = int(request.form["week"])
            week_sales_amount = int(request.form["amount"])
        except (KeyError, ValueError):
            connection.close()
            message = "All fields are required and must be valid numbers!"
            product_id = None

        if product_id is not None:
            cursor.execute(
                "SELECT * FROM material_master WHERE product_id = ?", (product_id,)
            )
            product_row = cursor.fetchone()
            if not product_row:
                message = f"Product ID {product_id} does not exist."
            else:
                cursor.execute("""
                    INSERT INTO sales(product_id, week, amount)
                    VALUES (?, ?, ?)
                    ON CONFLICT(product_id, week) DO UPDATE SET amount=excluded.amount
                """, (product_id, week_number, week_sales_amount))
                connection.commit()
                connection.close()
                return redirect(url_for("sales", product_id=product_id))

    selected_product_id = request.args.get("product_id", type=int)
    if selected_product_id:
        cursor.execute(
            "SELECT * FROM material_master WHERE product_id = ?", (selected_product_id,)
        )
        selected_product = cursor.fetchone()
        if selected_product:
            cursor.execute(
                "SELECT week, amount FROM sales WHERE product_id = ? ORDER BY week",
                (selected_product_id,)
            )
            weekly_sales = cursor.fetchall()

    cursor.execute("SELECT * FROM material_master ORDER BY product_id")
    products = cursor.fetchall()
    connection.close()

    return render_template(
        "sales.html",
        products=products,
        selected_product=selected_product,
        weekly_sales=weekly_sales,
        message=message
    )

@app.route("/sales/add", methods=["POST"])
def add_sales():
    product_id = int(request.form["product_id"])
    week = int(request.form["week"])
    amount = int(request.form["amount"])

    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
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
        return redirect(url_for("sales", product_id=product_id))

    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    cursor = connection.cursor()

    placeholders = ",".join("?" for _ in delete_weeks)
    cursor.execute(
        f"DELETE FROM sales WHERE product_id = ? AND week IN ({placeholders})",
        [product_id] + delete_weeks
    )

    connection.commit()
    connection.close()

    return redirect(url_for("sales", product_id=product_id))

def get_products():
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    
    cursor.execute("SELECT * FROM material_master ORDER BY product_id")
    products = cursor.fetchall()
    
    connection.close()
    return products

@app.route("/sales/forecast", methods=["GET"])
def sales_forecast():
    product_id = request.args.get("product_id", type=int)
    if product_id is None:
        return jsonify({"error": "Missing product_id"}), 400

    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute(
        "SELECT week, amount FROM sales WHERE product_id = ? ORDER BY week",
        (product_id,)
    )
    sales_rows = cursor.fetchall()
    weekly_amounts = [row["amount"] for row in sales_rows]

    connection.close()

    def weighted_moving_average(values):
        n = len(values)
        if n == 0:
            return None
        weights = list(range(1, n + 1))
        weighted_sum = sum(s * w for s, w in zip(values, weights))
        return weighted_sum / sum(weights)

    def smape(actual_values, forecasted_values):
        errors = []
        for actual, forecast in zip(actual_values, forecasted_values):
            denominator = (abs(actual) + abs(forecast)) / 2
            if denominator == 0:
                continue
            errors.append(abs(actual - forecast) / denominator)
        return (sum(errors) / len(errors) * 100) if errors else None

    forecasted_values = []
    if len(weekly_amounts) > 1:
        for i in range(1, len(weekly_amounts)):
            forecasted_values.append(weighted_moving_average(weekly_amounts[:i]))
        smape_value = smape(weekly_amounts[1:], forecasted_values)
    else:
        smape_value = None

    next_week_prediction = weighted_moving_average(weekly_amounts) if weekly_amounts else None

    return jsonify({
        "sMAPE_percent": smape_value,
        "next_week_prediction": next_week_prediction
    })

@app.route("/requisition", methods=["GET", "POST"])
def requisition():
    requisition_list = None
    bom_id = None
    qty_needed = None
    parent_status = None
    parent_shortage = 0
    parent_name = None
    parent_inventory = 0
    error = None

    if request.method == "POST":
        bom_id = int(request.form["bom_id"])
        qty_needed = int(request.form["quantity_needed"])

        connection = sqlite3.connect(db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()

        # Check if BOM ID exists first
        cursor.execute("SELECT parent_product_id FROM bom WHERE bom_id = ? LIMIT 1", (bom_id,))
        row = cursor.fetchone()
        if not row:
            error = f"BOM ID {bom_id} does not exist."
            connection.close()
            return render_template("requisition.html", error=error)

        parent_id = row["parent_product_id"]

        # Get parent product name
        cursor.execute("SELECT product_name FROM material_master WHERE product_id = ?", (parent_id,))
        parent_name = cursor.fetchone()["product_name"]

        # Get parent inventory
        cursor.execute("SELECT quantity FROM inventory WHERE product_id = ?", (parent_id,))
        inv_row = cursor.fetchone()
        parent_inventory = inv_row["quantity"] if inv_row else 0

        if parent_inventory >= qty_needed:
            parent_status = f"No need to repurchase. {parent_name} inventory ({parent_inventory}) covers the requirement of {qty_needed}."
            requisition_list = []
        else:
            parent_shortage = qty_needed - parent_inventory
            parent_status = f"{parent_name}: Need {qty_needed}, but only {parent_inventory} in inventory. Must create {parent_shortage} more."

            # Get all child components
            cursor.execute("""
                SELECT b.child_product_id, b.quantity_required, m.product_name
                FROM bom b
                JOIN material_master m ON b.child_product_id = m.product_id
                WHERE b.bom_id = ?
            """, (bom_id,))
            children = cursor.fetchall()

            requisition_list = []
            for child in children:
                child_id = child["child_product_id"]
                child_name = child["product_name"]
                required_per_unit = child["quantity_required"]
                total_required = required_per_unit * parent_shortage

                cursor.execute("SELECT quantity FROM inventory WHERE product_id = ?", (child_id,))
                inv_row = cursor.fetchone()
                inventory_amt = inv_row["quantity"] if inv_row else 0

                shortage = max(0, total_required - inventory_amt)

                requisition_list.append({
                    "child_id": child_id,
                    "child_name": child_name,
                    "required": total_required,
                    "inventory": inventory_amt,
                    "shortage": shortage
                })

        connection.close()

    return render_template("requisition.html",
                           requisition_list=requisition_list,
                           bom_id=bom_id,
                           qty_needed=qty_needed,
                           parent_status=parent_status,
                           parent_shortage=parent_shortage,
                           parent_name=parent_name,
                           parent_inventory=parent_inventory,
                           error=error)

if __name__ == "__main__":
    USE_GUI = False
    if USE_GUI:
        gui.run()
    else:
        app.run(debug=True)
