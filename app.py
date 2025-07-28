from flask import Flask, render_template, request, jsonify
import database
import datetime
import hashlib
import uuid # For generating unique IDs

app = Flask(__name__, template_folder='templates')

# Initialize the database when the app starts
database.init_db()

# Helper function to convert Row objects to dictionaries
def row_to_dict(row):
    return dict(row) if row else None

# --- API Endpoints ---

@app.route('/')
def index():
    """Serves the main admin panel HTML page."""
    return render_template('index.html')

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard_metrics():
    """Fetches dashboard metrics."""
    conn = database.get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM Users WHERE role = 'Customer'")
    total_customers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Accounts")
    total_accounts = cursor.fetchone()[0]

    today = datetime.datetime.now().isoformat().split('T')[0]
    cursor.execute("SELECT COUNT(*) FROM Transactions WHERE transaction_date LIKE ? || '%'", (today,))
    transactions_today = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(amount) FROM Transactions WHERE type LIKE '%Deposit%' AND status = 'Completed'")
    total_deposits = cursor.fetchone()[0] or 0.0

    cursor.execute("SELECT SUM(amount) FROM Transactions WHERE type LIKE '%Withdrawal%' AND status = 'Completed'")
    total_withdrawals = cursor.fetchone()[0] or 0.0

    conn.close()
    return jsonify({
        'totalCustomers': total_customers,
        'totalAccounts': total_accounts,
        'transactionsToday': transactions_today,
        'totalDeposits': total_deposits,
        'totalWithdrawals': total_withdrawals
    })

@app.route('/api/users', methods=['GET'])
def get_users():
    """Retrieves a list of users, with optional search filtering."""
    search_query = request.args.get('search', '').lower()
    conn = database.get_db_connection()
    cursor = conn.cursor()

    if search_query:
        cursor.execute('''
            SELECT id, name, email, role, status, created_at, updated_at
            FROM Users
            WHERE LOWER(name) LIKE ? OR LOWER(email) LIKE ? OR LOWER(id) LIKE ?
            ORDER BY created_at DESC
        ''', (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
    else:
        cursor.execute('SELECT id, name, email, role, status, created_at, updated_at FROM Users ORDER BY created_at DESC')

    users = [row_to_dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(users)

@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    """Retrieves a single user by ID."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, email, role, status FROM Users WHERE id = ?', (user_id,))
    user = row_to_dict(cursor.fetchone())
    conn.close()
    if user:
        return jsonify(user)
    return jsonify({'error': 'User not found'}), 404

@app.route('/api/users', methods=['POST'])
def add_user():
    """Adds a new user to the system."""
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role')
    initial_balance = data.get('initial_balance', 0)

    if not all([name, email, password, role]):
        return jsonify({'error': 'Missing required fields'}), 400

    conn = database.get_db_connection()
    cursor = conn.cursor()

    # Check if email already exists
    cursor.execute("SELECT id FROM Users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Email already exists'}), 409

    user_id = database.generate_unique_id('Users', 'U')
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    now = datetime.datetime.now().isoformat()

    try:
        cursor.execute('''
            INSERT INTO Users (id, name, email, password_hash, role, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, name, email, hashed_password, role, 'Active', now, now))
        conn.commit()

        database.add_audit_log('Admin User (U005)', 'New User Added', f'User ID: {user_id}, Name: {name}, Role: {role}')

        # If new user is a customer, create an account for them
        if role == 'Customer':
            account_id = database.generate_unique_id('Accounts', 'A')
            account_number = database.generate_unique_account_number()
            cursor.execute('''
                INSERT INTO Accounts (id, user_id, account_number, customer_name, account_type, balance, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (account_id, user_id, account_number, name, 'Savings', initial_balance, 'Active', now, now))
            conn.commit()
            database.add_audit_log('Admin User (U005)', 'New Account Created', f'Account No: {account_number} for User ID: {user_id}, Initial Balance: ${initial_balance:.2f}')

            if initial_balance > 0:
                transaction_id = database.generate_unique_id('Transactions', 'T')
                cursor.execute('''
                    INSERT INTO Transactions (id, account_id, account_number, customer_name, type, amount, transaction_date, status, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (transaction_id, account_id, account_number, name, 'Deposit', initial_balance, now, 'Completed', 'Initial account funding'))
                conn.commit()
                database.add_audit_log('Admin User (U005)', 'Transaction Added', f'Initial deposit for Account: {account_number}')

        conn.close()
        return jsonify({'message': f'User "{name}" added successfully.'}), 201
    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    """Updates an existing user's details."""
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role')
    now = datetime.datetime.now().isoformat()

    conn = database.get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT name, email, role FROM Users WHERE id = ?', (user_id,))
    original_user = row_to_dict(cursor.fetchone())
    if not original_user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404

    update_fields = []
    update_values = []
    audit_details = []

    if name and name != original_user['name']:
        update_fields.append('name = ?')
        update_values.append(name)
        audit_details.append(f'Name: {original_user["name"]} -> {name}')
    if email and email != original_user['email']:
        # Check if new email already exists for another user
        cursor.execute("SELECT id FROM Users WHERE email = ? AND id != ?", (email, user_id))
        if cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Email already exists for another user'}), 409
        update_fields.append('email = ?')
        update_values.append(email)
        audit_details.append(f'Email: {original_user["email"]} -> {email}')
    if password:
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        update_fields.append('password_hash = ?')
        update_values.append(hashed_password)
        audit_details.append('Password updated')
    if role and role != original_user['role']:
        update_fields.append('role = ?')
        update_values.append(role)
        audit_details.append(f'Role: {original_user["role"]} -> {role}')

    if not update_fields:
        conn.close()
        return jsonify({'message': 'No changes detected'}), 200

    update_fields.append('updated_at = ?')
    update_values.append(now)
    update_values.append(user_id) # For the WHERE clause

    try:
        cursor.execute(f"UPDATE Users SET {', '.join(update_fields)} WHERE id = ?", update_values)
        conn.commit()

        # Update customer_name in Accounts if user role is Customer and name changed
        if original_user['role'] == 'Customer' and name and name != original_user['name']:
            cursor.execute("UPDATE Accounts SET customer_name = ? WHERE user_id = ?", (name, user_id))
            conn.commit()
            database.add_audit_log('Admin User (U005)', 'Account Name Updated', f'Customer name updated in accounts for User ID: {user_id}.')

        # Handle role change from Customer to non-Customer (delete associated accounts)
        if original_user['role'] == 'Customer' and role != 'Customer':
            cursor.execute("DELETE FROM Accounts WHERE user_id = ?", (user_id,))
            conn.commit()
            database.add_audit_log('Admin User (U005)', 'Account(s) Removed', f'Removed accounts for User ID: {user_id} as role changed from Customer.')


        database.add_audit_log('Admin User (U005)', 'User Edited', f'User ID: {user_id}, Details: {", ".join(audit_details)}')
        conn.close()
        return jsonify({'message': f'User "{name}" updated successfully.'}), 200
    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Deletes a user and their associated accounts and transactions."""
    conn = database.get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT name, role FROM Users WHERE id = ?', (user_id,))
    user = row_to_dict(cursor.fetchone())
    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404

    try:
        # SQLite's ON DELETE CASCADE handles deleting accounts and transactions
        # if foreign key constraints are set up correctly.
        cursor.execute('DELETE FROM Users WHERE id = ?', (user_id,))
        conn.commit()
        database.add_audit_log('Admin User (U005)', 'User Deleted', f'User ID: {user_id}, Name: {user["name"]} and associated accounts/transactions deleted.')
        conn.close()
        return jsonify({'message': f'User "{user["name"]}" and associated data deleted.'}), 200
    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/users/<user_id>/toggle_status', methods=['PUT'])
def toggle_user_status(user_id):
    """Toggles a user's active/inactive status."""
    data = request.get_json()
    new_status = data.get('status')
    if new_status not in ['Active', 'Inactive']:
        return jsonify({'error': 'Invalid status provided'}), 400

    conn = database.get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT name, status FROM Users WHERE id = ?', (user_id,))
    user = row_to_dict(cursor.fetchone())
    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404

    if user['status'] == new_status:
        conn.close()
        return jsonify({'message': f'User is already {new_status}.'}), 200

    now = datetime.datetime.now().isoformat()
    try:
        cursor.execute('UPDATE Users SET status = ?, updated_at = ? WHERE id = ?', (new_status, now, user_id))
        conn.commit()
        database.add_audit_log('Admin User (U005)', f'User {new_status}d', f'User ID: {user_id}, Name: {user["name"]} status changed to {new_status}.')
        conn.close()
        return jsonify({'message': f'User {user_id} status changed to {new_status}.'}), 200
    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """Retrieves a list of bank accounts, with optional search filtering."""
    search_query = request.args.get('search', '').lower()
    conn = database.get_db_connection()
    cursor = conn.cursor()

    if search_query:
        cursor.execute('''
            SELECT id, user_id, account_number, customer_name, account_type, balance, status, created_at, updated_at
            FROM Accounts
            WHERE LOWER(account_number) LIKE ? OR LOWER(customer_name) LIKE ?
            ORDER BY created_at DESC
        ''', (f'%{search_query}%', f'%{search_query}%'))
    else:
        cursor.execute('SELECT id, user_id, account_number, customer_name, account_type, balance, status, created_at, updated_at FROM Accounts ORDER BY created_at DESC')

    accounts = [row_to_dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(accounts)

@app.route('/api/accounts/<account_id>', methods=['GET'])
def get_account(account_id):
    """Retrieves a single account by ID."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, user_id, account_number, customer_name, account_type, balance, status FROM Accounts WHERE id = ?', (account_id,))
    account = row_to_dict(cursor.fetchone())
    conn.close()
    if account:
        return jsonify(account)
    return jsonify({'error': 'Account not found'}), 404

@app.route('/api/accounts/<account_id>/adjust_balance', methods=['PUT'])
def adjust_account_balance(account_id):
    """Adjusts an account's balance and logs the transaction and audit."""
    data = request.get_json()
    amount = data.get('amount')
    reason = data.get('reason')

    if amount is None or not isinstance(amount, (int, float)) or not reason:
        return jsonify({'error': 'Invalid amount or missing reason'}), 400

    conn = database.get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT balance, account_number, customer_name FROM Accounts WHERE id = ?', (account_id,))
    account = row_to_dict(cursor.fetchone())
    if not account:
        conn.close()
        return jsonify({'error': 'Account not found'}), 404

    old_balance = account['balance']
    new_balance = old_balance + amount
    now = datetime.datetime.now().isoformat()

    try:
        cursor.execute('UPDATE Accounts SET balance = ?, updated_at = ? WHERE id = ?', (new_balance, now, account_id))
        conn.commit()

        # Add a transaction for this adjustment
        transaction_type = 'Deposit (Adjustment)' if amount >= 0 else 'Withdrawal (Adjustment)'
        transaction_id = database.generate_unique_id('Transactions', 'T')
        cursor.execute('''
            INSERT INTO Transactions (id, account_id, account_number, customer_name, type, amount, transaction_date, status, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (transaction_id, account_id, account['account_number'], account['customer_name'], transaction_type, abs(amount), now, 'Completed', f'Admin adjustment: {reason}'))
        conn.commit()

        database.add_audit_log('Admin User (U005)', 'Account Balance Adjusted',
                               f'Account: {account["account_number"]} (ID: {account_id}), Adjusted by: ${amount:.2f}, Old Balance: ${old_balance:.2f}, New Balance: ${new_balance:.2f}, Reason: {reason}')
        conn.close()
        return jsonify({'message': f'Balance for Account {account["account_number"]} adjusted by ${amount:.2f}. New Balance: ${new_balance:.2f}.'}), 200
    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Database error: {str(e)}'}), 500


@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    """Retrieves a list of transactions with various filters."""
    conn = database.get_db_connection()
    cursor = conn.cursor()

    query = "SELECT id, account_id, account_number, customer_name, type, amount, transaction_date, status, description FROM Transactions WHERE 1=1"
    params = []

    account_id = request.args.get('account_id')
    if account_id:
        query += " AND account_id = ?"
        params.append(account_id)

    transaction_type = request.args.get('type')
    if transaction_type:
        query += " AND type = ?"
        params.append(transaction_type)

    start_date_str = request.args.get('start_date')
    if start_date_str:
        # SQLite stores dates as ISO strings, so direct comparison works
        query += " AND transaction_date >= ?"
        params.append(start_date_str)

    end_date_str = request.args.get('end_date')
    if end_date_str:
        # For end date, include up to the end of the day
        end_date_obj = datetime.datetime.strptime(end_date_str, '%Y-%m-%d') + datetime.timedelta(days=1) - datetime.timedelta(microseconds=1)
        query += " AND transaction_date <= ?"
        params.append(end_date_obj.isoformat())

    search_query = request.args.get('search', '').lower()
    if search_query:
        query += " AND (LOWER(account_number) LIKE ? OR LOWER(customer_name) LIKE ? OR LOWER(description) LIKE ?)"
        params.append(f'%{search_query}%')
        params.append(f'%{search_query}%')
        params.append(f'%{search_query}%')

    query += " ORDER BY transaction_date DESC"

    cursor.execute(query, params)
    transactions = [row_to_dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(transactions)

@app.route('/api/transactions/<transaction_id>', methods=['GET'])
def get_transaction(transaction_id):
    """Retrieves a single transaction by ID."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, account_id, account_number, customer_name, type, amount, transaction_date, status, description FROM Transactions WHERE id = ?', (transaction_id,))
    transaction = row_to_dict(cursor.fetchone())
    conn.close()
    if transaction:
        return jsonify(transaction)
    return jsonify({'error': 'Transaction not found'}), 404

@app.route('/api/transactions/<transaction_id>/reverse', methods=['PUT'])
def reverse_transaction(transaction_id):
    """Reverses a completed transaction."""
    conn = database.get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT id, account_id, account_number, customer_name, type, amount, transaction_date, status, description FROM Transactions WHERE id = ?', (transaction_id,))
    transaction = row_to_dict(cursor.fetchone())

    if not transaction:
        conn.close()
        return jsonify({'error': 'Transaction not found'}), 404
    if transaction['status'] != 'Completed':
        conn.close()
        return jsonify({'error': 'Only "Completed" transactions can be reversed.'}), 400
    if 'Reversal' in transaction['type'] or 'Adjustment' in transaction['type']:
        conn.close()
        return jsonify({'error': 'Cannot reverse a reversal or adjustment transaction.'}), 400

    cursor.execute('SELECT balance FROM Accounts WHERE id = ?', (transaction['account_id'],))
    account = row_to_dict(cursor.fetchone())
    if not account:
        conn.close()
        return jsonify({'error': 'Associated account not found.'}), 404

    old_balance = account['balance']
    reversal_amount = transaction['amount']
    reversal_type = ''
    new_balance = old_balance

    if 'Deposit' in transaction['type']:
        new_balance -= reversal_amount
        reversal_type = 'Withdrawal (Reversal)'
    elif 'Withdrawal' in transaction['type']:
        new_balance += reversal_amount
        reversal_type = 'Deposit (Reversal)'
    elif 'Transfer' in transaction['type']:
        # For simplicity, assuming this is the sending account and reversing the outflow
        new_balance += reversal_amount
        reversal_type = 'Deposit (Transfer Reversal)'
    else:
        conn.close()
        return jsonify({'error': 'Cannot determine reversal type for this transaction.'}), 400

    now = datetime.datetime.now().isoformat()
    try:
        # Update original transaction status
        cursor.execute('UPDATE Transactions SET status = ?, description = ? WHERE id = ?',
                       ('Reversed', transaction['description'] + ' (Reversed by Admin)', transaction_id))
        conn.commit()

        # Update account balance
        cursor.execute('UPDATE Accounts SET balance = ?, updated_at = ? WHERE id = ?',
                       (new_balance, now, transaction['account_id']))
        conn.commit()

        # Add a new transaction for the reversal
        new_txn_id = database.generate_unique_id('Transactions', 'T')
        cursor.execute('''
            INSERT INTO Transactions (id, account_id, account_number, customer_name, type, amount, transaction_date, status, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (new_txn_id, transaction['account_id'], transaction['account_number'], transaction['customer_name'],
              reversal_type, reversal_amount, now, 'Completed', f'Reversal of TXN {transaction_id}: {transaction["description"]}'))
        conn.commit()

        database.add_audit_log('Admin User (U005)', 'Transaction Reversed',
                               f'Transaction ID: {transaction_id} (Account: {transaction["account_number"]}), Amount: ${reversal_amount:.2f}, Type: {transaction["type"]}, Account balance changed from ${old_balance:.2f} to ${new_balance:.2f}.')
        conn.close()
        return jsonify({'message': f'Transaction {transaction_id} successfully reversed. Account {transaction["account_number"]} balance updated to ${new_balance:.2f}.'}), 200
    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/audit_logs', methods=['GET'])
def get_audit_logs():
    """Retrieves a list of audit logs with optional search filtering."""
    search_query = request.args.get('search', '').lower()
    conn = database.get_db_connection()
    cursor = conn.cursor()

    if search_query:
        cursor.execute('''
            SELECT id, timestamp, admin_user, action_type, action_details
            FROM AuditLogs
            WHERE LOWER(action_type) LIKE ? OR LOWER(admin_user) LIKE ? OR LOWER(action_details) LIKE ?
            ORDER BY timestamp DESC
        ''', (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
    else:
        cursor.execute('SELECT id, timestamp, admin_user, action_type, action_details FROM AuditLogs ORDER BY timestamp DESC')

    logs = [row_to_dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(logs)

if __name__ == '__main__':
    app.run(debug=True) # debug=True allows automatic reloading on code changes and provides a debugger