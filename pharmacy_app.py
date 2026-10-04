# ===================================================================================
# প্রয়োজনীয় লাইব্রেরি ইম্পোর্ট করা
# ===================================================================================
import sqlite3
import tkinter
from tkinter import ttk, messagebox, Listbox
import traceback
import customtkinter
from datetime import datetime, date
import os
import webbrowser
from fpdf import FPDF
import sys
import time
import csv 
import shutil 

# ===================================================================================
# সেটিংস: প্রিন্ট করার পদ্ধতি নির্ধারণ
# ===================================================================================
PRINT_METHOD = "PDF_VIEWER" 

def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_base_path():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))
    
# ===================================================================================
# ডাটাবেসের সাথে সম্পর্কিত সব ফাংশন
# ===================================================================================
def connect_to_db():
    base_dir = get_base_path() 
    db_path = os.path.join(base_dir, "products.db")
    try:
        conn = sqlite3.connect('products.db', timeout=10) 
        cursor = conn.cursor()
        
        cursor.execute('CREATE TABLE IF NOT EXISTS products (product_code TEXT PRIMARY KEY, product_name TEXT NOT NULL, company_name TEXT, quantity INTEGER NOT NULL, unit_price REAL NOT NULL, purchase_price REAL, expiry_date TEXT)')
        cursor.execute('CREATE TABLE IF NOT EXISTS sales (sale_id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_id TEXT NOT NULL, product_code TEXT NOT NULL, product_name TEXT NOT NULL, quantity_sold INTEGER NOT NULL, price_per_unit REAL NOT NULL, total_price REAL NOT NULL, sale_date TEXT NOT NULL, FOREIGN KEY (product_code) REFERENCES products (product_code))')
        cursor.execute('CREATE TABLE IF NOT EXISTS customers (mobile TEXT PRIMARY KEY, customer_name TEXT NOT NULL, address TEXT, previous_due REAL DEFAULT 0.0)')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customer_ledger (
                ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_mobile TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                debit REAL DEFAULT 0.0,
                credit REAL DEFAULT 0.0,
                balance REAL NOT NULL,
                FOREIGN KEY (customer_mobile) REFERENCES customers (mobile)
            )
        ''')
        
        try:
            cursor.execute("SELECT generic_name FROM products LIMIT 1") 
            cursor.execute("BEGIN TRANSACTION;")
            cursor.execute("ALTER TABLE products RENAME TO products_old_temp")
            cursor.execute(''' CREATE TABLE products (product_code TEXT PRIMARY KEY, product_name TEXT NOT NULL, company_name TEXT, quantity INTEGER NOT NULL, unit_price REAL NOT NULL, purchase_price REAL, expiry_date TEXT ) ''')
            cursor.execute(''' INSERT INTO products (product_code, product_name, company_name, quantity, unit_price) SELECT product_code, product_name, company_name, quantity, unit_price FROM products_old_temp ''')
            cursor.execute("DROP TABLE products_old_temp")
            conn.commit() 
        except sqlite3.OperationalError: pass 
        except Exception: pass 
        
        conn.commit()
        return conn
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Could not connect to database: {e}")
        sys.exit(1)

def update_customer_due(mobile, new_due):
    try:
        conn = connect_to_db(); cursor = conn.cursor()
        cursor.execute("UPDATE customers SET previous_due = ? WHERE mobile = ?", (new_due, mobile))
        conn.commit(); conn.close()
        return True
    except Exception: return False

def get_daily_summary(report_date):
    try:
        conn = connect_to_db(); cursor = conn.cursor()
        cursor.execute("SELECT SUM(total_price) FROM sales WHERE date(sale_date) = date(?)", (report_date,))
        row = cursor.fetchone()
        total_sales = row[0] if row and row[0] is not None else 0.0
        
        cursor.execute("""
            SELECT SUM(s.quantity_sold * IFNULL(p.purchase_price, 0)) 
            FROM sales s JOIN products p ON s.product_code = p.product_code 
            WHERE date(s.sale_date) = date(?)
        """, (report_date,))
        row = cursor.fetchone()
        total_cost = row[0] if row and row[0] is not None else 0.0
        conn.close()
        return total_sales, (total_sales - total_cost)
    except Exception: return 0.0, 0.0 

def get_summary_by_date_range(start_date, end_date):
    try:
        conn = connect_to_db(); cursor = conn.cursor()
        cursor.execute("""
            SELECT SUM(s.total_price), SUM(s.quantity_sold * IFNULL(p.purchase_price, 0)) 
            FROM sales s LEFT JOIN products p ON s.product_code = p.product_code 
            WHERE date(s.sale_date) BETWEEN date(?) AND date(?)
        """, (start_date, end_date))
        row = cursor.fetchone()
        total_sales = row[0] if row and row[0] is not None else 0.0
        total_cost = row[1] if row and row[1] is not None else 0.0
        conn.close()
        return total_sales, (total_sales - total_cost)
    except Exception: return 0.0, 0.0 
    
def get_company_summary(start_date, end_date):
    summary = {}
    try:
        conn = connect_to_db(); cursor = conn.cursor()
        cursor.execute("""
            SELECT p.company_name, SUM(s.total_price) as total_sales, SUM(s.quantity_sold * IFNULL(p.purchase_price, 0)) as total_cost
            FROM sales s JOIN products p ON s.product_code = p.product_code
            WHERE date(s.sale_date) BETWEEN date(?) AND date(?)
            GROUP BY p.company_name ORDER BY p.company_name
        """, (start_date, end_date))
        results = cursor.fetchall(); conn.close()
        for row in results:
            company = row[0] if row[0] else "Unknown"
            sales = row[1] if row[1] else 0.0
            cost = row[2] if row[2] else 0.0
            summary[company] = {'sales': sales, 'cost': cost, 'profit': (sales - cost)}
        return summary
    except Exception: return {} 

def get_distinct_product_names(): conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("SELECT DISTINCT product_name FROM products WHERE product_name IS NOT NULL AND product_name != '' ORDER BY product_name"); names = [item[0] for item in cursor.fetchall()]; conn.close(); return names
def get_distinct_company_names(): conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("SELECT DISTINCT company_name FROM products WHERE company_name IS NOT NULL AND company_name != '' ORDER BY company_name"); names = [item[0] for item in cursor.fetchall()]; conn.close(); return names
def get_distinct_customer_mobiles(): conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("SELECT DISTINCT mobile FROM customers WHERE mobile IS NOT NULL AND mobile != '' ORDER BY mobile"); mobiles = [item[0] for item in cursor.fetchall()]; conn.close(); return mobiles
def generate_product_code(name): prefix = ''.join(filter(str.isalnum, name))[:4].upper(); timestamp = str(int(time.time() * 100))[-6:]; return f"{prefix}_{timestamp}"
def add_product_to_db(name, company, quantity, price, purchase_price, expiry_date):
    code = generate_product_code(name)
    try: conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)",(code, name, company, quantity, price, purchase_price, expiry_date)); conn.commit(); conn.close(); return (True, f"'{name}' is added to the inventory.")
    except sqlite3.IntegrityError: time.sleep(0.02); return add_product_to_db(name, company, quantity, price, purchase_price, expiry_date)
    except Exception: return (False, "Database error occurred.")
def get_all_products(): conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("SELECT * FROM products ORDER BY product_name"); products = cursor.fetchall(); conn.close(); return products
def update_product_in_db(code, name, company, quantity, price, purchase_price, expiry_date):
    try: conn = connect_to_db(); cursor = conn.cursor(); cursor.execute('UPDATE products SET product_name=?, company_name=?, quantity=?, unit_price=?, purchase_price=?, expiry_date=? WHERE product_code=?', (name, company, quantity, price, purchase_price, expiry_date, code)); conn.commit(); conn.close(); return True
    except Exception: return False
def delete_product_from_db(code):
    try: conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("DELETE FROM products WHERE product_code=?", (code,)); conn.commit(); conn.close(); return True
    except Exception: return False
def search_products(query): conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("SELECT product_code, product_name, quantity, unit_price FROM products WHERE quantity > 0 AND (product_name LIKE ? OR product_code LIKE ?)", (f'%{query}%', f'%{query}%')); results = cursor.fetchall(); conn.close(); return results
def update_stock_after_sale(code, qty): conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("UPDATE products SET quantity = quantity - ? WHERE product_code = ?", (qty, code)); conn.commit(); conn.close()
def log_sale_in_db(inv_id, cart, mobile, doc):
    conn = connect_to_db(); cursor = conn.cursor(); d = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for i in cart:
        disc = i.get('discount_percent', 0.0); disc_amt = (i['quantity'] * i['price']) * (disc / 100); tot = (i['quantity'] * i['price']) - disc_amt
        cursor.execute('INSERT INTO sales (invoice_id, product_code, product_name, quantity_sold, price_per_unit, total_price, sale_date) VALUES (?, ?, ?, ?, ?, ?, ?)', (inv_id, i['code'], i['name'], i['quantity'], i['price'], tot, d))
    conn.commit(); conn.close()

def get_sales_by_date_range(start, end): 
    conn = connect_to_db(); cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            s.invoice_id, s.sale_date, s.product_name, s.quantity_sold, 
            IFNULL(p.purchase_price, 0.0) as buy_price, s.price_per_unit as sell_price, 
            (s.total_price - (IFNULL(p.purchase_price, 0.0) * s.quantity_sold)) as profit
        FROM sales s 
        LEFT JOIN products p ON s.product_code = p.product_code 
        WHERE date(s.sale_date) BETWEEN date(?) AND date(?) 
        ORDER BY s.sale_date DESC
    """, (start, end))
    res = cursor.fetchall(); conn.close()
    return res

def add_or_update_customer(mobile, name, address, due):
    try: conn = connect_to_db(); cursor = conn.cursor(); cursor.execute('INSERT OR REPLACE INTO customers VALUES (?, ?, ?, ?)', (mobile, name, address, due)); conn.commit(); conn.close(); return True, f"Customer '{name}' saved!"
    except Exception: return False, "Error saving customer."
def get_all_customers(): conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("SELECT * FROM customers ORDER BY customer_name"); customers = cursor.fetchall(); conn.close(); return customers
def delete_customer(mobile):
    try: conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("DELETE FROM customers WHERE mobile=?", (mobile,)); conn.commit(); conn.close(); return True
    except Exception: return False
def get_customer_by_mobile(mobile):
    try: conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("SELECT customer_name, previous_due FROM customers WHERE mobile=?", (mobile,)); res = cursor.fetchone(); conn.close(); return res
    except Exception: return None

# ===================================================================================
# PDF Generation 
# ===================================================================================
def generate_invoice_pdf(inv_id, cart, bill_tot, cust, doc, paid, due, path, less=0.0, adj=0.0):
    page_width = 72; margin = 4; line_height = 3.5; font_size_normal = 8; font_size_large = 10; font_size_small = 7
    pdf = FPDF(orientation='P', unit='mm', format=(page_width + 2*margin, 297)) 
    pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=5); pdf.set_margins(margin, margin, margin); pdf.set_font("Courier", "", font_size_normal) 

    pdf.ln(2) 
    pdf.set_font("Courier", "B", font_size_large); pdf.cell(0, line_height, "Jonoseba Pharmacy", ln=True, align="C"); 
    pdf.set_font("Courier", "", font_size_small); pdf.cell(0, line_height, "Sarojgonj Bazar, Chuadanga", ln=True, align="C"); 
    pdf.cell(0, line_height, "Cell: 01855810820", ln=True, align="C"); 
    
    separator = "-" * 45; pdf.set_font("Courier", "", font_size_normal); pdf.cell(0, line_height, separator, ln=True, align="C");
    pdf.set_font("Courier", "", font_size_small); current_time = datetime.now(); 
    pdf.cell(page_width / 2, line_height, f"Date: {current_time.strftime('%d/%m/%Y')}", align="L"); pdf.cell(page_width / 2, line_height, f"Time: {current_time.strftime('%I:%M %p')}", align="R", ln=True); 
    pdf.cell(0, line_height, f"Bill No: {inv_id}", align="L", ln=True)

    cust_name = cust.get('name', 'Walk-in') if cust else 'Walk-in'
    if len(cust_name) > 15: cust_name = cust_name[:14] + '.'
    pdf.cell(page_width / 2, line_height, f"Customer: {cust_name}", align="L")
    if doc: pdf.cell(page_width / 2, line_height, f"Ref: {doc}", align="R", ln=True) 
    else: pdf.ln() 
    pdf.cell(0, line_height, separator, ln=True, align="C");

    pdf.set_font("Courier", "", font_size_small); col_widths = {'name': 38, 'qty': 7, 'price': 12, 'total': 15}; pdf.cell(col_widths['name'], line_height, "Item", border=0, align="L"); pdf.cell(col_widths['qty'], line_height, "Qty", border=0, align="C"); pdf.cell(col_widths['price'], line_height, "Price", border=0, align="R"); pdf.cell(col_widths['total'], line_height, "Total", border=0, align="R"); pdf.ln(); pdf.cell(0, line_height-1, separator, ln=True, align="C"); 

    total_discount_amount = 0.0; calculated_bill_total = 0.0 
    for item in cart:
        discount_percent = item.get('discount_percent', 0.0); item_total_before_discount = item['quantity'] * item['price']; item_discount_amount = item_total_before_discount * (discount_percent / 100); item_subtotal = item_total_before_discount - item_discount_amount; total_discount_amount += item_discount_amount; calculated_bill_total += item_subtotal
        expiry = item.get('expiry_date', None); display_name = item['name']; 
        if expiry: display_name += f" (Exp:{expiry})" 
        start_y = pdf.get_y(); pdf.multi_cell(col_widths['name'], line_height - 0.5, display_name, border=0, align="L", max_line_height=pdf.font_size); end_y = pdf.get_y(); pdf.set_xy(pdf.l_margin + col_widths['name'], start_y); pdf.cell(col_widths['qty'], line_height - 0.5, str(item['quantity']), border=0, align="C"); pdf.cell(col_widths['price'], line_height - 0.5, f"{item['price']:.2f}", border=0, align="R"); pdf.cell(col_widths['total'], line_height - 0.5, f"{item_subtotal:.2f}", border=0, align="R"); pdf.set_y(end_y if end_y > start_y + (line_height - 0.5) else start_y + (line_height - 0.5)); pdf.ln(0.5) 

    pdf.cell(0, line_height-1, separator, ln=True, align="C")
    label_width = page_width - col_widths['total'] - margin; value_width = col_widths['total'] + margin; 
    pdf.cell(label_width, line_height, "Sub Total:", align="R"); pdf.cell(value_width, line_height, f"Tk. {calculated_bill_total + total_discount_amount:.2f}", align="R", ln=True); 
    pdf.cell(label_width, line_height, "Discount:", align="R"); pdf.cell(value_width, line_height, f"Tk. {total_discount_amount:.2f}", align="R", ln=True); 
    pdf.cell(0, line_height-1, separator, ln=True, align="C"); 
    
    pdf.set_font("Courier", "B", font_size_normal); pdf.cell(label_width, line_height, "Gross Total:", align="R"); pdf.cell(value_width, line_height, f"Tk. {calculated_bill_total:.2f}", align="R", ln=True); 
    pdf.set_font("Courier", "", font_size_small); 
    previous_due = cust.get('due', 0.0) if cust else 0.0
    net_payable = calculated_bill_total + previous_due - less - adj
    
    if previous_due != 0: pdf.cell(label_width, line_height, "Previous Due:", align="R"); pdf.cell(value_width, line_height, f"Tk. {previous_due:.2f}", align="R", ln=True); 
    if less > 0: pdf.cell(label_width, line_height, "Less/Discount:", align="R"); pdf.cell(value_width, line_height, f"Tk. {less:.2f}", align="R", ln=True)
    if adj > 0: pdf.cell(label_width, line_height, "Adjust:", align="R"); pdf.cell(value_width, line_height, f"Tk. {adj:.2f}", align="R", ln=True)
        
    pdf.set_font("Courier", "B", font_size_normal); pdf.cell(label_width, line_height, "Net Payable:", align="R"); pdf.cell(value_width, line_height, f"Tk. {net_payable:.2f}", align="R", ln=True); 
    pdf.set_font("Courier", "", font_size_small)
    
    if paid != net_payable or previous_due != 0 or less > 0 or adj > 0: 
        pdf.cell(label_width, line_height, "Paid Amount:", align="R"); pdf.cell(value_width, line_height, f"Tk. {paid:.2f}", align="R", ln=True); 
        pdf.set_font("Courier", "B", font_size_normal); pdf.cell(label_width, line_height, "Amount Due:", align="R"); pdf.cell(value_width, line_height, f"Tk. {due:.2f}", align="R", ln=True) 
        
    pdf.cell(0, line_height, separator, ln=True, align="C")

    try:
        footer_image_path = resource_path("footer_rules.png") 
        if os.path.exists(footer_image_path): pdf.image(footer_image_path, x=margin, w=page_width, type='PNG'); pdf.ln(2) 
    except Exception: pdf.set_font("Courier", "I", font_size_small); pdf.cell(0, line_height, "[Return Policy - Image Missing]", ln=True, align="C")

    pdf.set_font("Courier", "", font_size_normal); pdf.cell(0, line_height, separator, ln=True, align="C") 
    pdf.ln(1)
    pdf.set_font("Courier", "I", 6)
    pdf.cell(0, 3, "Software Developed by: Tanvir Ahammed", ln=True, align="C")
    pdf.cell(0, 3, "Contact Email: tanvirarussel@gmail.com", ln=True, align="C")
    
    try: pdf.output(path) 
    except Exception as e_save: messagebox.showerror("Save Error", f"Error saving PDF: {e_save}")

# ===================================================================================
# কাস্টম ডায়ালগ এবং উইন্ডো
# ===================================================================================
class CustomerHistoryWindow(customtkinter.CTkToplevel):
    def __init__(self, master, mobile, name):
        super().__init__(master); self.title("Purchase History"); self.geometry("800x500"); self.lift(); self.focus_set()
        customtkinter.CTkLabel(self, text=f"Purchase History: {name} ({mobile})", font=("Roboto", 18, "bold")).pack(pady=15)
        
        tf = customtkinter.CTkFrame(self, fg_color="transparent"); tf.pack(expand=True, fill="both", padx=20, pady=(0, 20))
        self.tree = ttk.Treeview(tf, columns=('date', 'invoice', 'product', 'qty', 'price', 'total'), show='headings')
        for c, t in [('date', 'Date & Time'), ('invoice', 'Invoice No.'), ('product', 'Product Name'), ('qty', 'Qty'), ('price', 'Unit Price'), ('total', 'Total Price')]: self.tree.heading(c, text=t)
        for c, w in [('date', 140), ('invoice', 160), ('product', 200), ('qty', 60), ('price', 80), ('total', 90)]: self.tree.column(c, width=w, anchor='center')
        
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview); self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); self.tree.pack(side="left", fill="both", expand=True)
        
        self.populate(mobile)
        customtkinter.CTkButton(self, text="Close", command=self.destroy, width=100).pack(pady=(0, 15))

    def populate(self, mobile):
        try:
            conn = connect_to_db(); cursor = conn.cursor()
            cursor.execute("SELECT sale_date, invoice_id, product_name, quantity_sold, price_per_unit, total_price FROM sales WHERE invoice_id LIKE ? ORDER BY sale_date DESC", (f"{mobile}_%",))
            res = cursor.fetchall(); conn.close()
            for c, r in enumerate(res): self.tree.insert('', 'end', values=(r[0], r[1], r[2], r[3], f"{r[4]:.2f}", f"{r[5]:.2f}"), tags=('evenrow' if c % 2 == 0 else 'oddrow',))
        except Exception as e: messagebox.showerror("Error", f"Could not load history: {e}")

class SaleItemDetailsDialog(customtkinter.CTkToplevel):
    def __init__(self, parent, title, product_name, current_stock, default_price, initial_qty="", initial_custom_price="", initial_expiry="", initial_discount=""):
        super().__init__(parent); self.transient(parent); self.title(title); self.geometry("380x300") 
        self.lift(); self.focus_set(); self.grab_set(); self.result = None 

        main_frame = customtkinter.CTkFrame(self); main_frame.pack(expand=True, fill="both", padx=15, pady=15)
        info_label = customtkinter.CTkLabel(main_frame, text=f"{product_name}\nStock Available: {current_stock} | Default Price: {default_price:.2f}", justify="left"); info_label.pack(pady=(0, 10), anchor="w")

        self.entry_quantity = self._create_entry(main_frame, "Quantity*", 0)
        if initial_qty: self.entry_quantity.insert(0, str(initial_qty))
        self.entry_custom_price = self._create_entry(main_frame, f"Custom Sell Price (Optional)", 1)
        if initial_custom_price: self.entry_custom_price.insert(0, str(initial_custom_price))
        self.entry_expiry = self._create_entry(main_frame, "Expiry (DD/MM/YY, Optional)", 2)
        if initial_expiry: self.entry_expiry.insert(0, str(initial_expiry))
        self.entry_discount = self._create_entry(main_frame, "Discount % (Optional)", 3)
        if initial_discount: self.entry_discount.insert(0, str(initial_discount))

        button_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent"); button_frame.pack(pady=(15, 0), fill="x", side="bottom") 
        ok_button = customtkinter.CTkButton(button_frame, text="OK", command=self._ok_event, width=80); ok_button.pack(side="right", padx=5)
        cancel_button = customtkinter.CTkButton(button_frame, text="Cancel", command=self._cancel_event, width=80, fg_color="gray"); cancel_button.pack(side="right", padx=5)

        self.entry_quantity.bind("<Return>", lambda e: self.entry_custom_price.focus_set()); self.entry_custom_price.bind("<Return>", lambda e: self.entry_expiry.focus_set()); self.entry_expiry.bind("<Return>", lambda e: self.entry_discount.focus_set()); self.entry_discount.bind("<Return>", lambda e: self._ok_event()) 
        self.after(100, self._force_focus); self.protocol("WM_DELETE_WINDOW", self._cancel_event); self.wait_window() 

    def _force_focus(self):
        self.entry_quantity.focus_force()
        self.entry_quantity.select_range(0, 'end')

    def _create_entry(self, parent, placeholder, row):
        frame = customtkinter.CTkFrame(parent, fg_color="transparent"); frame.pack(fill="x", pady=4) 
        label = customtkinter.CTkLabel(frame, text=placeholder.split("*")[0].split("(")[0].strip() + ":", width=130, anchor="w"); label.pack(side="left", padx=(0,5))
        entry = customtkinter.CTkEntry(frame, placeholder_text=placeholder); entry.pack(side="left", fill="x", expand=True)
        return entry

    def _ok_event(self, event=None): self.result = (self.entry_quantity.get(), self.entry_expiry.get(), self.entry_discount.get(), self.entry_custom_price.get()); self.grab_release(); self.destroy()
    def _cancel_event(self, event=None): self.result = None; self.grab_release(); self.destroy()
    def get_input(self): return self.result

class AutocompleteEntry(customtkinter.CTkFrame):
    def __init__(self, master, completions, on_select_callback=None, **kwargs): 
        super().__init__(master); self.configure(fg_color="transparent")
        placeholder = kwargs.pop("placeholder_text", ""); entry_width = kwargs.pop("width", 150)
        self.completions = completions; self.listbox = None; self._after_id = None; self.on_select_callback = on_select_callback 
        self.entry = customtkinter.CTkEntry(self, placeholder_text=placeholder, width=entry_width, **kwargs); self.entry.pack(fill="both", expand=True)
        self.entry.bind('<KeyRelease>', self.on_key_release); self.entry.bind('<FocusOut>', self.on_focus_out); self.entry.bind('<Down>', self.on_arrow_down); self.entry.bind('<Up>', self.on_arrow_up); self.entry.bind('<Escape>', self.hide_listbox)

    def get(self): return self.entry.get()
    def delete(self, first, last): self.entry.delete(first, last)
    def focus_set(self): self.entry.focus_set() 
    def select_range(self, start, end): self.entry.select_range(start, end)
    def insert(self, index, text): self.entry.insert(index, text) 
    def bind(self, sequence=None, command=None, add=None): self.entry.bind(sequence, command, add)

    def on_key_release(self, event):
        if event.keysym in ('Up', 'Down', 'Return', 'Escape', 'Tab', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R'): return
        query = self.entry.get(); self.hide_listbox() 
        if query:
            suggestions = [w for w in self.completions if query.lower() in str(w).lower()]
            if suggestions:
                mode = customtkinter.get_appearance_mode()
                bg_col = '#2b2b2b' if mode == 'Dark' else '#ffffff'
                fg_col = 'white' if mode == 'Dark' else 'black'
                sel_col = '#22559b' if mode == 'Dark' else '#a0c4ff'
                self.listbox = Listbox(self.winfo_toplevel(), width=int(self.entry.winfo_width() / 7), height=min(4, len(suggestions)), relief='flat', background=bg_col, fg=fg_col, selectbackground=sel_col, highlightthickness=1, font=("Helvetica", 11))
                self.update_idletasks(); x = self.entry.winfo_rootx(); y = self.entry.winfo_rooty() + self.entry.winfo_height() + 1; self.listbox.place(x=x, y=y)
                for item in suggestions: self.listbox.insert('end', item)
                self.listbox.bind('<Double-Button-1>', self._select_item_from_listbox); self.listbox.bind('<Return>', self._select_item_from_listbox); self.listbox.bind('<Escape>', self.hide_listbox); self.listbox.bind('<FocusOut>', self.on_focus_out)                     

    def _select_item_from_listbox(self, event=None):
        if self.listbox and self.listbox.curselection():
            selection = self.listbox.get(self.listbox.curselection())
            self.entry.delete(0, 'end'); self.entry.insert(0, selection); self.hide_listbox(); self.entry.icursor('end')
            if self.on_select_callback: self.on_select_callback() 
            return "break" 

    def on_arrow_down(self, event=None):
        if self.listbox and self.listbox.size() > 0:
            if not self.listbox.curselection(): self.listbox.focus_set(); self.listbox.selection_set(0); self.listbox.activate(0)
            else:
                current_index = self.listbox.curselection()[0]
                if current_index < self.listbox.size() - 1: self.listbox.selection_clear(current_index); new_index = current_index + 1; self.listbox.selection_set(new_index); self.listbox.activate(new_index)
            return "break" 
    def on_arrow_up(self, event=None):
        if self.listbox and self.listbox.curselection():
            current_index = self.listbox.curselection()[0]
            if current_index > 0: self.listbox.selection_clear(current_index); new_index = current_index - 1; self.listbox.selection_set(new_index); self.listbox.activate(new_index)
            return "break" 
    def on_focus_out(self, event):
        if self._after_id: self.after_cancel(self._after_id)
        self._after_id = self.after(200, self.hide_listbox_if_not_focused)
    def hide_listbox_if_not_focused(self):
        self._after_id = None; focused_widget = self.focus_get()
        if self.listbox and self.listbox.winfo_exists() and focused_widget != self.listbox and focused_widget != self.entry: self.hide_listbox()
    def hide_listbox(self, event=None):
        if self._after_id: self.after_cancel(self._after_id); self._after_id = None
        if self.listbox: 
             try: self.listbox.destroy()
             except Exception: pass
             self.listbox = None

class EditProductWindow(customtkinter.CTkToplevel):
    def __init__(self, master, product_data, app_instance):
        super().__init__(master); self.title("Edit Product Information"); self.geometry("450x550"); self.app_instance = app_instance; self.product_code = product_data[0] 
        customtkinter.CTkLabel(self, text=f"Product Code: {self.product_code}", font=("Roboto", 14, "bold")).pack(pady=(15, 5))

        self.entry_name = customtkinter.CTkEntry(self, placeholder_text="Product Name", width=300); self.entry_name.insert(0, product_data[1]); self.entry_name.pack(pady=10, padx=20)
        self.entry_company = customtkinter.CTkEntry(self, placeholder_text="Company Name", width=300); self.entry_company.insert(0, product_data[2]); self.entry_company.pack(pady=10, padx=20)
        self.entry_purchase_price = customtkinter.CTkEntry(self, placeholder_text="Purchase Price", width=300); self.entry_purchase_price.insert(0, product_data[5] if product_data[5] else ""); self.entry_purchase_price.pack(pady=10, padx=20)
        self.entry_expiry_date = customtkinter.CTkEntry(self, placeholder_text="Expiry Date (DD/MM/YY)", width=300); self.entry_expiry_date.insert(0, product_data[6] if product_data[6] else ""); self.entry_expiry_date.pack(pady=10, padx=20)
        self.entry_price = customtkinter.CTkEntry(self, placeholder_text="Unit Price", width=300); self.entry_price.insert(0, product_data[4]); self.entry_price.pack(pady=10, padx=20)

        quantity_frame = customtkinter.CTkFrame(self, fg_color="transparent"); quantity_frame.pack(pady=10, padx=20, fill="x")
        self.entry_quantity = customtkinter.CTkEntry(quantity_frame, placeholder_text="Current Quantity"); self.entry_quantity.insert(0, product_data[3]); self.entry_quantity.pack(side="left", expand=True, fill="x")
        self.entry_add_stock = customtkinter.CTkEntry(quantity_frame, placeholder_text="Add New Stock", width=120); self.entry_add_stock.pack(side="left", padx=(10, 5))
        self.add_stock_button = customtkinter.CTkButton(quantity_frame, text="+ Add", width=50, command=self.add_stock_to_quantity); self.add_stock_button.pack(side="left")

        self.save_button = customtkinter.CTkButton(self, text="Save Changes", command=self.save_changes, height=40); self.save_button.pack(pady=20, padx=20, fill="x")

        self.edit_form_widgets = [self.entry_name, self.entry_company, self.entry_purchase_price, self.entry_expiry_date, self.entry_price, self.entry_quantity, self.entry_add_stock, self.add_stock_button, self.save_button]
        for i, widget in enumerate(self.edit_form_widgets):
            next_w = self.edit_form_widgets[(i + 1) % len(self.edit_form_widgets)]; prev_w = self.edit_form_widgets[(i - 1 + len(self.edit_form_widgets)) % len(self.edit_form_widgets)]
            widget.bind("<Return>", lambda e, t=next_w: self._fcs(t)); widget.bind("<Down>", lambda e, t=next_w: self._fcs(t)); widget.bind("<Up>", lambda e, t=prev_w: self._fcs(t))
        
        self.add_stock_button.bind("<Return>", lambda e: self.add_stock_to_quantity()); self.save_button.bind("<Return>", lambda e: self.save_changes())
        self.entry_name.focus_set(); self.entry_name.select_range(0, 'end')

    def _fcs(self, w):
        w.focus_set()
        if isinstance(w, customtkinter.CTkEntry): w.select_range(0, 'end')
        return "break" 

    def add_stock_to_quantity(self, event=None): 
        try:
            curr = self.entry_quantity.get(); add = self.entry_add_stock.get()
            if not curr or not add: messagebox.showwarning("Invalid", "Enter values."); return
            if int(add) > 0: self.entry_quantity.delete(0, 'end'); self.entry_quantity.insert(0, int(curr) + int(add)); self.entry_add_stock.delete(0, 'end'); self.save_button.focus_set()
            else: messagebox.showwarning("Invalid", "Stock to add must be positive.")
        except ValueError: messagebox.showwarning("Invalid", "Enter valid numbers.")

    def save_changes(self, event=None): 
        try:
            pp = self.entry_purchase_price.get()
            if update_product_in_db(self.product_code, self.entry_name.get(), self.entry_company.get(), int(self.entry_quantity.get()), float(self.entry_price.get()), float(pp) if pp else None, self.entry_expiry_date.get()):
                 self.app_instance.refresh_add_product_suggestions(); self.destroy()
            else: messagebox.showerror("Error", "Failed to update product.")
        except ValueError: messagebox.showerror("Invalid Input", "Ensure Qty & Prices are numbers.")


# ===================================================================================
# মূল অ্যাপ্লিকেশন ক্লাস
# ===================================================================================
class PharmacyApp(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("Jonoseba Pharmacy")
        self.geometry("1100x750")
        
        try:
            icon_file = resource_path("app_icon.ico")
            if os.path.exists(icon_file):
                self.iconbitmap(icon_file)
        except Exception: pass
        
        customtkinter.set_default_color_theme("blue")
        customtkinter.set_appearance_mode("Light")
        
        self.current_customer = None 
        self.cart = []
        self.is_stock_value_visible = False
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.header_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=20, pady=(10, 0))
        self.title_lbl = customtkinter.CTkLabel(self.header_frame, text="Jonoseba Pharmacy POS", font=("Roboto", 24, "bold"), text_color="#3484F0")
        self.title_lbl.pack(side="left")
        
        self.theme_switch_var = tkinter.IntVar(value=0) 
        self.theme_switch = customtkinter.CTkSwitch(self.header_frame, text="Dark Mode", variable=self.theme_switch_var, command=self.toggle_theme)
        self.theme_switch.pack(side="right", padx=10)
        
        self.backup_btn = customtkinter.CTkButton(self.header_frame, text="💾 Backup Data", fg_color="#229954", hover_color="#1d8348", command=self.backup_database)
        self.backup_btn.pack(side="right", padx=10)
        
        self.tab_view = customtkinter.CTkTabview(self, width=1050, height=650)
        self.tab_view.pack(padx=20, pady=10, fill="both", expand=True)
        
        self.stock_tab = self.tab_view.add("Stock Management")
        self.low_stock_tab = self.tab_view.add("Low Stock") 
        self.sales_tab = self.tab_view.add("Sales Point")
        self.reports_tab = self.tab_view.add("All Reports")
        self.customers_tab = self.tab_view.add("Customers Information")
        
        self.create_stock_management_tab()
        self.create_low_stock_tab() 
        self.create_sales_point_tab()
        self.create_reports_tab()
        self.create_customers_tab()
        
        self.update_treeview_style() 
        self.populate_stock_list()
        self.refresh_low_stock_display()
        self.populate_customer_list()

    def backup_database(self):
        try:
            backup_folder = os.path.join(get_base_path(), "Database_Backups")
            if not os.path.exists(backup_folder): os.makedirs(backup_folder)
            date_str = datetime.now().strftime("%Y-%m-%d_%I-%M-%p")
            backup_path = os.path.join(backup_folder, f"products_backup_{date_str}.db")
            db_original_path = os.path.join(get_base_path(), "products.db")
            shutil.copy2(db_original_path, backup_path)
            messagebox.showinfo("Backup Successful", f"Database successfully backed up!\n\nLocation: {backup_path}")
        except Exception as e: messagebox.showerror("Backup Failed", f"Could not backup the database.\nError: {e}")

    def toggle_theme(self):
        if self.theme_switch_var.get() == 1: customtkinter.set_appearance_mode("Dark")
        else: customtkinter.set_appearance_mode("Light")
        self.update_treeview_style(); self.update_tk_listbox_styles()

    def update_tk_listbox_styles(self):
        mode = customtkinter.get_appearance_mode()
        bg_col = '#2b2b2b' if mode == 'Dark' else '#ffffff'
        fg_col = 'white' if mode == 'Dark' else 'black'
        sel_col = '#22559b' if mode == 'Dark' else '#a0c4ff'
        if hasattr(self, 'search_results_listbox'): self.search_results_listbox.configure(bg=bg_col, fg=fg_col, selectbackground=sel_col)
        if hasattr(self, 'cart_listbox'): self.cart_listbox.configure(bg=bg_col, fg=fg_col, selectbackground=sel_col)

    def update_treeview_style(self):
        style = ttk.Style(); style.theme_use("default")
        mode = customtkinter.get_appearance_mode()
        
        if mode == "Dark":
            bg_col = "#2b2b2b"; fg_col = "white"; head_bg = "#565b5e"; sel_bg = "#22559b"
            even_bg = "#323232"; odd_bg = "#2b2b2b"
        else:
            bg_col = "#ffffff"; fg_col = "black"; head_bg = "#e9ecef"; sel_bg = "#a0c4ff"
            even_bg = "#f0f4fa"; odd_bg = "#ffffff"

        style.configure("Treeview", background=bg_col, foreground=fg_col, rowheight=28, fieldbackground=bg_col, borderwidth=0)
        style.map('Treeview', background=[('selected', sel_bg)]) 
        
        style.configure("Treeview.Heading", background=head_bg, foreground=fg_col, relief="groove", borderwidth=1, font=('Helvetica', 10, 'bold'))
        style.map("Treeview.Heading", background=[('active', sel_bg)])

        for tree in [getattr(self, 'stock_tree', None), getattr(self, 'low_stock_tree', None), getattr(self, 'customer_tree', None), getattr(self, 'report_tree', None)]:
            if tree:
                tree.tag_configure('evenrow', background=even_bg, foreground=fg_col)
                tree.tag_configure('oddrow', background=odd_bg, foreground=fg_col)

    def on_closing(self): self.clear_cart(restore_stock=True); self.destroy()

    def create_low_stock_tab(self):
        frame = customtkinter.CTkFrame(master=self.low_stock_tab)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        top_bar = customtkinter.CTkFrame(master=frame, fg_color="transparent")
        top_bar.pack(fill="x", pady=(0, 10))
        
        title_frame = customtkinter.CTkFrame(master=top_bar, fg_color="transparent")
        title_frame.pack(side="left")
        customtkinter.CTkLabel(master=title_frame, text="🚨", font=("Roboto", 20), text_color="red").pack(side="left")
        customtkinter.CTkLabel(master=title_frame, text=" All Products", font=("Roboto", 20, "bold")).pack(side="left", padx=(5,0))
        
        self.low_stock_search_entry = customtkinter.CTkEntry(master=top_bar, placeholder_text="Search Name or Company...", width=200)
        self.low_stock_search_entry.pack(side="left", padx=30)
        self.low_stock_search_entry.bind("<KeyRelease>", self.refresh_low_stock_display)

        self.low_stock_sort_var = tkinter.StringVar(value="Default")
        self.low_stock_sort_combo = customtkinter.CTkComboBox(master=top_bar, values=["Default", "Low to High", "High to Low"], variable=self.low_stock_sort_var, command=self.refresh_low_stock_display, width=130)
        self.low_stock_sort_combo.pack(side="left", padx=10)

        customtkinter.CTkButton(master=top_bar, text="Refresh List", command=self.refresh_low_stock_display).pack(side="right")

        table_container = customtkinter.CTkFrame(master=frame, border_width=1, border_color="#d3d3d3", width=800)
        table_container.pack(expand=True, fill="y", pady=10) 

        columns = ('name', 'company', 'qty')
        self.low_stock_tree = ttk.Treeview(master=table_container, columns=columns, show='headings', selectmode='browse')
        self.low_stock_tree.heading('name', text='Product Name')
        self.low_stock_tree.heading('company', text='Company')
        self.low_stock_tree.heading('qty', text='Remaining Quantity')
        
        self.low_stock_tree.column('name', width=350, anchor='center')
        self.low_stock_tree.column('company', width=250, anchor='center')
        self.low_stock_tree.column('qty', width=180, anchor='center')

        scrollbar = ttk.Scrollbar(master=table_container, orient="vertical", command=self.low_stock_tree.yview)
        self.low_stock_tree.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        self.low_stock_tree.pack(side="left", fill="y", expand=True, padx=(1, 0), pady=1)
        
        self.low_stock_tree.bind("<Double-1>", self.edit_low_stock_product)
        self.low_stock_tree.bind("<Return>", self.edit_low_stock_product)

    def refresh_low_stock_display(self, event=None):
        if not hasattr(self, 'low_stock_tree'): return
        query = self.low_stock_search_entry.get().lower()
        for row in self.low_stock_tree.get_children(): self.low_stock_tree.delete(row)
        
        products = get_all_products()
        filtered_products = []
        
        for p in products:
            company = str(p[2]).lower() if p[2] else ""
            name = str(p[1]).lower()
            if query in company or query in name:
                filtered_products.append(p)
                
        sort_order = self.low_stock_sort_var.get()
        if sort_order == "Low to High":
            sorted_filtered = sorted(filtered_products, key=lambda x: int(x[3]))
        elif sort_order == "High to Low":
            sorted_filtered = sorted(filtered_products, key=lambda x: int(x[3]), reverse=True)
        else: 
            def default_sort(p):
                qty = int(p[3])
                if qty == 0: return (0, qty)
                elif qty < 10: return (1, qty)
                else: return (2, qty)
            sorted_filtered = sorted(filtered_products, key=default_sort)

        count = 0
        for product in sorted_filtered:
            qty = int(product[3])
            tag = 'evenrow' if count % 2 == 0 else 'oddrow'
            self.low_stock_tree.insert('', 'end', iid=product[0], values=(product[1], product[2], qty), tags=(tag,))
            count += 1

    def edit_low_stock_product(self, event=None):
        selected_item_iid = self.low_stock_tree.focus()
        if not selected_item_iid: return
        conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("SELECT * FROM products WHERE product_code=?", (selected_item_iid,)); product_data = cursor.fetchone(); conn.close()
        if product_data: EditProductWindow(self, product_data, self).grab_set()

    def create_stock_management_tab(self):
        global status_label
        stock_main_frame = customtkinter.CTkFrame(master=self.stock_tab); stock_main_frame.pack(fill="both", expand=True)
        input_frame = customtkinter.CTkFrame(master=stock_main_frame); input_frame.pack(side="left", fill="y", padx=10, pady=10)
        main_label = customtkinter.CTkLabel(master=input_frame, text="Add Product", font=("Roboto", 20)); main_label.pack(pady=12, padx=10)
        entry_box_width = 180

        product_list = get_distinct_product_names(); company_list = get_distinct_company_names()
        self.entry_name = AutocompleteEntry(master=input_frame, placeholder_text="Product Name*", completions=product_list, width=entry_box_width, on_select_callback=lambda: self.entry_company.focus_set()); self.entry_name.pack(pady=10, padx=10)
        self.entry_company = AutocompleteEntry(master=input_frame, placeholder_text="Company Name", completions=company_list, width=entry_box_width, on_select_callback=lambda: self.entry_quantity.focus_set()); self.entry_company.pack(pady=10, padx=10)
        
        self.entry_quantity = customtkinter.CTkEntry(master=input_frame, placeholder_text="Quantity*", width=entry_box_width); self.entry_quantity.pack(pady=10, padx=10)
        self.entry_price = customtkinter.CTkEntry(master=input_frame, placeholder_text="Sell Price*", width=entry_box_width); self.entry_price.pack(pady=10, padx=10)
        self.entry_purchase_price = customtkinter.CTkEntry(master=input_frame, placeholder_text="Buy Price", width=entry_box_width); self.entry_purchase_price.pack(pady=10, padx=10)
        self.entry_expiry_date = customtkinter.CTkEntry(master=input_frame, placeholder_text="Expiry Date (DD/MM/YY)", width=entry_box_width); self.entry_expiry_date.pack(pady=10, padx=10)

        button_frame = customtkinter.CTkFrame(master=input_frame, fg_color="transparent"); button_frame.pack(pady=(15, 0))
        self.add_button = customtkinter.CTkButton(master=button_frame, text="Add Product", command=self.on_add_button_click); self.add_button.pack(side="left", padx=5)
        self.clear_button = customtkinter.CTkButton(master=button_frame, text="Clear", command=self.clear_add_product_form, fg_color="gray"); self.clear_button.pack(side="left", padx=5)
        status_label = customtkinter.CTkLabel(master=input_frame, text="", font=("Roboto", 12)); status_label.pack(pady=(10, 5))

        self.form_widgets_stock = [self.entry_name, self.entry_company, self.entry_quantity, self.entry_price, self.entry_purchase_price, self.entry_expiry_date, self.add_button]
        for i, widget in enumerate(self.form_widgets_stock):
            next_w = self.form_widgets_stock[(i + 1) % len(self.form_widgets_stock)]
            bind_target = widget.entry if isinstance(widget, AutocompleteEntry) else widget
            if widget != self.add_button: bind_target.bind("<Return>", lambda e, t=next_w: t.focus_set())
            else: bind_target.bind("<Return>", lambda e: self.on_add_button_click())

        list_frame = customtkinter.CTkFrame(master=stock_main_frame); list_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        top_list_frame = customtkinter.CTkFrame(master=list_frame, fg_color="transparent"); top_list_frame.pack(fill="x", padx=10, pady=(10, 5))

        self.stock_search_entry = customtkinter.CTkEntry(master=top_list_frame, placeholder_text="Search by Name, Company...", width=250); self.stock_search_entry.pack(side="left", fill="x", expand=True) 
        self.stock_search_entry.bind("<KeyRelease>", self.search_stock_list)

        self.toggle_value_btn = customtkinter.CTkButton(master=top_list_frame, text="👁️", width=30, fg_color="transparent", hover_color="#343638", command=self.toggle_stock_value); self.toggle_value_btn.pack(side="right", padx=(5, 0))
        self.total_value_label = customtkinter.CTkLabel(master=top_list_frame, text="Buy: *** TK | MRP: *** TK", font=("Roboto", 13, "bold"), text_color="#229954"); self.total_value_label.pack(side="right")

        columns = ('name', 'company', 'qty', 'price', 'purchase_price', 'expiry_date')
        self.stock_tree = ttk.Treeview(master=list_frame, columns=columns, show='headings')
        self.stock_tree.heading('name', text='Product Name'); self.stock_tree.heading('company', text='Company'); self.stock_tree.heading('qty', text='Qty'); self.stock_tree.heading('price', text='Sell Price'); self.stock_tree.heading('purchase_price', text='Buy Price'); self.stock_tree.heading('expiry_date', text='Expiry', command=self.sort_stock_by_expiry); 
        
        self.stock_tree.column('name', width=200, anchor='center'); self.stock_tree.column('company', width=120, anchor='center'); self.stock_tree.column('qty', width=50, anchor='center'); self.stock_tree.column('price', width=70, anchor='center'); self.stock_tree.column('purchase_price', width=70, anchor='center'); self.stock_tree.column('expiry_date', width=80, anchor='center'); 
        
        self.stock_tree.pack(fill="both", expand=True, padx=10, pady=10); self.stock_search_entry.bind("<Down>", self.focus_on_stock_tree)
        self.stock_tree.bind("<Return>", self.edit_selected_product); self.stock_tree.bind("<Double-1>", self.edit_selected_product)
        
        action_frame = customtkinter.CTkFrame(master=list_frame); action_frame.pack(fill="x", padx=10, pady=5); 
        customtkinter.CTkButton(master=action_frame, text="Edit Selected", command=self.edit_selected_product).pack(side="left", padx=5); 
        customtkinter.CTkButton(master=action_frame, text="Delete Selected", fg_color="red", hover_color="#CC0000", command=self.delete_selected_product).pack(side="left", padx=5); 
        customtkinter.CTkButton(master=action_frame, text="Refresh", command=self.refresh_add_product_suggestions).pack(side="right", padx=5)
    
    def calculate_total_stock_value(self):
        try:
            conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("SELECT quantity, purchase_price, unit_price FROM products WHERE quantity > 0"); products = cursor.fetchall(); conn.close()
            total_purchase = sum((qty * (pp if pp is not None else 0.0)) for qty, pp, up in products)
            total_mrp = sum((qty * (up if up is not None else 0.0)) for qty, pp, up in products)
            return total_purchase, total_mrp
        except Exception: return 0.0, 0.0

    def toggle_stock_value(self): self.is_stock_value_visible = not self.is_stock_value_visible; self.update_stock_value_display()

    def update_stock_value_display(self):
        if not hasattr(self, 'total_value_label'): return
        if self.is_stock_value_visible:
            total_purchase, total_mrp = self.calculate_total_stock_value()
            self.total_value_label.configure(text=f"Buy: {total_purchase:,.2f} TK | MRP: {total_mrp:,.2f} TK"); self.toggle_value_btn.configure(text="🙈") 
        else: self.total_value_label.configure(text="Buy: *** TK | MRP: *** TK"); self.toggle_value_btn.configure(text="👁️") 

    def get_customer_search_suggestions(self):
        customers = get_all_customers(); suggestions = []
        for c in customers: suggestions.append(f"{c[1]} ({c[0]})")
        return suggestions

    def create_sales_point_tab(self):
        sales_frame = customtkinter.CTkFrame(master=self.sales_tab, fg_color="transparent"); sales_frame.pack(fill="both", expand=True, padx=10, pady=10)
        sales_frame.grid_columnconfigure(0, weight=1); sales_frame.grid_columnconfigure(1, weight=1); sales_frame.grid_rowconfigure(0, weight=1) 

        left_column_frame = customtkinter.CTkFrame(master=sales_frame); left_column_frame.grid(row=0, column=0, padx=(0, 5), pady=0, sticky="nsew") 
        left_column_frame.grid_rowconfigure(7, weight=1); left_column_frame.grid_columnconfigure(0, weight=1) 

        customer_info_frame = customtkinter.CTkFrame(master=left_column_frame, fg_color="transparent"); customer_info_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew"); customer_info_frame.grid_columnconfigure(1, weight=1) 
        customtkinter.CTkLabel(master=customer_info_frame, text="Customer:", width=110, anchor='w').grid(row=0, column=0, padx=(0, 5), sticky="w")
        
        self.entry_sales_cust_mobile = AutocompleteEntry(master=customer_info_frame, placeholder_text="Search Name or Mobile", completions=self.get_customer_search_suggestions(), on_select_callback=self.lookup_customer) 
        self.entry_sales_cust_mobile.grid(row=0, column=1, sticky="ew"); self.entry_sales_cust_mobile.entry.bind("<Return>", self.lookup_customer) 

        customtkinter.CTkLabel(master=left_column_frame, text="Customer Name:", anchor="w", font=("Roboto", 12)).grid(row=1, column=0, padx=10, pady=(5, 0), sticky="ew") 
        self.entry_sales_cust_name = customtkinter.CTkEntry(master=left_column_frame, placeholder_text="Walk-in Customer"); self.entry_sales_cust_name.grid(row=2, column=0, padx=10, pady=(0, 5), sticky="ew") 
        self.label_sales_cust_due = customtkinter.CTkLabel(master=left_column_frame, text="Previous Due: 0.00 TK", anchor="w", font=("Roboto", 12)); self.label_sales_cust_due.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="ew") 
        
        doctor_ref_frame = customtkinter.CTkFrame(master=left_column_frame, fg_color="transparent"); doctor_ref_frame.grid(row=4, column=0, padx=10, pady=(0, 15), sticky="ew"); doctor_ref_frame.grid_columnconfigure(1, weight=1) 
        customtkinter.CTkLabel(master=doctor_ref_frame, text="Ref (Doctor):", width=110, anchor='w').grid(row=0, column=0, padx=(0,5), sticky="w")
        self.entry_sales_doctor = customtkinter.CTkEntry(master=doctor_ref_frame, placeholder_text="Doctor's Name (Optional)"); self.entry_sales_doctor.grid(row=0, column=1, sticky="ew")
        
        customtkinter.CTkLabel(master=left_column_frame, text="Search Product", font=("Roboto", 16)).grid(row=5, column=0, padx=10, pady=(5,5), sticky="ew") 
        self.search_entry = customtkinter.CTkEntry(master=left_column_frame, placeholder_text="Search by Name or Code..."); self.search_entry.grid(row=6, column=0, padx=10, pady=(0,5), sticky="ew") 
        self.search_results_listbox = Listbox(master=left_column_frame, height=10, font=("Helvetica", 12), borderwidth=0); self.search_results_listbox.grid(row=7, column=0, padx=10, pady=(0,10), sticky="nsew") 
        
        self.search_entry.bind("<KeyRelease>", self.update_search_results); self.search_entry.bind("<Down>", self.focus_on_search_list)
        self.search_results_listbox.bind("<Double-1>", self.add_to_cart); self.search_results_listbox.bind("<Return>", self.add_to_cart); self.search_results_listbox.bind("<Escape>", self.focus_on_search_entry)
        
        cart_frame = customtkinter.CTkFrame(master=sales_frame); cart_frame.grid(row=0, column=1, padx=(5, 0), pady=0, sticky="nsew"); cart_frame.grid_columnconfigure(0, weight=1) 
        customtkinter.CTkLabel(master=cart_frame, text="Current Bill", font=("Roboto", 16)).grid(row=0, column=0, padx=10, pady=(10,0), sticky="ew")
        customtkinter.CTkLabel(master=cart_frame, text="Double-Click/Enter to Edit  |  Delete Key to Remove", font=("Roboto", 11), text_color="#A0A0A0").grid(row=1, column=0, padx=10, pady=(0,5), sticky="ew")

        self.cart_listbox = Listbox(master=cart_frame, height=14, font=("Helvetica", 11), borderwidth=0); self.cart_listbox.grid(row=2, column=0, padx=10, pady=(0,10), sticky="nsew"); cart_frame.grid_rowconfigure(2, weight=1) 
        self.cart_listbox.bind("<Double-1>", self.edit_cart_item); self.cart_listbox.bind("<Return>", self.edit_cart_item); self.cart_listbox.bind("<Delete>", self.remove_cart_item); self.cart_listbox.bind("<BackSpace>", self.remove_cart_item)

        payment_frame = customtkinter.CTkFrame(master=cart_frame); payment_frame.grid(row=3, column=0, padx=10, pady=10, sticky="sew"); payment_frame.grid_columnconfigure(1, weight=1) 
        self.label_total_items = customtkinter.CTkLabel(master=payment_frame, text="Total Items: 0", font=("Roboto", 12), anchor="w"); self.label_total_items.grid(row=0, column=0, pady=(2,0), padx=5, sticky="w")
        self.check_mark_as_due_var = tkinter.IntVar() 
        self.check_mark_as_due = customtkinter.CTkCheckBox(master=payment_frame, text="Mark as Due", variable=self.check_mark_as_due_var, command=self._update_payment_display); self.check_mark_as_due.grid(row=0, column=1, pady=(2,0), padx=5, sticky="e")
        self.bill_total_label = customtkinter.CTkLabel(master=payment_frame, text="Bill Total: 0.00 TK", font=("Roboto", 13, "bold"), anchor="w"); self.bill_total_label.grid(row=1, column=0, pady=1, padx=5, sticky="w")
        self.entry_less_amount = customtkinter.CTkEntry(master=payment_frame, placeholder_text="Less/Discount (TK)", width=120, justify="right"); self.entry_less_amount.grid(row=1, column=1, pady=1, padx=5, sticky="e"); self.entry_less_amount.bind("<KeyRelease>", self._update_payment_display)
        self.grand_total_label = customtkinter.CTkLabel(master=payment_frame, text="Gross Total: 0.00 TK", font=("Roboto", 15, "bold"), text_color="#229954", anchor="w"); self.grand_total_label.grid(row=2, column=0, pady=1, padx=5, sticky="w")
        self.entry_adjust_amount = customtkinter.CTkEntry(master=payment_frame, placeholder_text="Adjust (TK)", width=120, justify="right"); self.entry_adjust_amount.grid(row=2, column=1, pady=1, padx=5, sticky="e"); self.entry_adjust_amount.bind("<KeyRelease>", self._update_payment_display)
        self.entry_paid_amount = customtkinter.CTkEntry(master=payment_frame, placeholder_text="Paid Amount", width=120, justify="right"); self.entry_paid_amount.grid(row=3, column=1, pady=1, padx=5, sticky="e"); self.entry_paid_amount.bind("<KeyRelease>", self._update_payment_display) 
        self.print_receipt_var = tkinter.IntVar(value=1) 
        self.check_print_receipt = customtkinter.CTkCheckBox(master=payment_frame, text="Print Receipt", variable=self.print_receipt_var); self.check_print_receipt.grid(row=3, column=0, pady=1, padx=5, sticky="w") 
        self.label_current_due = customtkinter.CTkLabel(master=payment_frame, text="Current Due: 0.00 TK", font=("Roboto", 14, "bold"), text_color="red", anchor="e"); self.label_current_due.grid(row=4, column=1, pady=(2,5), padx=5, sticky="e")
        customtkinter.CTkButton(master=payment_frame, text="Finalize Sale", command=self.finalize_sale).grid(row=5, column=0, columnspan=2, pady=3, sticky="ew") 
        customtkinter.CTkButton(master=payment_frame, text="Clear Bill", fg_color="red", hover_color="#CC0000", command=lambda: self.clear_cart(restore_stock=True)).grid(row=6, column=0, columnspan=2, pady=3, sticky="ew") 
        self.sales_status_label = customtkinter.CTkLabel(master=payment_frame, text="", font=("Roboto", 12)); self.sales_status_label.grid(row=7, column=0, columnspan=2, pady=(5,2), sticky="ew")

        self.update_tk_listbox_styles() 
        
    def create_reports_tab(self):
        reports_frame = customtkinter.CTkFrame(master=self.reports_tab); reports_frame.pack(fill="both", expand=True, padx=10, pady=10); reports_frame.grid_columnconfigure(0, weight=1)
        top_frame = customtkinter.CTkFrame(master=reports_frame); top_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew"); top_frame.grid_columnconfigure(0, weight=0); top_frame.grid_columnconfigure(1, weight=1); top_frame.grid_columnconfigure(2, weight=0); top_frame.grid_columnconfigure(3, weight=0); top_frame.grid_columnconfigure(4, weight=0); top_frame.grid_columnconfigure(5, weight=0); top_frame.grid_columnconfigure(6, weight=1); top_frame.grid_columnconfigure(7, weight=2) 
        customtkinter.CTkLabel(master=top_frame, text="Start Date:").grid(row=0, column=0, padx=(5,0), pady=5, sticky="w"); self.start_date_entry = customtkinter.CTkEntry(master=top_frame, placeholder_text="YYYY-MM-DD"); self.start_date_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        customtkinter.CTkLabel(master=top_frame, text="End Date:").grid(row=1, column=0, padx=(5,0), pady=5, sticky="w"); self.end_date_entry = customtkinter.CTkEntry(master=top_frame, placeholder_text="YYYY-MM-DD"); self.end_date_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        customtkinter.CTkButton(master=top_frame, text="View Sales", command=self.generate_custom_report).grid(row=0, column=2, rowspan=2, padx=(10,5), pady=5, sticky="ns") 
        customtkinter.CTkButton(master=top_frame, text="Today's Summary", command=self.show_today_report).grid(row=0, column=3, rowspan=2, padx=5, pady=5, sticky="ns") 
        customtkinter.CTkButton(master=top_frame, text="Company Summary", command=self.generate_company_summary_csv).grid(row=0, column=4, rowspan=2, padx=5, pady=5, sticky="ns")
        customtkinter.CTkLabel(master=top_frame, text="Today's Expense:").grid(row=0, column=5, padx=(10,0), pady=5, sticky="w")
        self.entry_todays_expense = customtkinter.CTkEntry(master=top_frame, placeholder_text="Enter Amount", width=120, justify="right"); self.entry_todays_expense.grid(row=0, column=6, padx=5, pady=5, sticky="w"); self.entry_todays_expense.bind("<Return>", lambda e: self._update_net_revenue_display()); self.entry_todays_expense.bind("<KeyRelease>", lambda e: self._update_net_revenue_display()) 

        summary_frame = customtkinter.CTkFrame(master=top_frame, fg_color="transparent"); summary_frame.grid(row=1, column=5, columnspan=3, padx=5, pady=5, sticky="nsew"); summary_frame.grid_columnconfigure(0, weight=1) 
        self.label_total_sell = customtkinter.CTkLabel(master=summary_frame, text="Total Sell: 0.00 TK", font=("Roboto", 13), anchor="w"); self.label_total_sell.grid(row=0, column=0, sticky="w")
        self.label_total_profit = customtkinter.CTkLabel(master=summary_frame, text="Total Profit: 0.00 TK", font=("Roboto", 13), anchor="w"); self.label_total_profit.grid(row=1, column=0, sticky="w")
        self.label_net_revenue = customtkinter.CTkLabel(master=summary_frame, text="Net Revenue: 0.00 TK", font=("Roboto", 14, "bold"), text_color="#229954", anchor="w"); self.label_net_revenue.grid(row=2, column=0, sticky="w", pady=(5,0))

        rtf = customtkinter.CTkFrame(master=reports_frame); rtf.grid(row=1, column=0, padx=10, pady=10, sticky="nsew"); reports_frame.grid_rowconfigure(1, weight=1)
        self.report_tree = ttk.Treeview(master=rtf, columns=('invoice', 'date', 'name', 'qty', 'buy', 'sell', 'profit'), show='headings')
        for c, t in [('invoice','Invoice ID'), ('date','Date & Time'), ('name','Product Name'), ('qty','Qty Sold'), ('buy','Buy Price'), ('sell','Sell Price'), ('profit','Profit')]: self.report_tree.heading(c, text=t)
        for c, w in [('invoice',120), ('date',140), ('name',200), ('qty',80), ('buy',90), ('sell',90), ('profit',90)]: self.report_tree.column(c, width=w, anchor='center')
        self.report_tree.pack(fill="both", expand=True)
    
    def generate_company_summary_csv(self):
        start_date = self.start_date_entry.get(); end_date = self.end_date_entry.get()
        if not (len(start_date) == 10 and start_date[4] == '-' and start_date[7] == '-' and len(end_date) == 10 and end_date[4] == '-' and end_date[7] == '-'): messagebox.showerror("Invalid Format", "Use YYYY-MM-DD format."); return
        try: datetime.strptime(start_date, "%Y-%m-%d"); datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError: messagebox.showerror("Invalid Date", "Enter valid dates."); return
        summary_data = get_company_summary(start_date, end_date)
        if not summary_data: messagebox.showinfo("No Data", "No sales data found for the selected period."); return
        try:
            file_path = customtkinter.filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")], title="Save Company Summary As...", initialfile=f"company_summary_{start_date}_to_{end_date}.csv" )
            if not file_path: return 
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=['Company Name', 'Total Sales (TK)', 'Total Cost (TK)', 'Gross Profit (TK)']); writer.writeheader() 
                for company, data in summary_data.items(): writer.writerow({'Company Name': company, 'Total Sales (TK)': f"{data['sales']:.2f}", 'Total Cost (TK)': f"{data['cost']:.2f}", 'Gross Profit (TK)': f"{data['profit']:.2f}"})
            messagebox.showinfo("Export Successful", f"Company summary saved to:\n{file_path}")
        except Exception as e: messagebox.showerror("Export Error", f"Could not save the CSV file.\nError: {e}")
    
    def _update_net_revenue_display(self):
        try:
             total_profit = float(self.label_total_profit.cget("text").split(':')[1].strip().split(' ')[0])
             expense_str = self.entry_todays_expense.get(); todays_expense = float(expense_str) if expense_str else 0.0
             self.label_net_revenue.configure(text=f"Net Revenue: {total_profit - todays_expense:.2f} TK")
        except Exception: pass

    def on_customer_select(self, event=None):
        if self.customer_tree.focus(): 
            self.button_receive_payment.configure(state="normal"); self.button_export_ledger.configure(state="normal")
            self.button_view_history.configure(state="normal")
        else: 
            self.button_receive_payment.configure(state="disabled"); self.button_export_ledger.configure(state="disabled")
            self.button_view_history.configure(state="disabled")

    def _log_to_ledger(self, mobile, description, debit, credit, new_balance):
        try:
            conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("INSERT INTO customer_ledger (customer_mobile, date, description, debit, credit, balance) VALUES (?, ?, ?, ?, ?, ?)", (mobile, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), description, debit, credit, new_balance)); conn.commit(); conn.close()
        except Exception: pass

    def on_receive_payment_click(self):
        selected_item_iid = self.customer_tree.focus() 
        if not selected_item_iid: messagebox.showwarning("No Selection", "Please select a customer."); return
        payment_str = self.entry_receive_payment.get()
        if not payment_str: messagebox.showwarning("No Amount", "Please enter a payment amount."); return
        try:
            payment_amount = float(payment_str)
            if payment_amount <= 0: raise ValueError
        except ValueError: messagebox.showerror("Invalid Amount", "Positive number required."); return

        customer_data = get_customer_by_mobile(selected_item_iid)
        if not customer_data: return
        new_balance = customer_data[1] - payment_amount
        if not messagebox.askyesno("Confirm", f"Receive: {payment_amount:.2f}\nNew Due: {new_balance:.2f}\nSure?"): return

        self._log_to_ledger(selected_item_iid, "Payment Received (Deposit)", 0.0, payment_amount, new_balance)
        update_customer_due(selected_item_iid, new_balance)
        self.populate_customer_list(); self.entry_receive_payment.delete(0, 'end'); self.clear_customer_form(); self.sales_status_label.configure(text=f"Payment received", text_color="green")
        
    def export_customer_ledger(self):
        selected_item_iid = self.customer_tree.focus() 
        if not selected_item_iid: return
        try:
            conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("SELECT date, description, debit, credit, balance FROM customer_ledger WHERE customer_mobile = ? ORDER BY date ASC", (selected_item_iid,)); ledger_data = cursor.fetchall()
            cursor.execute("SELECT customer_name, previous_due FROM customers WHERE mobile = ?", (selected_item_iid,)); customer_info = cursor.fetchone(); conn.close()
            customer_name = customer_info[0] if customer_info else "Unknown"
            
            opening_balance = customer_info[1] if customer_info else 0.0
            if ledger_data: opening_balance = ledger_data[0][4] - ledger_data[0][2] + ledger_data[0][3]

            file_path = customtkinter.filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")], title=f"Save Ledger", initialfile=f"Ledger_{customer_name}_{selected_item_iid}.csv")
            if not file_path: return 
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile); writer.writerow(['Date', 'Description', 'Debit (Due+)', 'Credit (Paid-)', 'Balance']); writer.writerow(['-', 'Opening Balance', '-', '-', f"{opening_balance:.2f}"])
                for row in ledger_data: writer.writerow([datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %I:%M%p"), row[1], f"{row[2]:.2f}", f"{row[3]:.2f}", f"{row[4]:.2f}"])
            messagebox.showinfo("Export Successful", f"Ledger saved to:\n{file_path}")
        except Exception as e: messagebox.showerror("Export Error", f"Error: {e}")
        
    def view_purchase_history(self):
        selected_item_iid = self.customer_tree.focus()
        if not selected_item_iid: return
        customer_data = get_customer_by_mobile(selected_item_iid)
        customer_name = customer_data[0] if customer_data else "Unknown"
        CustomerHistoryWindow(self, selected_item_iid, customer_name).grab_set()
    
    def create_customers_tab(self):
        global customer_status_label 
        customer_main_frame = customtkinter.CTkFrame(master=self.customers_tab); customer_main_frame.pack(fill="both", expand=True)
        cust_input_frame = customtkinter.CTkFrame(master=customer_main_frame); cust_input_frame.pack(side="left", fill="y", padx=10, pady=10)
        customtkinter.CTkLabel(master=cust_input_frame, text="Customer Details", font=("Roboto", 20)).pack(pady=12, padx=10)

        entry_box_width = 180 
        self.entry_cust_mobile = customtkinter.CTkEntry(master=cust_input_frame, placeholder_text="Mobile Number*", width=entry_box_width); self.entry_cust_mobile.pack(pady=10, padx=10)
        self.entry_cust_name = customtkinter.CTkEntry(master=cust_input_frame, placeholder_text="Customer Name*", width=entry_box_width); self.entry_cust_name.pack(pady=10, padx=10)
        self.entry_cust_address = customtkinter.CTkEntry(master=cust_input_frame, placeholder_text="Address", width=entry_box_width); self.entry_cust_address.pack(pady=10, padx=10)
        self.entry_cust_due = customtkinter.CTkEntry(master=cust_input_frame, placeholder_text="Opening Due", width=entry_box_width); self.entry_cust_due.pack(pady=10, padx=10)

        cust_button_frame = customtkinter.CTkFrame(master=cust_input_frame, fg_color="transparent"); cust_button_frame.pack(pady=(15,0))
        self.save_customer_button = customtkinter.CTkButton(master=cust_button_frame, text="Save Customer", command=self.on_save_customer_click); self.save_customer_button.pack(side="left", padx=5)
        self.clear_customer_button = customtkinter.CTkButton(master=cust_input_frame, text="Clear Form", command=self.clear_customer_form, fg_color="gray"); self.clear_customer_button.pack(pady=(5,10), padx=10, fill="x")
        customer_status_label = customtkinter.CTkLabel(master=cust_input_frame, text="", font=("Roboto", 12)); customer_status_label.pack(pady=(0, 10))
        
        payment_frame = customtkinter.CTkFrame(master=cust_input_frame, fg_color="transparent"); payment_frame.pack(pady=(10,0), fill="x", padx=10)
        customtkinter.CTkLabel(master=payment_frame, text="Receive Payment:", font=("Roboto", 14, "bold")).pack(anchor="w")
        self.entry_receive_payment = customtkinter.CTkEntry(master=payment_frame, placeholder_text="Enter Amount", width=entry_box_width, justify="right"); self.entry_receive_payment.pack(pady=5, fill="x")
        self.button_receive_payment = customtkinter.CTkButton(master=payment_frame, text="Receive Payment", command=self.on_receive_payment_click); self.button_receive_payment.pack(pady=5, fill="x"); self.button_receive_payment.configure(state="disabled") 
        
        self.customer_form_widgets_order = [self.entry_cust_mobile, self.entry_cust_name, self.entry_cust_address, self.entry_cust_due, self.save_customer_button, self.clear_customer_button, self.entry_receive_payment, self.button_receive_payment]
        for i, widget in enumerate(self.customer_form_widgets_order):
            next_w = self.customer_form_widgets_order[(i + 1) % len(self.customer_form_widgets_order)]
            if widget == self.save_customer_button: widget.bind("<Return>", lambda e: self.on_save_customer_click())
            elif widget == self.clear_customer_button: widget.bind("<Return>", lambda e: self.clear_customer_form())
            elif widget == self.button_receive_payment: widget.bind("<Return>", lambda e: self.on_receive_payment_click())
            else: widget.bind("<Return>", lambda e, tw=next_w: (tw.focus_set(), "break")[1])

        cust_list_frame = customtkinter.CTkFrame(master=customer_main_frame); cust_list_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        cust_top_bar = customtkinter.CTkFrame(master=cust_list_frame, fg_color="transparent"); cust_top_bar.pack(fill="x", padx=10, pady=(10, 5))
        customtkinter.CTkLabel(master=cust_top_bar, text="Customer List", font=("Roboto", 20)).pack(side="left")
        self.total_due_label = customtkinter.CTkLabel(master=cust_top_bar, text="Total Market Due: 0.00 TK", font=("Roboto", 18, "bold"), text_color="red"); self.total_due_label.pack(side="right")
        
        search_frame = customtkinter.CTkFrame(master=cust_list_frame, fg_color="transparent"); search_frame.pack(fill="x", padx=10, pady=(0, 5))
        self.cust_search_entry = customtkinter.CTkEntry(master=search_frame, placeholder_text="Search by Name, Mobile, or Address...", width=300); self.cust_search_entry.pack(side="left", fill="x", expand=True); self.cust_search_entry.bind("<KeyRelease>", self.search_customer_list)
        customtkinter.CTkButton(master=search_frame, text="Refresh List", width=100, command=self.populate_customer_list).pack(side="right", padx=(10, 0))
        
        cust_columns = ('mobile', 'name', 'address', 'due'); self.customer_tree = ttk.Treeview(master=cust_list_frame, columns=cust_columns, show='headings'); self.customer_tree.heading('mobile', text='Mobile'); self.customer_tree.heading('name', text='Name'); self.customer_tree.heading('address', text='Address'); self.customer_tree.heading('due', text='Due (TK)'); self.customer_tree.column('mobile', width=100, anchor='center'); self.customer_tree.column('name', width=180, anchor='center'); self.customer_tree.column('address', width=200, anchor='center'); self.customer_tree.column('due', width=80, anchor='center'); self.customer_tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.customer_tree.bind("<Double-1>", self.load_customer_for_edit); self.customer_tree.bind("<Return>", self.load_customer_for_edit); self.customer_tree.bind("<ButtonRelease-1>", self.on_customer_select) 
        
        cust_action_frame = customtkinter.CTkFrame(master=cust_list_frame); cust_action_frame.pack(fill="x", padx=10, pady=5)
        customtkinter.CTkButton(master=cust_action_frame, text="Delete Selected", fg_color="red", hover_color="#CC0000", command=self.delete_selected_customer).pack(side="left", padx=5)
        self.button_export_ledger = customtkinter.CTkButton(master=cust_action_frame, text="Export Ledger (CSV)", command=self.export_customer_ledger); self.button_export_ledger.pack(side="left", padx=5); self.button_export_ledger.configure(state="disabled") 
        self.button_view_history = customtkinter.CTkButton(master=cust_action_frame, text="View Purchase History", command=self.view_purchase_history); self.button_view_history.pack(side="left", padx=5); self.button_view_history.configure(state="disabled")

    def _update_payment_display(self, *args):
        if not hasattr(self, 'entry_paid_amount'): return 
        try: bill_total = float(self.bill_total_label.cget("text").split(':')[1].strip().split(' ')[0])
        except: bill_total = 0.0
        previous_due = self.current_customer['due'] if self.current_customer else 0.0
        try: less_amount = float(self.entry_less_amount.get()) if self.entry_less_amount.get() else 0.0
        except ValueError: less_amount = 0.0
        try: adjust_amount = float(self.entry_adjust_amount.get()) if self.entry_adjust_amount.get() else 0.0
        except ValueError: adjust_amount = 0.0

        grand_total = bill_total + previous_due - less_amount - adjust_amount
        if self.check_mark_as_due.get() == 1: current_due = grand_total; self.entry_paid_amount.delete(0, 'end'); self.entry_paid_amount.configure(state="disabled") 
        else: 
            self.entry_paid_amount.configure(state="normal") 
            try: paid_amount = float(self.entry_paid_amount.get()) if self.entry_paid_amount.get() else 0.0
            except ValueError: paid_amount = 0.0 
            current_due = grand_total - paid_amount
        self.label_current_due.configure(text=f"Current Due: {current_due:.2f} TK")

    def _calculate_new_due(self):
        try: bill_total = float(self.bill_total_label.cget("text").split(':')[1].strip().split(' ')[0])
        except: bill_total = 0.0
        previous_due = self.current_customer['due'] if self.current_customer else 0.0
        try: less_amount = float(self.entry_less_amount.get()) if self.entry_less_amount.get() else 0.0
        except ValueError: less_amount = 0.0
        try: adjust_amount = float(self.entry_adjust_amount.get()) if self.entry_adjust_amount.get() else 0.0
        except ValueError: adjust_amount = 0.0
        
        if self.check_mark_as_due.get() == 1: new_total_due = previous_due + bill_total - less_amount - adjust_amount
        else: 
            try: paid_amount = float(self.entry_paid_amount.get()) if self.entry_paid_amount.get() else 0.0
            except ValueError: paid_amount = 0.0
            new_total_due = previous_due + bill_total - less_amount - adjust_amount - paid_amount
        return max(0, new_total_due)
    
    def clear_add_product_form(self):
        self.entry_name.delete(0, 'end'); self.entry_company.delete(0, 'end'); self.entry_quantity.delete(0, 'end'); self.entry_price.delete(0, 'end'); self.entry_purchase_price.delete(0, 'end'); self.entry_expiry_date.delete(0, 'end'); self.entry_name.focus_set(); 
        
    def refresh_add_product_suggestions(self):
        if hasattr(self, 'entry_name'): self.entry_name.completions = get_distinct_product_names()
        if hasattr(self, 'entry_company'): self.entry_company.completions = get_distinct_company_names()
        if hasattr(self, 'entry_sales_cust_mobile'): self.entry_sales_cust_mobile.completions = self.get_customer_search_suggestions()
        self.populate_stock_list()
        self.refresh_low_stock_display()
        
    def on_add_button_click(self):
        name = self.entry_name.get(); company = self.entry_company.get(); quantity = self.entry_quantity.get(); price = self.entry_price.get(); purchase_price = self.entry_purchase_price.get(); expiry_date = self.entry_expiry_date.get()
        if not all([name, quantity, price]): status_label.configure(text="Name, Qty, & Sell Price required.", text_color="orange"); return
        try:
            success, message = add_product_to_db(name, company, int(quantity), float(price), float(purchase_price) if purchase_price else None, expiry_date)
            if success: 
                status_label.configure(text=f"'{name}' is added to the inventory.", text_color="green")
                self.refresh_add_product_suggestions(); self.clear_add_product_form()
            else: status_label.configure(text=message, text_color="red")
        except ValueError: status_label.configure(text="Ensure Qty, Sell & Buy Prices are numbers.", text_color="orange")
        except Exception as e: status_label.configure(text="An unexpected error occurred.", text_color="red")
        
    def search_stock_list(self, event=None):
        query = self.stock_search_entry.get().lower();
        for row in self.stock_tree.get_children(): self.stock_tree.delete(row)
        count = 0
        for product in get_all_products():
            if query in str(product[0]).lower() or query in str(product[1]).lower() or (product[2] and query in str(product[2]).lower()): 
                tag = 'evenrow' if count % 2 == 0 else 'oddrow'
                self.stock_tree.insert('', 'end', iid=product[0], values=(product[1], product[2], product[3], product[4], product[5], product[6]), tags=(tag,))
                count += 1
            
    def focus_on_stock_tree(self, event=None):
        if len(self.stock_tree.get_children()) > 0: self.stock_tree.focus_set(); self.stock_tree.selection_set(self.stock_tree.get_children()[0])
        
    def edit_selected_product(self, event=None):
        selected_item_iid = self.stock_tree.focus(); 
        if not selected_item_iid: return
        conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("SELECT * FROM products WHERE product_code=?", (selected_item_iid,)); product_data = cursor.fetchone(); conn.close()
        if product_data: EditProductWindow(self, product_data, self).grab_set()
        
    def delete_selected_product(self):
        selected_item_iid = self.stock_tree.focus(); 
        if not selected_item_iid: return
        try: product_name = self.stock_tree.item(selected_item_iid, 'values')[0]
        except Exception: product_name = "this product"
        if messagebox.askyesno("Confirm Delete", f"Delete '{product_name}'?"):
            if delete_product_from_db(selected_item_iid): self.refresh_add_product_suggestions(); messagebox.showinfo("Deleted", f"'{product_name}' deleted.")
            
    def populate_stock_list(self):
        if hasattr(self, 'stock_search_entry'): self.stock_search_entry.delete(0, 'end')
        if hasattr(self, 'stock_tree'): 
            for row in self.stock_tree.get_children(): self.stock_tree.delete(row)
            count = 0
            for product in get_all_products(): 
                tag = 'evenrow' if count % 2 == 0 else 'oddrow'
                self.stock_tree.insert('', 'end', iid=product[0], values=(product[1], product[2], product[3], product[4], product[5], product[6]), tags=(tag,)) 
                count += 1
        self.update_stock_value_display()
        if hasattr(self, 'low_stock_tree'): self.refresh_low_stock_display()

    def sort_stock_by_expiry(self, reverse_sort=False):
        items = []; 
        if not hasattr(self, 'stock_tree'): return 
        for item_id in self.stock_tree.get_children():
            try:
                item_values = self.stock_tree.item(item_id, 'values')
                if isinstance(item_values, tuple) and len(item_values) >= 6: items.append((item_id, item_values))
            except Exception: continue
        def get_sortable_date(date_str):
            if not date_str or str(date_str).lower() == 'none': return '99999999' 
            try:
                dt = None
                for fmt in ["%d/%m/%y", "%d-%m-%y", "%d/%m/%Y", "%d-%m-%Y"]:
                    try: dt = datetime.strptime(str(date_str), fmt); break
                    except ValueError: continue
                if dt is None: raise ValueError
                if dt.year > datetime.now().year + 25: dt = dt.replace(year=dt.year - 100)
                return dt.strftime('%Y%m%d')
            except ValueError: return '99999998' 
        try: items.sort(key=lambda x: get_sortable_date(x[1][5]) if len(x[1]) >= 6 else '99999999', reverse=reverse_sort)
        except Exception: return 
        for item_id in self.stock_tree.get_children(): self.stock_tree.delete(item_id)
        count = 0
        for item_id, values in items: 
            tag = 'evenrow' if count % 2 == 0 else 'oddrow'
            self.stock_tree.insert('', 'end', iid=item_id, values=values, tags=(tag,))
            count += 1

    def focus_on_search_list(self, event=None):
        if self.search_results_listbox.size() > 0: self.search_results_listbox.focus_set(); self.search_results_listbox.selection_set(0)
    def focus_on_search_entry(self, event=None): self.search_entry.focus_set()
    def update_search_results(self, event):
        query = self.search_entry.get(); self.search_results_listbox.delete(0, 'end'); results = search_products(query) 
        for item in results: self.search_results_listbox.insert('end', f"{item[0]} - {item[1]} (Stock: {item[2]}) - {item[3]:.2f} TK")
        
    def add_to_cart(self, event):
        self.cart = getattr(self, 'cart', []) 
        selected_indices = self.search_results_listbox.curselection()
        if not selected_indices: return 
        try: product_code = self.search_results_listbox.get(selected_indices[0]).split(" - ")[0]
        except IndexError: return
        conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("SELECT product_name, unit_price, quantity FROM products WHERE product_code=?", (product_code,)); product_info = cursor.fetchone(); conn.close()
        if not product_info: return
            
        product_name, default_unit_price, current_db_stock = product_info
        try: details = SaleItemDetailsDialog(self, title="Add Item", product_name=product_name, current_stock=current_db_stock, default_price=default_unit_price).get_input() 
        except Exception: return 

        if details:
            qty_str, expiry_str, discount_str, custom_price_str = details 
            try:
                quantity_to_add = int(qty_str)
                try: discount_percent = float(discount_str) if discount_str else 0.0
                except ValueError: discount_percent = 0.0
                expiry_date = expiry_str.strip() if expiry_str else None 
                try: unit_price_to_use = float(custom_price_str) if custom_price_str else default_unit_price
                except ValueError: unit_price_to_use = default_unit_price 

                if quantity_to_add <= 0 or not (0 <= discount_percent <= 100): return
                product_found_in_cart = next((item for item in self.cart if item['code'] == product_code), None)
                
                if quantity_to_add <= current_db_stock:
                    update_stock_after_sale(product_code, quantity_to_add)
                    if product_found_in_cart: product_found_in_cart['quantity'] += quantity_to_add
                    else: self.cart.append({'code': product_code, 'name': product_name, 'quantity': quantity_to_add, 'price': unit_price_to_use, 'expiry_date': expiry_date, 'discount_percent': discount_percent}) 
                    
                    self.update_cart_display(); self.populate_stock_list() 
                    self.search_entry.focus_set(); self.search_entry.delete(0, 'end'); self.update_search_results(None) 
                else: self.sales_status_label.configure(text=f"Not enough stock.", text_color="red")
            except (ValueError, TypeError): pass
            
    def edit_cart_item(self, event=None):
        selected_indices = self.cart_listbox.curselection()
        if not selected_indices: return
        idx = selected_indices[0]; item = self.cart[idx]
        
        conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("SELECT quantity FROM products WHERE product_code=?", (item['code'],)); product_info = cursor.fetchone(); conn.close()
        current_db_stock = product_info[0] if product_info else 0
        max_available = current_db_stock + item['quantity']
        
        try: details = SaleItemDetailsDialog(self, title="Edit Cart Item", product_name=item['name'], current_stock=max_available, default_price=item['price'], initial_qty=str(item['quantity']), initial_custom_price=str(item['price']), initial_expiry=item.get('expiry_date', '') or "", initial_discount=str(item.get('discount_percent', '')) or "").get_input() 
        except Exception: return 

        if details:
            qty_str, expiry_str, discount_str, custom_price_str = details 
            try:
                new_qty = int(qty_str)
                try: new_discount = float(discount_str) if discount_str else 0.0
                except ValueError: new_discount = 0.0
                try: new_price = float(custom_price_str) if custom_price_str else item['price']
                except ValueError: new_price = item['price']
                if new_qty <= 0 or not (0 <= new_discount <= 100): return

                qty_diff = new_qty - item['quantity']
                if qty_diff <= current_db_stock:
                    update_stock_after_sale(item['code'], qty_diff) 
                    item['quantity'] = new_qty; item['price'] = new_price; item['expiry_date'] = expiry_str.strip() if expiry_str else None; item['discount_percent'] = new_discount
                    self.update_cart_display(); self.populate_stock_list() 
                else: self.sales_status_label.configure(text=f"Not enough stock.", text_color="red")
            except (ValueError, TypeError): pass

    def remove_cart_item(self, event=None):
        selected_indices = self.cart_listbox.curselection()
        if not selected_indices: return
        idx = selected_indices[0]; item = self.cart[idx]
        try:
            update_stock_after_sale(item['code'], -item['quantity']); self.cart.pop(idx)
            self.update_cart_display(); self.populate_stock_list()
            self.search_entry.focus_set(); self.update_search_results(None) 
        except Exception: pass

    def update_cart_display(self):
        self.cart_listbox.delete(0, 'end'); bill_total = 0.0
        for item in self.cart: 
            discount = item.get('discount_percent', 0.0); discount_amount = (item['quantity'] * item['price']) * (discount / 100); subtotal = (item['quantity'] * item['price']) - discount_amount; bill_total += subtotal
            expiry_display = f" (Exp: {item.get('expiry_date','-')})" if item.get('expiry_date') else ""; discount_display = f" [-{discount:.0f}%]" if discount > 0 else ""
            self.cart_listbox.insert('end', f"{item['quantity']} x {item['name']}{expiry_display} @ {item['price']:.2f}{discount_display} = {subtotal:.2f}")
        
        self.label_total_items.configure(text=f"Total Items: {len(self.cart)}") 
        self.bill_total_label.configure(text=f"Bill Total: {bill_total:.2f} TK")
        self._update_payment_display()

    def finalize_sale(self):
        if not self.cart: return
        invoice_id = f"{self.current_customer['mobile'] if self.current_customer else (self.entry_sales_cust_name.get().strip().replace(' ', '_') or 'NA')}_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        pdf_path = os.path.join("invoice", f"invoice_{invoice_id}.pdf")
        if not os.path.exists("invoice"): os.makedirs("invoice")

        previous_due_before_sale = self.current_customer['due'] if self.current_customer else 0.0 
        doctor_name = self.entry_sales_doctor.get() 
        log_sale_in_db(invoice_id, self.cart, self.current_customer['mobile'] if self.current_customer else "NA", doctor_name) 
        
        bill_total = sum(((item['quantity'] * item['price']) - ((item['quantity'] * item['price']) * (item.get('discount_percent', 0.0) / 100))) for item in self.cart)
        
        try: less_amount = float(self.entry_less_amount.get()) if self.entry_less_amount.get() else 0.0
        except ValueError: less_amount = 0.0
        try: adjust_amount = float(self.entry_adjust_amount.get()) if self.entry_adjust_amount.get() else 0.0
        except ValueError: adjust_amount = 0.0

        if self.current_customer: 
            new_total_due = self._calculate_new_due() 
            paid_amount = (bill_total + previous_due_before_sale - less_amount - adjust_amount) - new_total_due 
            actual_bill_charge = bill_total - less_amount - adjust_amount
            self._log_to_ledger(self.current_customer['mobile'], f"Sale (Inv: {invoice_id})", actual_bill_charge, 0.0, previous_due_before_sale + actual_bill_charge)
            if paid_amount > 0: self._log_to_ledger(self.current_customer['mobile'], f"Payment (Inv: {invoice_id})", 0.0, paid_amount, new_total_due)
            update_customer_due(self.current_customer['mobile'], new_total_due)
        else: 
            if self.check_mark_as_due_var.get() == 0: 
                try: paid_amount = float(self.entry_paid_amount.get()) if self.entry_paid_amount.get() else (bill_total - less_amount - adjust_amount)
                except ValueError: paid_amount = 0.0
            new_total_due = max(0, (bill_total - less_amount - adjust_amount) - paid_amount) 

        pdf_generated_successfully = False
        if self.print_receipt_var.get() == 1:
            try: 
                customer_info_for_pdf = self.current_customer.copy() if self.current_customer else {'mobile': None, 'name': self.entry_sales_cust_name.get() or "Walk-in", 'due': 0.0}
                if self.current_customer: customer_info_for_pdf['due'] = previous_due_before_sale
                generate_invoice_pdf(invoice_id, self.cart, bill_total, customer_info_for_pdf, doctor_name, paid_amount, new_total_due, pdf_path, less_amount, adjust_amount) 
                if os.path.exists(pdf_path): pdf_generated_successfully = True
            except Exception: pass
        
        if pdf_generated_successfully:
            try:
                absolute_path = os.path.abspath(pdf_path) 
                if PRINT_METHOD == "DIRECT_POS" and sys.platform == "win32": os.startfile(absolute_path, 'print')
                else: webbrowser.open(f"file:///{absolute_path}")
            except Exception: pass
        
        self.sales_status_label.configure(text=f"Sale OK! Inv: {invoice_id}", text_color="green")
        self.refresh_add_product_suggestions(); self.clear_cart(restore_stock=False) 
        self.entry_sales_cust_mobile.delete(0,'end'); self.entry_sales_doctor.delete(0,'end'); self.entry_sales_cust_name.configure(state="normal"); self.entry_sales_cust_name.delete(0, 'end'); self.current_customer = None; self.label_sales_cust_due.configure(text="Previous Due: 0.00 TK"); self._update_payment_display(); self.print_receipt_var.set(1)

    def clear_cart(self, restore_stock=True):
        if restore_stock and getattr(self, 'cart', None):
            for item in self.cart: update_stock_after_sale(item['code'], -item['quantity'])
            self.populate_stock_list()

        self.cart = []; self.update_cart_display(); self.sales_status_label.configure(text="")
        self.entry_sales_cust_mobile.delete(0, 'end'); self.entry_sales_doctor.delete(0, 'end'); self.entry_sales_cust_name.configure(state="normal"); self.entry_sales_cust_name.delete(0, 'end'); self.current_customer = None; self.label_sales_cust_due.configure(text="Previous Due: 0.00 TK")
        if hasattr(self, 'entry_paid_amount'): self.entry_paid_amount.delete(0, 'end')
        if hasattr(self, 'entry_less_amount'): self.entry_less_amount.delete(0, 'end')
        if hasattr(self, 'entry_adjust_amount'): self.entry_adjust_amount.delete(0, 'end')
        if hasattr(self, 'check_mark_as_due_var'): self.check_mark_as_due_var.set(0) 
        self._update_payment_display()

    def lookup_customer(self, event=None):
        raw_input = self.entry_sales_cust_mobile.get().strip()
        if not raw_input: 
             self.current_customer = None; self.entry_sales_cust_name.configure(state="normal"); self.entry_sales_cust_name.delete(0, 'end'); self.label_sales_cust_due.configure(text="Previous Due: 0.00 TK"); self.update_cart_display(); self._update_payment_display(); return
        search_term = raw_input
        if "(" in raw_input and ")" in raw_input: search_term = raw_input.split("(")[-1].replace(")", "").strip()
        conn = connect_to_db(); cursor = conn.cursor()
        cursor.execute("SELECT mobile, customer_name, previous_due FROM customers WHERE mobile = ? OR customer_name = ?", (search_term, raw_input))
        customer_data = cursor.fetchone()
        if not customer_data: cursor.execute("SELECT mobile, customer_name, previous_due FROM customers WHERE mobile LIKE ? OR customer_name LIKE ? LIMIT 1", ('%' + search_term + '%', '%' + search_term + '%')); customer_data = cursor.fetchone()
        conn.close()
        
        if customer_data:
            mobile, name, due = customer_data; self.current_customer = {'mobile': mobile, 'name': name, 'due': due}
            self.entry_sales_cust_name.configure(state="normal"); self.entry_sales_cust_name.delete(0, 'end'); self.entry_sales_cust_name.insert(0, name); self.entry_sales_cust_name.configure(state="disabled"); self.label_sales_cust_due.configure(text=f"Previous Due: {due:.2f} TK")
        else: self.current_customer = None; self.entry_sales_cust_name.configure(state="normal"); self.entry_sales_cust_name.delete(0, 'end'); self.label_sales_cust_due.configure(text="Previous Due: 0.00 TK")
        self.update_cart_display(); self._update_payment_display()

    def lookup_customer_after_selection(self, event=None): self.lookup_customer(event); self.entry_sales_cust_mobile.focus_set(); return "break" 
    
    def generate_custom_report(self):
        start_date = self.start_date_entry.get(); end_date = self.end_date_entry.get()
        if (len(start_date) == 10 and start_date[4] == '-' and start_date[7] == '-' and len(end_date) == 10 and end_date[4] == '-' and end_date[7] == '-'):
            try: 
                 datetime.strptime(start_date, "%Y-%m-%d"); datetime.strptime(end_date, "%Y-%m-%d")
                 self.populate_report_table(start_date, end_date)
                 if start_date == end_date: total_sales, total_profit = get_daily_summary(start_date); self.label_total_sell.configure(text=f"Total Sell: {total_sales:.2f} TK"); self.label_total_profit.configure(text=f"Total Profit: {total_profit:.2f} TK")
                 else: 
                     ts, tp = get_summary_by_date_range(start_date, end_date)
                     self.label_total_sell.configure(text=f"Total Sell: {ts:.2f} TK"); self.label_total_profit.configure(text=f"Total Profit: {tp:.2f} TK")
                 self._update_net_revenue_display() 
            except ValueError: messagebox.showerror("Invalid Date", "Enter valid dates.")
        else: messagebox.showerror("Invalid Format", "Use YYYY-MM-DD format.")

    def show_today_report(self):
        today = date.today().strftime("%Y-%m-%d")
        self.start_date_entry.delete(0, 'end'); self.start_date_entry.insert(0, today); self.end_date_entry.delete(0, 'end'); self.end_date_entry.insert(0, today)
        self.populate_report_table(today, today)
        total_sales, total_profit = get_daily_summary(today); self.label_total_sell.configure(text=f"Total Sell: {total_sales:.2f} TK"); self.label_total_profit.configure(text=f"Total Profit: {total_profit:.2f} TK")
        self._update_net_revenue_display()

    def populate_report_table(self, start_date, end_date):
        for row in self.report_tree.get_children(): self.report_tree.delete(row)
        count = 0
        for r in get_sales_by_date_range(start_date, end_date): 
            fmt_r = (r[0], r[1], r[2], r[3], f"{r[4]:.2f}", f"{r[5]:.2f}", f"{r[6]:.2f}")
            tag = 'evenrow' if count % 2 == 0 else 'oddrow'
            self.report_tree.insert('', 'end', values=fmt_r, tags=(tag,))
            count += 1

    def clear_customer_form(self):
        if self.entry_cust_mobile.cget("state") == "disabled": self.entry_cust_mobile.configure(state="normal")
        self.entry_cust_mobile.delete(0, 'end'); self.entry_cust_name.delete(0, 'end'); self.entry_cust_address.delete(0, 'end'); self.entry_cust_due.delete(0, 'end')
        self.entry_cust_mobile.focus_set(); 
        if 'customer_status_label' in globals() and customer_status_label: customer_status_label.configure(text="")
        self.save_customer_button.configure(text="Save Customer") 
         
    def on_save_customer_click(self):
        is_update_mode = self.entry_cust_mobile.cget("state") == "disabled"
        if is_update_mode: self.entry_cust_mobile.configure(state="normal")
        mobile = self.entry_cust_mobile.get(); name = self.entry_cust_name.get(); address = self.entry_cust_address.get(); due_str = self.entry_cust_due.get()

        if not mobile or not name: customer_status_label.configure(text="Mobile and Name required.", text_color="orange"); return
        try:
            success, message = add_or_update_customer(mobile, name, address, float(due_str) if due_str else 0.0)
            if success: customer_status_label.configure(text=message, text_color="green"); self.populate_customer_list(); self.clear_customer_form(); self.refresh_add_product_suggestions() 
            else: 
                customer_status_label.configure(text=message, text_color="red")
                if is_update_mode: self.entry_cust_mobile.configure(state="disabled")
        except ValueError: 
            customer_status_label.configure(text="Previous Due must be a number.", text_color="orange")
            if is_update_mode: self.entry_cust_mobile.configure(state="disabled")

    def populate_customer_list(self):
        if hasattr(self, 'customer_tree'): 
            for row in self.customer_tree.get_children(): self.customer_tree.delete(row)
            total_market_due = 0.0; count = 0
            for customer in get_all_customers(): 
                tag = 'evenrow' if count % 2 == 0 else 'oddrow'
                self.customer_tree.insert('', 'end', iid=customer[0], values=(customer[0], customer[1], customer[2], f"{customer[3]:.2f}"), tags=(tag,))
                total_market_due += float(customer[3])
                count += 1
            if hasattr(self, 'total_due_label'): self.total_due_label.configure(text=f"Total Market Due: {total_market_due:,.2f} TK")

    def search_customer_list(self, event=None):
        query = self.cust_search_entry.get().lower()
        for row in self.customer_tree.get_children(): self.customer_tree.delete(row)
        count = 0
        for customer in get_all_customers():
            if query in str(customer[0]).lower() or query in str(customer[1]).lower() or (customer[2] and query in str(customer[2]).lower()):
                tag = 'evenrow' if count % 2 == 0 else 'oddrow'
                self.customer_tree.insert('', 'end', iid=customer[0], values=(customer[0], customer[1], customer[2], f"{customer[3]:.2f}"), tags=(tag,))
                count += 1

    def load_customer_for_edit(self, event):
        selected_item_iid = self.customer_tree.focus() 
        if not selected_item_iid: return
        conn = connect_to_db(); cursor = conn.cursor(); cursor.execute("SELECT mobile, customer_name, address, previous_due FROM customers WHERE mobile=?", (selected_item_iid,)); customer_data = cursor.fetchone(); conn.close()
        if not customer_data: return
        self.clear_customer_form(); self.entry_cust_mobile.insert(0, customer_data[0]); self.entry_cust_name.insert(0, customer_data[1]); self.entry_cust_address.insert(0, customer_data[2] if customer_data[2] else ""); self.entry_cust_due.insert(0, f"{customer_data[3]:.2f}") 
        self.save_customer_button.configure(text="Update Customer"); self.entry_cust_mobile.configure(state="disabled") 

    def delete_selected_customer(self):
        selected_item_iid = self.customer_tree.focus() 
        if not selected_item_iid: return
        try: customer_name = self.customer_tree.item(selected_item_iid, 'values')[1]
        except Exception: customer_name = "this customer"
        if messagebox.askyesno("Confirm Delete", f"Delete '{customer_name}' ({selected_item_iid})?"):
            if delete_customer(selected_item_iid): self.populate_customer_list(); messagebox.showinfo("Deleted", f"'{customer_name}' deleted."); self.refresh_add_product_suggestions() 

class CustomerHistoryWindow(customtkinter.CTkToplevel):
    def __init__(self, master, mobile, name):
        super().__init__(master); self.title("Purchase History"); self.geometry("800x500"); self.lift(); self.focus_set()
        customtkinter.CTkLabel(self, text=f"Purchase History: {name} ({mobile})", font=("Roboto", 18, "bold")).pack(pady=15)
        
        tf = customtkinter.CTkFrame(self, fg_color="transparent"); tf.pack(expand=True, fill="both", padx=20, pady=(0, 20))
        self.tree = ttk.Treeview(tf, columns=('date', 'invoice', 'product', 'qty', 'price', 'total'), show='headings')
        for c, t in [('date', 'Date & Time'), ('invoice', 'Invoice No.'), ('product', 'Product Name'), ('qty', 'Qty'), ('price', 'Unit Price'), ('total', 'Total Price')]: self.tree.heading(c, text=t)
        for c, w in [('date', 140), ('invoice', 160), ('product', 200), ('qty', 60), ('price', 80), ('total', 90)]: self.tree.column(c, width=w, anchor='center')
        
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview); self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); self.tree.pack(side="left", fill="both", expand=True)
        
        self.populate(mobile)
        customtkinter.CTkButton(self, text="Close", command=self.destroy, width=100).pack(pady=(0, 15))

    def populate(self, mobile):
        try:
            conn = connect_to_db(); cursor = conn.cursor()
            cursor.execute("SELECT sale_date, invoice_id, product_name, quantity_sold, price_per_unit, total_price FROM sales WHERE invoice_id LIKE ? ORDER BY sale_date DESC", (f"{mobile}_%",))
            res = cursor.fetchall(); conn.close()
            for c, r in enumerate(res): self.tree.insert('', 'end', values=(r[0], r[1], r[2], r[3], f"{r[4]:.2f}", f"{r[5]:.2f}"), tags=('evenrow' if c % 2 == 0 else 'oddrow',))
        except Exception as e: messagebox.showerror("Error", f"Could not load history: {e}")

if __name__ == "__main__":
    connect_to_db() 
    app = PharmacyApp()
    app.mainloop()