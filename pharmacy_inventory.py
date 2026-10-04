import sqlite3
import tkinter
import customtkinter

# --- Database Functions ---

def connect_to_db():
    """ডাটাবেসের সাথে কানেক্ট করে এবং টেবিল তৈরি নিশ্চিত করে"""
    conn = sqlite3.connect('products.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            product_code TEXT PRIMARY KEY,
            product_name TEXT NOT NULL,
            company_name TEXT,
            generic_name TEXT,
            quantity INTEGER NOT NULL,
            location TEXT,
            unit_price REAL NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def add_product_to_db(code, name, company, generic, quantity, location, price):
    """ডাটাবেসে নতুন প্রোডাক্ট যোগ করে"""
    try:
        conn = sqlite3.connect('products.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO products (product_code, product_name, company_name, generic_name, quantity, location, unit_price) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (code, name, company, generic, quantity, location, price))
        conn.commit()
        conn.close()
        status_label.configure(text=f"Product '{name}' added successfully!", text_color="green")
    except sqlite3.IntegrityError:
        status_label.configure(text=f"Error: Product code '{code}' already exists.", text_color="red")
    except Exception as e:
        status_label.configure(text=f"An error occurred: {e}", text_color="red")

# --- UI Functions ---

def on_add_button_click():
    """'Add Product' বাটনে ক্লিক করলে এই ফাংশনটি কাজ করবে"""
    code = entry_code.get()
    name = entry_name.get()
    company = entry_company.get()
    generic = entry_generic.get()
    quantity = entry_quantity.get()
    location = entry_location.get()
    price = entry_price.get()

    # বেসিক ভ্যালিডেশন
    if not all([code, name, quantity, price]):
        status_label.configure(text="Code, Name, Quantity, and Price are required.", text_color="red")
        return

    try:
        # সংখ্যা এবং মূল্য সঠিক কিনা তা পরীক্ষা করা
        quantity_val = int(quantity)
        price_val = float(price)
        add_product_to_db(code, name, company, generic, quantity_val, location, price_val)
        # ইনপুট ফিল্ডগুলো খালি করা
        clear_entries()
    except ValueError:
        status_label.configure(text="Quantity must be an integer and Price must be a number.", text_color="red")

def clear_entries():
    """সব ইনপুট বক্স খালি করে"""
    entry_code.delete(0, 'end')
    entry_name.delete(0, 'end')
    entry_company.delete(0, 'end')
    entry_generic.delete(0, 'end')
    entry_quantity.delete(0, 'end')
    entry_location.delete(0, 'end')
    entry_price.delete(0, 'end')
    entry_code.focus()


# --- Main Application Setup ---
connect_to_db()  # প্রোগ্রাম শুরুতেই ডাটাবেস কানেক্ট ও টেবিল তৈরি করবে

app = customtkinter.CTk()
app.title("Pharmacy Inventory - Add Product")
app.geometry("500x550")

# --- UI Widgets ---
frame = customtkinter.CTkFrame(master=app)
frame.pack(pady=20, padx=20, fill="both", expand=True)

main_label = customtkinter.CTkLabel(master=frame, text="Add New Product to Inventory", font=("Roboto", 20))
main_label.pack(pady=12, padx=10)

# Entry fields for product details
entry_code = customtkinter.CTkEntry(master=frame, placeholder_text="Product Code*")
entry_code.pack(pady=10, padx=10)

entry_name = customtkinter.CTkEntry(master=frame, placeholder_text="Product Name*")
entry_name.pack(pady=10, padx=10)

entry_company = customtkinter.CTkEntry(master=frame, placeholder_text="Company Name")
entry_company.pack(pady=10, padx=10)

entry_generic = customtkinter.CTkEntry(master=frame, placeholder_text="Generic Name")
entry_generic.pack(pady=10, padx=10)

entry_quantity = customtkinter.CTkEntry(master=frame, placeholder_text="Quantity*")
entry_quantity.pack(pady=10, padx=10)

entry_location = customtkinter.CTkEntry(master=frame, placeholder_text="Location (e.g., Rack A1)")
entry_location.pack(pady=10, padx=10)

entry_price = customtkinter.CTkEntry(master=frame, placeholder_text="Unit Price*")
entry_price.pack(pady=10, padx=10)

# Button to add the product
add_button = customtkinter.CTkButton(master=frame, text="Add Product", command=on_add_button_click)
add_button.pack(pady=20, padx=10)

# Status label to show success or error messages
status_label = customtkinter.CTkLabel(master=frame, text="", font=("Roboto", 12))
status_label.pack(pady=5, padx=10)

app.mainloop()