PRAGMA foreign_keys = ON;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT
);

CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    isbn TEXT,
    price REAL,
    quantity INTEGER,
    shelf_location TEXT
);

CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT,
    phone TEXT
);

CREATE TABLE suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_name TEXT,
    email TEXT,
    phone TEXT,
    address TEXT
);

CREATE TABLE sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    user_id INTEGER,
    sale_date TEXT DEFAULT CURRENT_TIMESTAMP,
    subtotal REAL,
    tax REAL,
    total REAL,
    payment_method TEXT,
    amount_paid REAL,
    change_due REAL,
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    quantity INTEGER,
    price_each REAL,
    line_total REAL,
    FOREIGN KEY (sale_id) REFERENCES sales(id),
    FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE supplier_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL,
    user_id INTEGER,
    order_date TEXT DEFAULT CURRENT_TIMESTAMP,
    total_cost REAL,
    status TEXT,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE supplier_order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_order_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    quantity_ordered INTEGER,
    cost_each REAL,
    FOREIGN KEY (supplier_order_id) REFERENCES supplier_orders(id),
    FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE customer_request (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    -- if requested, we likely wouldn't have it in our DB. 
    -- should requested books be immediately inserted to our DB with QTY of 0?
    --book_id INTEGER,
    requested_title TEXT,
    requested_author TEXT,
    request_date TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    --FOREIGN KEY (book_id) REFERENCES books(id)
);
