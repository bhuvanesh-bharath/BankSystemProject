import sqlite3
import uuid
import datetime
import hashlib

DATABASE = 'bank.db'

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn

def init_db():
    """Initializes the database by creating tables and inserting mock data if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL, -- 'Customer', 'Staff', 'Admin'
            status TEXT NOT NULL, -- 'Active', 'Inactive'
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    # Create Accounts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Accounts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            account_number TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL, -- Denormalized for easier lookup
            account_type TEXT NOT NULL, -- 'Savings', 'Checking'
            balance REAL NOT NULL,
            status TEXT NOT NULL, -- 'Active', 'Closed'
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
        )
    ''')

    # Create Transactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Transactions (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            account_number TEXT NOT NULL, -- Denormalized
            customer_name TEXT NOT NULL, -- Denormalized
            type TEXT NOT NULL, -- 'Deposit', 'Withdrawal', 'Transfer', 'Deposit (Adjustment)', 'Withdrawal (Adjustment)', 'Deposit (Reversal)', 'Withdrawal (Reversal)'
            amount REAL NOT NULL,
            transaction_date TEXT NOT NULL,
            status TEXT NOT NULL, -- 'Completed', 'Pending', 'Failed', 'Reversed'
            description TEXT,
            FOREIGN KEY (account_id) REFERENCES Accounts(id) ON DELETE CASCADE
        )
    ''')

    # Create AuditLogs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS AuditLogs (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            admin_user TEXT NOT NULL, -- e.g., 'Admin User (U005)'
            action_type TEXT NOT NULL, -- e.g., 'User Added', 'Balance Adjusted'
            action_details TEXT NOT NULL
        )
    ''')

    # Check if tables are empty and insert mock data if they are
    cursor.execute("SELECT COUNT(*) FROM Users")
    if cursor.fetchone()[0] == 0:
        print("Inserting mock data...")
        now = datetime.datetime.now().isoformat()

        # Users
        users_data = [
            {'id': 'U001', 'name': 'Alice Smith', 'email': 'alice.s@example.com', 'role': 'Customer', 'status': 'Active', 'password': 'password123'},
            {'id': 'U002', 'name': 'Bob Johnson', 'email': 'bob.j@example.com', 'role': 'Customer', 'status': 'Active', 'password': 'password123'},
            {'id': 'U003', 'name': 'Charlie Brown', 'email': 'charlie.b@example.com', 'role': 'Customer', 'status': 'Inactive', 'password': 'password123'},
            {'id': 'U004', 'name': 'David Lee', 'email': 'david.l@example.com', 'role': 'Staff', 'status': 'Active', 'password': 'staffpass'},
            {'id': 'U005', 'name': 'Admin User', 'email': 'admin@example.com', 'role': 'Admin', 'status': 'Active', 'password': 'adminpass'}
        ]
        for user in users_data:
            hashed_password = hashlib.sha256(user['password'].encode()).hexdigest()
            cursor.execute('''
                INSERT INTO Users (id, name, email, password_hash, role, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user['id'], user['name'], user['email'], hashed_password, user['role'], user['status'], now, now))

        # Accounts
        accounts_data = [
            {'id': 'A001', 'user_id': 'U001', 'account_number': '100010001', 'customer_name': 'Alice Smith', 'account_type': 'Savings', 'balance': 5000.75, 'status': 'Active'},
            {'id': 'A002', 'user_id': 'U002', 'account_number': '100010002', 'customer_name': 'Bob Johnson', 'account_type': 'Checking', 'balance': 1250.20, 'status': 'Active'},
            {'id': 'A003', 'user_id': 'U003', 'account_number': '100010003', 'customer_name': 'Charlie Brown', 'account_type': 'Savings', 'balance': 200.00, 'status': 'Closed'},
            {'id': 'A004', 'user_id': 'U001', 'account_number': '100010004', 'customer_name': 'Alice Smith', 'account_type': 'Checking', 'balance': 350.50, 'status': 'Active'}
        ]
        for account in accounts_data:
            cursor.execute('''
                INSERT INTO Accounts (id, user_id, account_number, customer_name, account_type, balance, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (account['id'], account['user_id'], account['account_number'], account['customer_name'], account['account_type'], account['balance'], account['status'], now, now))

        # Transactions
        transactions_data = [
            {'id': 'T001', 'account_id': 'A001', 'account_number': '100010001', 'customer_name': 'Alice Smith', 'type': 'Deposit', 'amount': 1000.00, 'date': '2025-07-19T10:00:00Z', 'status': 'Completed', 'description': 'Initial deposit'},
            {'id': 'T002', 'account_id': 'A001', 'account_number': '100010001', 'customer_name': 'Alice Smith', 'type': 'Withdrawal', 'amount': 200.00, 'date': '2025-07-20T11:30:00Z', 'status': 'Completed', 'description': 'ATM withdrawal'},
            {'id': 'T003', 'account_id': 'A002', 'account_number': '100010002', 'customer_name': 'Bob Johnson', 'type': 'Deposit', 'amount': 500.00, 'date': '2025-07-20T14:00:00Z', 'status': 'Completed', 'description': 'Salary deposit'},
            {'id': 'T004', 'account_id': 'A001', 'account_number': '100010001', 'customer_name': 'Alice Smith', 'type': 'Deposit', 'amount': 500.00, 'date': '2025-07-21T09:00:00Z', 'status': 'Completed', 'description': 'Online transfer in'},
            {'id': 'T005', 'account_id': 'A003', 'account_number': '100010003', 'customer_name': 'Charlie Brown', 'type': 'Withdrawal', 'amount': 50.00, 'date': '2025-07-21T10:30:00Z', 'status': 'Completed', 'description': 'Online bill payment'},
            {'id': 'T006', 'account_id': 'A002', 'account_number': '100010002', 'customer_name': 'Bob Johnson', 'type': 'Withdrawal', 'amount': 100.00, 'date': '2025-07-21T12:00:00Z', 'status': 'Completed', 'description': 'Shopping'},
            {'id': 'T007', 'account_id': 'A004', 'account_number': '100010004', 'customer_name': 'Alice Smith', 'type': 'Deposit', 'amount': 200.00, 'date': '2025-07-21T13:00:00Z', 'status': 'Pending', 'description': 'Pending check deposit'},
        ]
        for txn in transactions_data:
            cursor.execute('''
                INSERT INTO Transactions (id, account_id, account_number, customer_name, type, amount, transaction_date, status, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (txn['id'], txn['account_id'], txn['account_number'], txn['customer_name'], txn['type'], txn['amount'], txn['date'], txn['status'], txn['description']))

        # Audit Logs
        audit_logs_data = [
            {'id': 'L001', 'date': '2025-07-20T09:00:00Z', 'admin_user': 'Admin User (U005)', 'action_type': 'User Activated', 'action_details': 'User: Bob Johnson (U002) status changed to Active.'},
            {'id': 'L002', 'date': '2025-07-20T15:00:00Z', 'admin_user': 'Admin User (U005)', 'action_type': 'Account Balance Adjusted', 'action_details': 'Account: 100010001 (Alice Smith), Adjusted by: $5.00, Reason: Error correction.'},
        ]
        for log in audit_logs_data:
            cursor.execute('''
                INSERT INTO AuditLogs (id, timestamp, admin_user, action_type, action_details)
                VALUES (?, ?, ?, ?, ?)
            ''', (log['id'], log['date'], log['admin_user'], log['action_type'], log['action_details']))

        conn.commit()
        print("Mock data inserted successfully.")
    conn.close()

def add_audit_log(admin_user, action_type, action_details):
    """Adds an entry to the audit logs table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    log_id = str(uuid.uuid4()) # Generate a unique ID for the log
    timestamp = datetime.datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO AuditLogs (id, timestamp, admin_user, action_type, action_details)
        VALUES (?, ?, ?, ?, ?)
    ''', (log_id, timestamp, admin_user, action_type, action_details))
    conn.commit()
    conn.close()

def generate_unique_account_number():
    """Generates a unique 9-digit account number."""
    conn = get_db_connection()
    while True:
        # Generate a random 9-digit number
        account_number = str(uuid.uuid4().int)[:9]
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM Accounts WHERE account_number = ?", (account_number,))
        if cursor.fetchone() is None:
            conn.close()
            return account_number

def generate_unique_id(table_name, prefix):
    """Generates a unique ID for a given table with a prefix."""
    conn = get_db_connection()
    while True:
        new_id = f"{prefix}{str(uuid.uuid4())[:7].replace('-', '')}" # Shorten UUID for IDs
        cursor = conn.cursor()
        cursor.execute(f"SELECT 1 FROM {table_name} WHERE id = ?", (new_id,))
        if cursor.fetchone() is None:
            conn.close()
            return new_id

if __name__ == '__main__':
    # This block runs when database.py is executed directly
    init_db()
    print("Database initialized or already exists.")