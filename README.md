# Bank Transactions Management System

This is a simple web-based Bank Transactions Management System designed to demonstrate core DBMS concepts and full-stack development. It provides an administrative panel to manage users, bank accounts, transactions, and audit logs.

## Features

* **Dashboard:** Overview of key banking metrics (total customers, accounts, daily transactions, deposits, withdrawals).
* **User Management:** Add, edit, deactivate/activate, and delete users (customers, staff, admins). Automatically creates an account for new customers.
* **Account Management:** View all bank accounts, adjust account balances (with audit trail), and view detailed transaction history for each account.
* **Transaction History:** Comprehensive list of all transactions with filtering options (by type, date range, account number, customer name).
* **Transaction Reversal:** Ability to reverse completed transactions, which automatically adjusts account balances and logs the reversal.
* **Audit Logs:** A record of all administrative actions performed within the system.
* **Responsive Design:** User interface built with Tailwind CSS, adapting to different screen sizes.

## Technologies Used

* **Backend:** Python 3.x with Flask
* **Database:** SQLite3
* **Frontend:** HTML, JavaScript
* **Styling:** Tailwind CSS

## Setup and Execution Instructions

Follow these steps to get the Bank Transactions Management System up and running on your local machine.

### 1. Clone the Repository

First, clone this repository to your local machine using Git:

```bash
git clone [https://github.com/bhuvanesh-bharath/BankSystemProject.git](https://github.com/bhuvanesh-bharath/BankSystemProject.git)
cd BankSystemProject
2. Create a Python Virtual Environment (Recommended)
It's good practice to use a virtual environment to manage dependencies for your Python projects.

Bash

python -m venv venv
3. Activate the Virtual Environment
On Windows:

Bash

.\venv\Scripts\activate
On macOS/Linux:

Bash

source venv/bin/activate
4. Install Dependencies
Once the virtual environment is active, install the required Python packages (Flask) using pip:

Bash

pip install Flask
5. Initialize the Database
The project uses an SQLite database (bank.db). This step will create the database file and populate it with some initial mock data if it doesn't already exist.

Bash

python database.py
You should see output indicating that mock data is being inserted.

6. Run the Flask Application
Now you can start the Flask development server:

Bash

python app.py
You should see output in your terminal indicating that the Flask app is running, typically on http://127.0.0.1:5000.

7. Access the Application
Open your web browser and navigate to the address displayed in your terminal, usually:

http://127.0.0.1:5000

You should now see the Bank Admin Panel dashboard.
