# Automobile Spare Parts Shop Automation System (ASPAS)
# Full-featured GUI: Inventory, Vendor Management, Sales Recording, Reports

import sqlite3
import json
import csv
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox
import uuid
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os


STORAGE_MODE = 'sqlite'
DB_NAME = ':memory:' if STORAGE_MODE == 'memory' else 'aspas.db'

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

current_user = {'username': 'admin', 'role': 'admin'}


# Setup database function
def setup_database():
    cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id TEXT PRIMARY KEY,
        part_name TEXT,
        manufacturer TEXT,
        vehicle_type TEXT,
        stock INTEGER,
        price REAL,
        initial_stock INTEGER DEFAULT 0 
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS vendors (
        id TEXT PRIMARY KEY,
        name TEXT,
        contact TEXT,
        parts TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS sales (
        id TEXT PRIMARY KEY,
        part_id TEXT,
        quantity INTEGER,
        amount REAL,
        date TEXT,
        payment_method TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT,
        role TEXT
    )''')
    
    # Create audit log table
    cursor.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id TEXT PRIMARY KEY,
        action_type TEXT,
        action_details TEXT,
        timestamp TEXT,
        username TEXT,
        user_role TEXT
    )''')
    
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", [
            ("admin", "admin123", "admin"),
            ("employee1", "emp123", "employee")
        ])
    conn.commit()


# Generate uuid function
def generate_uuid():
    return str(uuid.uuid4())[:8]


# Generate inventory id function
def generate_inventory_id():
    suffix = str(uuid.uuid4().int)[:3]
    return f"I-ATIL{suffix}"


# Generate vendor id function
def generate_vendor_id():
    suffix = str(uuid.uuid4().int)[:3]
    return f"V-ATIL{suffix}"


# Generate sale id function
def generate_sale_id():
    suffix = str(uuid.uuid4().int)[:3]
    return f"S-ATIL{suffix}"


# Generate audit id function
def generate_audit_id():
    suffix = str(uuid.uuid4().int)[:6]
    return f"A-ATIL{suffix}"


# Add audit log function
def add_audit_log(action_type, action_details):
    audit_id = generate_audit_id()
    timestamp = datetime.now().isoformat()
    username = current_user['username']
    user_role = current_user['role']
    
    cursor.execute("""
        INSERT INTO audit_log (id, action_type, action_details, timestamp, username, user_role)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (audit_id, action_type, action_details, timestamp, username, user_role))
    conn.commit()


# Add inventory function
def add_inventory(part_name, manufacturer, vehicle_type, stock, price):
    inv_id = generate_inventory_id()
    cursor.execute("INSERT INTO inventory (id, part_name, manufacturer, vehicle_type, stock, price, initial_stock) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (inv_id, part_name, manufacturer, vehicle_type, stock, price, stock))
    conn.commit()
    
    # Add audit log entry
    action_details = f"Added part '{part_name}' (ID: {inv_id}), Stock: {stock}, Price: {price}"
    add_audit_log("ADD_INVENTORY", action_details)
    
    refresh_inventory_table()
    # Refresh the part dropdown if it exists
    if 'sale_pid' in globals():
        populate_part_dropdown()


# Delete inventory function
def delete_inventory(item_id):
    # Get part details before deleting for the audit log
    cursor.execute("SELECT part_name FROM inventory WHERE id = ?", (item_id,))
    result = cursor.fetchone()
    part_name = result[0] if result else "Unknown Part"
    
    cursor.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
    conn.commit()
    
    # Add audit log entry
    action_details = f"Deleted part '{part_name}' (ID: {item_id})"
    add_audit_log("DELETE_INVENTORY", action_details)
    
    refresh_inventory_table()
    # Refresh the part dropdown if it exists
    if 'sale_pid' in globals():
        populate_part_dropdown()


# Refresh inventory table function
def refresh_inventory_table():
    # Clear current table content
    for row in inventory_table.get_children():
        inventory_table.delete(row)
    
    # Fetch the latest data from the inventory table
    cursor.execute("SELECT * FROM inventory")
    rows = cursor.fetchall()
    for row in rows:
        inventory_table.insert('', 'end', values=row)  # Insert each row into the table


# Check and auto order function
def check_and_auto_order():
    cursor.execute("SELECT id, part_name, stock, initial_stock FROM inventory")
    parts = cursor.fetchall()

    for part in parts:
        part_id, name, stock, initial_stock = part
        threshold = initial_stock * 0.3  # 30% of initial stock
        if stock <= threshold:
            # Trigger auto-order logic
            print(f"Auto-order triggered for {name} (Stock: {stock}, Threshold: {threshold})")
            # Simulating an order by increasing stock to the initial value
            new_stock = initial_stock
            cursor.execute("UPDATE inventory SET stock = ? WHERE id = ?", (new_stock, part_id))
            conn.commit()
            
            # Add audit log entry
            action_details = f"Auto-reorder triggered for '{name}' (ID: {part_id}). Stock updated from {stock} to {new_stock}"
            add_audit_log("AUTO_REORDER", action_details)
            
            # Refresh the inventory table to show updated stock
            refresh_inventory_table()
            
            # Also refresh the part dropdown if it exists
            if 'sale_pid' in globals():
                populate_part_dropdown()

            messagebox.showinfo("Auto-Order", f"Part '{name}' is low on stock. New stock ordered.")



# Add vendor function
def add_vendor(name, contact, parts):
    ven_id = generate_vendor_id()
    cursor.execute("INSERT INTO vendors (id, name, contact, parts) VALUES (?, ?, ?, ?)", (ven_id, name, contact, parts))
    conn.commit()
    
    # Add audit log entry
    action_details = f"Added vendor '{name}' (ID: {ven_id}), Contact: {contact}, Parts: {parts}"
    add_audit_log("ADD_VENDOR", action_details)
    
    refresh_vendor_table()


# Refresh vendor table function
def refresh_vendor_table():
    for row in vendor_table.get_children():
        vendor_table.delete(row)
    cursor.execute("SELECT * FROM vendors")
    for row in cursor.fetchall():
        vendor_table.insert('', 'end', values=row)

# Function to populate the part ID dropdown in sales tab

# Populate part dropdown function
def populate_part_dropdown():
    cursor.execute("SELECT id, part_name FROM inventory WHERE stock > 0")
    parts = cursor.fetchall()
    # Format as "ID - Part Name" for better readability
    part_options = [f"{part[0]} - {part[1]}" for part in parts]
    sale_pid['values'] = part_options


# Refresh sales table function
def refresh_sales_table():
    # Clear current sales table content
    for row in sales_table.get_children():
        sales_table.delete(row)
    
    # Fetch the latest sales data from the database and include unit price
    cursor.execute("""
        SELECT s.id, s.part_id, s.quantity, i.price as unit_price, s.amount, s.date, s.payment_method 
        FROM sales s
        JOIN inventory i ON s.part_id = i.id
    """)
    for sale in cursor.fetchall():
        sales_table.insert("", "end", values=sale)



# Record sale function
def record_sale(part_id, quantity, method):
    try:
        quantity = int(quantity)
    except ValueError:
        messagebox.showerror("Invalid", "Quantity must be a number.")
        return
        
    cursor.execute("SELECT stock, price, initial_stock, part_name FROM inventory WHERE id = ?", (part_id,))
    result = cursor.fetchone()
    if not result:
        messagebox.showerror("Error", "Part not found.")
        return
        
    stock, price, initial_stock, part_name = result
    if stock < quantity:
        messagebox.showerror("Error", "Insufficient stock.")
        return
        
    new_stock = stock - quantity
    amount = quantity * price
    cursor.execute("UPDATE inventory SET stock = ? WHERE id = ?", (new_stock, part_id))
    sale_id = generate_sale_id()
    cursor.execute("INSERT INTO sales (id, part_id, quantity, amount, date, payment_method) VALUES (?, ?, ?, ?, ?, ?)",
                   (sale_id, part_id, quantity, amount, datetime.now().isoformat(), method))
    conn.commit()
    
    # Add audit log entry
    action_details = f"Sale recorded (ID: {sale_id}) for '{part_name}' (ID: {part_id}), Quantity: {quantity}, Amount: ₹{amount:.2f}"
    add_audit_log("RECORD_SALE", action_details)
    
    refresh_inventory_table()
    refresh_sales_table()
    # Refresh the part dropdown
    if 'sale_pid' in globals():
        populate_part_dropdown()
    check_and_auto_order()
    messagebox.showinfo("Success", f"Sale recorded. Amount: ₹{amount:.2f}")


# Generate reports function
def generate_reports():
    win = tk.Toplevel()
    win.title("Sales Reports")

    filter_frame = ttk.Frame(win)
    filter_frame.pack(padx=10, pady=5)

    ttk.Label(filter_frame, text="Filter by Date (YYYY-MM-DD):").pack(side="left")
    date_entry = ttk.Entry(filter_frame)
    date_entry.pack(side="left")

    text = tk.Text(win, width=80, height=20)
    text.pack(padx=10, pady=10)


# Apply filter function
    def apply_filter():
        query = "SELECT * FROM sales"
        args = []
        if date_entry.get():
            query += " WHERE date LIKE ?"
            args.append(date_entry.get() + "%")
        cursor.execute(query, args)
        rows = cursor.fetchall()
        text.delete("1.0", tk.END)
        for r in rows:
            text.insert(tk.END, f"Sale ID: {r[0]}, Part ID: {r[1]}, Qty: {r[2]}, Amount: {r[3]}, Date: {r[4]}, Payment: {r[5]}\n")

    ttk.Button(filter_frame, text="Apply Filter", command=apply_filter).pack(side="left", padx=5)
    apply_filter()
    
    # Add audit log entry
    add_audit_log("VIEW_REPORT", "Viewed sales report")


# Export monthly sales pdf function
def export_monthly_sales_pdf():
    cursor.execute("""
        SELECT strftime('%Y-%m', date) AS month, COUNT(*) as total_sales, SUM(quantity) as total_quantity, SUM(amount) as total_revenue
        FROM sales
        GROUP BY month
        ORDER BY month
    """)
    rows = cursor.fetchall()

    if not rows:
        messagebox.showinfo("No Data", "No sales data available.")
        return

    filename = "Monthly_Sales_Report.pdf"
    c = canvas.Canvas(filename, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(180, 750, "Monthly Sales Report")

    y = 700
    c.drawString(50, y, "Month")
    c.drawString(150, y, "Total Sales")
    c.drawString(270, y, "Total Qty")
    c.drawString(390, y, "Revenue (₹)")
    y -= 20

    for month, total_sales, total_quantity, total_revenue in rows:
        c.drawString(50, y, month)
        c.drawString(150, y, str(total_sales))
        c.drawString(270, y, str(total_quantity))
        c.drawString(390, y, f"{total_revenue:.2f}")
        y -= 20
        if y < 50:
            c.showPage()
            y = 750

    c.save()
    
    # Add audit log entry
    add_audit_log("EXPORT_PDF", f"Exported monthly sales report as PDF: {filename}")
    
    messagebox.showinfo("Report Generated", f"PDF saved as {os.path.abspath(filename)}")


# Function to view audit logs with filtering

# View audit logs function
def view_audit_logs():
    audit_win = tk.Toplevel()
    audit_win.title("System Audit Logs")
    audit_win.geometry("900x600")
    
    # Filter frame at the top
    filter_frame = ttk.Frame(audit_win)
    filter_frame.pack(fill="x", padx=10, pady=5)
    
    # Add filter options
    ttk.Label(filter_frame, text="Filter by:").grid(row=0, column=0, padx=5)
    
    # Action type filter
    ttk.Label(filter_frame, text="Action:").grid(row=0, column=1, padx=5)
    action_var = tk.StringVar()
    action_combo = ttk.Combobox(filter_frame, textvariable=action_var, width=15)
    cursor.execute("SELECT DISTINCT action_type FROM audit_log")
    action_types = [r[0] for r in cursor.fetchall()]
    action_combo['values'] = ["All"] + action_types
    action_combo.current(0)
    action_combo.grid(row=0, column=2, padx=5)
    
    # User filter
    ttk.Label(filter_frame, text="User:").grid(row=0, column=3, padx=5)
    user_var = tk.StringVar()
    user_combo = ttk.Combobox(filter_frame, textvariable=user_var, width=15)
    cursor.execute("SELECT DISTINCT username FROM audit_log")
    users = [r[0] for r in cursor.fetchall()]
    user_combo['values'] = ["All"] + users
    user_combo.current(0)
    user_combo.grid(row=0, column=4, padx=5)
    
    # Date filter
    ttk.Label(filter_frame, text="Date (YYYY-MM-DD):").grid(row=0, column=5, padx=5)
    date_entry = ttk.Entry(filter_frame, width=15)
    date_entry.grid(row=0, column=6, padx=5)
    
    # Create treeview to display audit logs
    log_frame = ttk.Frame(audit_win)
    log_frame.pack(fill="both", expand=True, padx=10, pady=5)
    
    # Scrollbar
    scrollbar = ttk.Scrollbar(log_frame)
    scrollbar.pack(side="right", fill="y")
    
    # Treeview
    log_tree = ttk.Treeview(log_frame, yscrollcommand=scrollbar.set, columns=("ID", "Action", "Details", "Timestamp", "User", "Role"), show="headings")
    
    # Column definitions
    log_tree.column("ID", width=80)
    log_tree.column("Action", width=120)
    log_tree.column("Details", width=300)
    log_tree.column("Timestamp", width=150)
    log_tree.column("User", width=100)
    log_tree.column("Role", width=100)
    
    # Column headings
    log_tree.heading("ID", text="Log ID")
    log_tree.heading("Action", text="Action Type")
    log_tree.heading("Details", text="Details")
    log_tree.heading("Timestamp", text="Timestamp")
    log_tree.heading("User", text="Username")
    log_tree.heading("Role", text="User Role")
    
    log_tree.pack(fill="both", expand=True)
    
    # Configure scrollbar
    scrollbar.config(command=log_tree.yview)
    
    # Function to refresh log data based on filters

# Refresh logs function
    def refresh_logs():
        # Clear current data
        for item in log_tree.get_children():
            log_tree.delete(item)
        
        # Build query based on filters
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        
        if action_var.get() != "All":
            query += " AND action_type = ?"
            params.append(action_var.get())
            
        if user_var.get() != "All":
            query += " AND username = ?"
            params.append(user_var.get())
            
        if date_entry.get():
            query += " AND timestamp LIKE ?"
            params.append(f"{date_entry.get()}%")
            
        query += " ORDER BY timestamp DESC"
        
        # Execute query and populate treeview
        cursor.execute(query, params)
        for row in cursor.fetchall():
            log_tree.insert("", "end", values=row)
        
        # Add audit log entry for viewing audit logs
        add_audit_log("VIEW_AUDIT_LOG", "Viewed system audit logs")
    
    # Export audit logs to CSV

# Export audit logs function
    def export_audit_logs():
        filename = f"audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(filename, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            # Write header
            csvwriter.writerow(["Log ID", "Action Type", "Details", "Timestamp", "Username", "User Role"])
            
            # Write data - use the same query as the current view
            query = "SELECT * FROM audit_log WHERE 1=1"
            params = []
            
            if action_var.get() != "All":
                query += " AND action_type = ?"
                params.append(action_var.get())
                
            if user_var.get() != "All":
                query += " AND username = ?"
                params.append(user_var.get())
                
            if date_entry.get():
                query += " AND timestamp LIKE ?"
                params.append(f"{date_entry.get()}%")
                
            query += " ORDER BY timestamp DESC"
            
            cursor.execute(query, params)
            csvwriter.writerows(cursor.fetchall())
        
        # Add audit log entry
        add_audit_log("EXPORT_AUDIT_LOG", f"Exported audit logs to CSV: {filename}")
        
        messagebox.showinfo("Export Complete", f"Audit logs exported to {filename}")
    
    # Button frame
    button_frame = ttk.Frame(audit_win)
    button_frame.pack(fill="x", padx=10, pady=5)
    
    ttk.Button(button_frame, text="Apply Filters", command=refresh_logs).pack(side="left", padx=5)
    ttk.Button(button_frame, text="Export to CSV", command=export_audit_logs).pack(side="left", padx=5)
    
    # Load initial data
    refresh_logs()


# Function to calculate average weekly demand for each part
def calculate_weekly_demand():
    weekly_demand_win = tk.Toplevel()
    weekly_demand_win.title("Weekly Demand Analysis")
    weekly_demand_win.geometry("900x600")
    
    # Create frames for filters and results
    filter_frame = ttk.Frame(weekly_demand_win)
    filter_frame.pack(fill="x", padx=10, pady=5)
    
    # Add filter options
    ttk.Label(filter_frame, text="Filter by:").grid(row=0, column=0, padx=5)
    
    # Date range filter
    ttk.Label(filter_frame, text="Start Date (YYYY-MM-DD):").grid(row=0, column=1, padx=5)
    start_date_entry = ttk.Entry(filter_frame, width=15)
    start_date_entry.grid(row=0, column=2, padx=5)
    
    ttk.Label(filter_frame, text="End Date (YYYY-MM-DD):").grid(row=0, column=3, padx=5)
    end_date_entry = ttk.Entry(filter_frame, width=15)
    end_date_entry.grid(row=0, column=4, padx=5)
    
    # Part filter (optional)
    ttk.Label(filter_frame, text="Part ID (optional):").grid(row=0, column=5, padx=5)
    part_entry = ttk.Entry(filter_frame, width=15)
    part_entry.grid(row=0, column=6, padx=5)
    
    # Create treeview to display weekly demand data
    result_frame = ttk.Frame(weekly_demand_win)
    result_frame.pack(fill="both", expand=True, padx=10, pady=5)
    
    # Scrollbars
    y_scrollbar = ttk.Scrollbar(result_frame)
    y_scrollbar.pack(side="right", fill="y")
    
    x_scrollbar = ttk.Scrollbar(result_frame, orient="horizontal")
    x_scrollbar.pack(side="bottom", fill="x")
    
    # Treeview with column definitions
    weekly_tree = ttk.Treeview(
        result_frame, 
        yscrollcommand=y_scrollbar.set,
        xscrollcommand=x_scrollbar.set,
        columns=("Part ID", "Part Name", "Week", "Total Quantity", "Avg Daily", "Max Day", "Min Day", "Week Trend"),
        show="headings"
    )
    
    # Configure scrollbars
    y_scrollbar.config(command=weekly_tree.yview)
    x_scrollbar.config(command=weekly_tree.xview)
    
    # Column definitions and headings
    weekly_tree.column("Part ID", width=80)
    weekly_tree.column("Part Name", width=150)
    weekly_tree.column("Week", width=100)
    weekly_tree.column("Total Quantity", width=100)
    weekly_tree.column("Avg Daily", width=100)
    weekly_tree.column("Max Day", width=100)
    weekly_tree.column("Min Day", width=100)
    weekly_tree.column("Week Trend", width=100)
    
    weekly_tree.heading("Part ID", text="Part ID")
    weekly_tree.heading("Part Name", text="Part Name")
    weekly_tree.heading("Week", text="Week (YYYY-WW)")
    weekly_tree.heading("Total Quantity", text="Total Qty")
    weekly_tree.heading("Avg Daily", text="Avg Daily")
    weekly_tree.heading("Max Day", text="Max Day")
    weekly_tree.heading("Min Day", text="Min Day")
    weekly_tree.heading("Week Trend", text="Week Trend")
    
    weekly_tree.pack(fill="both", expand=True)
    
    # Chart frame for visualization
    chart_frame = ttk.LabelFrame(weekly_demand_win, text="Weekly Demand Chart")
    chart_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Function to calculate and display weekly demand
    def analyze_weekly_demand():
        # Clear current data
        for item in weekly_tree.get_children():
            weekly_tree.delete(item)
        
        # Clear previous chart if exists
        for widget in chart_frame.winfo_children():
            widget.destroy()
        
        # Build base query to get sales data grouped by part and week
        query_parts = [
            "SELECT s.part_id, i.part_name,",
            "strftime('%Y-%W', s.date) AS week,",
            "SUM(s.quantity) AS total_quantity,",
            "ROUND(AVG(s.quantity), 2) AS avg_daily",
            "FROM sales s",
            "JOIN inventory i ON s.part_id = i.id",
            "WHERE 1=1"
        ]
        
        params = []
        
        # Add date filters if provided
        if start_date_entry.get():
            query_parts.append("AND s.date >= ?")
            params.append(start_date_entry.get())
        
        if end_date_entry.get():
            query_parts.append("AND s.date <= ?")
            params.append(end_date_entry.get() + " 23:59:59")  # Include entire day
        
        # Add part filter if provided
        if part_entry.get():
            query_parts.append("AND s.part_id = ?")
            params.append(part_entry.get())
        
        # Group by part and week
        query_parts.append("GROUP BY s.part_id, week")
        query_parts.append("ORDER BY s.part_id, week")
        
        query = " ".join(query_parts)
        
        # Execute query
        cursor.execute(query, params)
        weekly_data = cursor.fetchall()
        
        if not weekly_data:
            messagebox.showinfo("No Data", "No sales data available for the selected filters.")
            return
        
        # Additional data for min/max and trends
        part_week_data = {}
        
        # Process each result
        for part_id, part_name, week, total_qty, avg_daily in weekly_data:
            # Get daily sales for this part and week to calculate min/max
            week_start = datetime.strptime(f"{week}-1", "%Y-%W-%w").strftime("%Y-%m-%d")
            week_end = (datetime.strptime(f"{week}-1", "%Y-%W-%w") + timedelta(days=6)).strftime("%Y-%m-%d")
            
            cursor.execute("""
                SELECT strftime('%Y-%m-%d', date) AS sale_date, SUM(quantity) AS day_qty
                FROM sales
                WHERE part_id = ? AND date >= ? AND date <= ?
                GROUP BY sale_date
                ORDER BY sale_date
            """, (part_id, week_start, week_end))
            
            daily_sales = cursor.fetchall()
            
            # Calculate min/max
            if daily_sales:
                daily_qtys = [qty for _, qty in daily_sales]
                max_day = max(daily_qtys) if daily_qtys else 0
                min_day = min(daily_qtys) if daily_qtys else 0
            else:
                max_day = min_day = 0
            
            # Calculate trend (compare with previous week if available)
            if part_id not in part_week_data:
                part_week_data[part_id] = []
            
            trend = "—"  # Default: no change
            if part_week_data[part_id]:
                prev_qty = part_week_data[part_id][-1][3]  # total_qty from previous week
                if total_qty > prev_qty:
                    trend = "↑"  # Increasing
                elif total_qty < prev_qty:
                    trend = "↓"  # Decreasing
            
            # Store data for trend calculation of future weeks
            part_week_data[part_id].append((part_id, part_name, week, total_qty))
            
            # Insert into tree
            weekly_tree.insert("", "end", values=(
                part_id, part_name, week, total_qty, avg_daily, max_day, min_day, trend
            ))
        
        # Create visualization
        create_demand_chart(weekly_data)
        
        # Add audit log entry
        add_audit_log("VIEW_WEEKLY_DEMAND", "Analyzed weekly demand for parts")
    
    # Function to create demand chart
    def create_demand_chart(weekly_data):
        # Group data by part
        part_data = {}
        for part_id, part_name, week, total_qty, _ in weekly_data:
            if part_id not in part_data:
                part_data[part_id] = {"name": part_name, "weeks": [], "quantities": []}
            
            part_data[part_id]["weeks"].append(week)
            part_data[part_id]["quantities"].append(total_qty)
        
        # Create figure
        fig, ax = plt.subplots(figsize=(8, 4))
        
        # Plot line for each part (limit to top 5 parts for clarity)
        colors = ['b', 'g', 'r', 'c', 'm', 'y']
        
        # Sort parts by total quantity sold
        sorted_parts = sorted(
            part_data.items(), 
            key=lambda x: sum(x[1]["quantities"]), 
            reverse=True
        )
        
        # Take top 5 parts only
        top_parts = sorted_parts[:5]
        
        for i, (part_id, data) in enumerate(top_parts):
            color = colors[i % len(colors)]
            ax.plot(data["weeks"], data["quantities"], marker='o', linestyle='-', 
                    color=color, label=f"{data['name']} ({part_id})")
        
        ax.set_title("Weekly Demand by Part")
        ax.set_xlabel("Week")
        ax.set_ylabel("Quantity Sold")
        ax.legend(loc='upper left', bbox_to_anchor=(1, 1))
        ax.tick_params(axis='x', rotation=45)
        fig.tight_layout()
        
        # Embed in tkinter window
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

        plt.close(fig)  # Frees memory by closing the figure
    
    # Function to export weekly demand data as CSV
    def export_weekly_demand():
        filename = f"weekly_demand_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Build query similar to the one in analyze_weekly_demand
        query_parts = [
            "SELECT s.part_id, i.part_name,",
            "strftime('%Y-%W', s.date) AS week,",
            "SUM(s.quantity) AS total_quantity,",
            "ROUND(AVG(s.quantity), 2) AS avg_daily",
            "FROM sales s",
            "JOIN inventory i ON s.part_id = i.id",
            "WHERE 1=1"
        ]
        
        params = []
        
        if start_date_entry.get():
            query_parts.append("AND s.date >= ?")
            params.append(start_date_entry.get())
        
        if end_date_entry.get():
            query_parts.append("AND s.date <= ?")
            params.append(end_date_entry.get() + " 23:59:59")
        
        if part_entry.get():
            query_parts.append("AND s.part_id = ?")
            params.append(part_entry.get())
        
        query_parts.append("GROUP BY s.part_id, week")
        query_parts.append("ORDER BY s.part_id, week")
        
        query = " ".join(query_parts)
        cursor.execute(query, params)
        weekly_data = cursor.fetchall()
        
        if not weekly_data:
            messagebox.showinfo("No Data", "No data available to export.")
            return
            
        with open(filename, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            # Write header
            csvwriter.writerow(["Part ID", "Part Name", "Week", "Total Quantity", "Average Daily"])
            # Write data
            csvwriter.writerows(weekly_data)
        
        # Add audit log entry
        add_audit_log("EXPORT_WEEKLY_DEMAND", f"Exported weekly demand report to CSV: {filename}")
        
        messagebox.showinfo("Export Complete", f"Weekly demand data exported to {filename}")
    
    # Button frame
    button_frame = ttk.Frame(filter_frame)
    button_frame.grid(row=1, column=0, columnspan=7, pady=5)
    
    ttk.Button(button_frame, text="Analyze Demand", command=analyze_weekly_demand).pack(side="left", padx=5)
    ttk.Button(button_frame, text="Export to CSV", command=export_weekly_demand).pack(side="left", padx=5)
    
    # Make some fields optional but with defaults
    current_date = datetime.now()
    # Default to previous 4 weeks
    start_date = (current_date - timedelta(days=28)).strftime('%Y-%m-%d')
    end_date = current_date.strftime('%Y-%m-%d')
    
    start_date_entry.insert(0, start_date)
    end_date_entry.insert(0, end_date)
    
    # Load initial data with default dates
    analyze_weekly_demand()


# === REPORTS TAB (Admin only) ===

# Create reports tab function
def create_reports_tab(notebook):
    report_tab = ttk.Frame(notebook)
    notebook.add(report_tab, text="Reports")

    # Sales reports section
    sales_frame = ttk.LabelFrame(report_tab, text="Sales Reports")
    sales_frame.pack(fill="x", padx=20, pady=10, anchor="w")

    ttk.Button(sales_frame, text="View Sales Report", command=generate_reports).pack(side="left", padx=10, pady=10)
    ttk.Button(sales_frame, text="Export Monthly Sales PDF", command=export_monthly_sales_pdf).pack(side="left", padx=10, pady=10)
    ttk.Button(sales_frame, text="Weekly Demand Analysis", command=calculate_weekly_demand).pack(side="left", padx=10, pady=10)

    # Monthly Sales Chart Section
    chart_frame = ttk.LabelFrame(report_tab, text="Monthly Sales Chart")
    chart_frame.pack(fill="both", expand=True, padx=20, pady=10)

    def draw_sales_chart():
        cursor.execute("""
            SELECT strftime('%Y-%m', date) as month, SUM(amount) as revenue
            FROM sales
            GROUP BY month
            ORDER BY month
        """)
        data = cursor.fetchall()
        if not data:
            messagebox.showinfo("No Data", "No sales data available for chart.")
            return

        months = [d[0] for d in data]
        revenues = [d[1] for d in data]

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(months, revenues, color='skyblue')
        ax.set_title("Monthly Revenue")
        ax.set_xlabel("Month")
        ax.set_ylabel("Revenue (₹)")
        ax.tick_params(axis='x', rotation=45)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

    ttk.Button(chart_frame, text="Show Sales Chart", command=draw_sales_chart).pack(pady=5)

    # Audit logs section
    audit_frame = ttk.LabelFrame(report_tab, text="System Audit Logs")
    audit_frame.pack(fill="x", padx=20, pady=10, anchor="w")

    ttk.Button(audit_frame, text="View Audit Logs", command=view_audit_logs).pack(side="left", padx=10, pady=10)


# Record sale from customer view function
def record_sale_from_customer_view(part_id, quantity, method):
    try:
        quantity = int(quantity)
    except ValueError:
        messagebox.showerror("Invalid", "Quantity must be a number.")
        return
        
    cursor.execute("SELECT stock, part_name FROM inventory WHERE id = ?", (part_id,))
    result = cursor.fetchone()
    if not result or result[0] < quantity:
        messagebox.showerror("Error", "Insufficient stock.")
        return
        
    stock, part_name = result
    
    cursor.execute("UPDATE inventory SET stock = stock - ? WHERE id = ?", (quantity, part_id))
    sale_id = generate_sale_id()
    cursor.execute("INSERT INTO sales (id, part_id, quantity, date, payment_method) VALUES (?, ?, ?, ?, ?)",
                   (sale_id, part_id, quantity, datetime.now().isoformat(), method))
    conn.commit()
    
    # Add audit log entry
    action_details = f"Customer sale recorded for '{part_name}' (ID: {part_id}), Quantity: {quantity}"
    add_audit_log("CUSTOMER_SALE", action_details)
    
    refresh_inventory_table()
    refresh_sales_table()
    messagebox.showinfo("Order Confirmed", f"Sale recorded successfully for Part ID {part_id}.")


# Login screen function
def login_screen():
    login_win = tk.Tk()
    login_win.title("ASPAS Login")
    login_win.geometry("300x200")

    ttk.Label(login_win, text="Username:").pack(pady=5)
    username_entry = ttk.Entry(login_win)
    username_entry.pack(pady=5)

    ttk.Label(login_win, text="Password:").pack(pady=5)
    password_entry = ttk.Entry(login_win, show="*")
    password_entry.pack(pady=5)


# Authenticate function
    def authenticate():
        username = username_entry.get()
        password = password_entry.get()
        cursor.execute("SELECT role FROM users WHERE username = ? AND password = ?", (username, password))
        result = cursor.fetchone()
        if result:
            global current_user
            current_user = {'username': username, 'role': result[0]}
            
            # Add audit log entry for login
            add_audit_log("LOGIN", f"User login: {username} ({result[0]})")
            
            login_win.destroy()
            build_gui()
        else:
            messagebox.showerror("Login Failed", "Invalid credentials.")
            
            # Optionally log failed login attempts
            # add_audit_log("FAILED_LOGIN", f"Failed login attempt for username: {username}")

    ttk.Button(login_win, text="Login", command=authenticate).pack(pady=10)

    login_win.mainloop()


# Build gui function
def build_gui():
    root = tk.Tk()
    root.title(f"ASPAS System - {current_user['username']} ({current_user['role']})")

    notebook = ttk.Notebook(root)
    notebook.pack(expand=True, fill='both')

    # === INVENTORY TAB ===
    inv_tab = ttk.Frame(notebook)
    notebook.add(inv_tab, text="Inventory")

    global inventory_table
    inventory_table = ttk.Treeview(inv_tab, columns=("ID", "Part Name", "Manufacturer", "Vehicle Type", "Stock", "Price"), show='headings')
    for col in inventory_table["columns"]:
        inventory_table.heading(col, text=col)
    inventory_table.pack(pady=10, fill="both", expand=True)

    frm_inv = ttk.Frame(inv_tab)
    frm_inv.pack(pady=10)

    entries = {}
    for i, label in enumerate(["Part Name", "Manufacturer", "Vehicle Type", "Stock", "Price"]):
        ttk.Label(frm_inv, text=label).grid(row=i, column=0, sticky='e', padx=5, pady=2)
        entry = ttk.Entry(frm_inv)
        entry.grid(row=i, column=1, padx=5, pady=2)
        entries[label] = entry


# Handle add function
    def handle_add():
        try:
            stock_str = entries["Stock"].get()
            price_str = entries["Price"].get()

            if not stock_str.strip().isdigit():
                raise ValueError("Stock must be a positive number.")
            if not price_str.strip().replace('.', '', 1).isdigit():
                raise ValueError("Price must be a valid number.")

            stock = int(stock_str)
            price = float(price_str)

            add_inventory(entries["Part Name"].get(), entries["Manufacturer"].get(),
                      entries["Vehicle Type"].get(), stock, price)
        except ValueError as ve:
            messagebox.showerror("Error", str(ve))

    ttk.Button(frm_inv, text="Add Inventory", command=handle_add).grid(row=6, columnspan=2, pady=5)
    ttk.Button(frm_inv, text="Delete Selected", command=lambda: delete_inventory(
        inventory_table.item(inventory_table.selection()[0])['values'][0] if inventory_table.selection() else None)).grid(row=7, columnspan=2, pady=5)

    refresh_inventory_table()

   # === SALES TAB (All users) ===
    sales_tab = ttk.Frame(notebook)
    notebook.add(sales_tab, text="Sales")

    ttk.Label(sales_tab, text="Part ID").pack(pady=5)
    global sale_pid
    # Use a combobox instead of a text entry for Part ID
    sale_pid = ttk.Combobox(sales_tab, width=30)
    sale_pid.pack(pady=5)
    # Populate the dropdown initially
    populate_part_dropdown()

    ttk.Label(sales_tab, text="Quantity").pack(pady=5)
    sale_qty = ttk.Entry(sales_tab)
    sale_qty.pack(pady=5)

    ttk.Label(sales_tab, text="Payment Method").pack(pady=5)
    sale_method = ttk.Entry(sales_tab)
    sale_method.pack(pady=5)

    # Handle sale button click

# Handle sale function
    def handle_sale():
        selected = sale_pid.get()
        if selected:
            part_id = selected.split(' - ')[0]  # Extract just the ID portion
            try:
                quantity = int(sale_qty.get())
                record_sale(part_id, quantity, sale_method.get())
            except ValueError:
                messagebox.showerror("Error", "Quantity must be a number.")
        else:
            messagebox.showerror("Error", "Please select a part.")

    ttk.Button(sales_tab, text="Record Sale", command=handle_sale).pack(pady=10)

    global sales_table
    # Update the sales table to include Unit Price column
    sales_table = ttk.Treeview(sales_tab, columns=("ID", "Part ID", "Quantity", "Unit Price", "Amount", "Date", "Payment Method"), show='headings')

    # Define headings and optional column widths
    for col in sales_table["columns"]:
        sales_table.heading(col, text=col)
        sales_table.column(col, anchor='center', width=100)

    sales_table.pack(pady=10, fill="both", expand=True)

    refresh_sales_table()


    # === VENDOR TAB (Admin only) ===
    if current_user['role'] == 'admin':
        vendor_tab = ttk.Frame(notebook)
        notebook.add(vendor_tab, text="Vendors")

        global vendor_table
        vendor_table = ttk.Treeview(vendor_tab, columns=("ID", "Name", "Contact", "Parts"), show='headings')
        for col in vendor_table["columns"]:
            vendor_table.heading(col, text=col)
        vendor_table.pack(pady=10, fill="both", expand=True)

        frm_ven = ttk.Frame(vendor_tab)
        frm_ven.pack(pady=10)

        ven_name = ttk.Entry(frm_ven)
        ven_contact = ttk.Entry(frm_ven)
        ven_parts = ttk.Entry(frm_ven)

        for i, (lbl, ent) in enumerate(zip(["Name", "Contact", "Parts"], [ven_name, ven_contact, ven_parts])):
            ttk.Label(frm_ven, text=lbl).grid(row=i, column=0, sticky='e', padx=5)
            ent.grid(row=i, column=1, padx=5)

        ttk.Button(frm_ven, text="Add Vendor", command=lambda: add_vendor(ven_name.get(), ven_contact.get(), ven_parts.get())).grid(row=3, columnspan=2, pady=5)

        refresh_vendor_table()
        # === REPORTS TAB (Admin only) ===
        create_reports_tab(notebook)

    # === LOGOUT BUTTON (All users) ===

# Handle logout function
    def handle_logout():
        # Add audit log entry for logout
        add_audit_log("LOGOUT", f"User logout: {current_user['username']}")
        
        root.destroy()
        login_screen()

    ttk.Button(root, text="Logout", command=handle_logout).pack(pady=10)

    root.geometry("800x600")
    root.mainloop()

if __name__ == '__main__':
    setup_database()
    login_screen()