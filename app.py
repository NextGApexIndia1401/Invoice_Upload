from flask import Flask, request, redirect, url_for, render_template_string, jsonify
import pyodbc
from datetime import datetime
import logging
from azure.storage.blob import BlobServiceClient
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# SQL Server Connection Configuration
def get_db_connection():
    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=103.7.181.119;'
        'DATABASE=SimplyAmplify;'
        'UID=Yashs;'
        'PWD=yashshinde$0310$'
    )
    return conn

# Login Route
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['userName']
        password = request.form['password']

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            try:
                # Check if user exists and password matches
                cursor.execute('SELECT userID FROM MobiUser WHERE userName = ? AND password = ?', (username, password))
                user = cursor.fetchone()

                if user:
                    # Store user ID in session or pass it as a parameter
                    return redirect(url_for('dashboard', user_id=user[0]))
                else:
                    return "Invalid credentials. Please try again."
            finally:
                # Ensure connection is closed
                if conn is not None:
                    try:
                        conn.close()
                    except Exception as close_error:
                        logger.error(f"Error closing database connection: {str(close_error)}")

        except pyodbc.Error as db_error:
            # Specific database-related error handling
            logger.error(f"Database error: {str(db_error)}")
            return f"Database error: {str(db_error)}", 500
        except Exception as e:
            # Catch-all for any other unexpected errors
            logger.error(f"Unexpected error in login route: {str(e)}", exc_info=True)
            return f"An unexpected error occurred: {str(e)}", 500

    return render_template_string(login_page)

# Dashboard (to show after successful login)
@app.route('/dashboard')
def dashboard():
    conn = None
    try:
        # Retrieve user ID from query parameter
        user_id = request.args.get('user_id')
        
        # Validate user ID
        if not user_id:
            logger.error("No user ID found in request")
            return "User ID is required", 400

        # Log the user ID for debugging
        logger.info(f"Dashboard accessed for user ID: {user_id}")
        
        # Establish database connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get the current month
        current_month = datetime.now().strftime("%m")
        
        # First, verify if the user exists
        cursor.execute('SELECT userName FROM MobiUser WHERE userID = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            logger.error(f"User with ID {user_id} not found in database")
            return f"User not found", 404

        # Fetch routes for the current user and month
        cursor.execute('''
            SELECT DISTINCT routeName 
            FROM mobiRouteScheduleList 
            WHERE userID = ? AND MONTH = ?
        ''', (user_id, current_month))
        routes = cursor.fetchall()
        
        # Log the number of routes found
        logger.info(f"Found {len(routes)} routes for user ID {user_id}")
        
        # Prepare route dropdown HTML
        if not routes:
            route_options = '<option value="">No routes available</option>'
            logger.warning(f"No routes found for user ID {user_id} in month {current_month}")
        else:
            route_options = ''.join([f'<option value="{route[0]}">{route[0]}</option>' for route in routes])

        dashboard_page = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Invoice Upload Dashboard</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
            <style>
                * {{
                    box-sizing: border-box;
                    -webkit-tap-highlight-color: transparent;
                }}
                body {{ 
                    font-family: Arial, sans-serif; 
                    margin: 0; 
                    padding: 16px;
                    background-color: #f4f4f9;
                    line-height: 1.6;
                }}
                .container {{
                    width: 100%;
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 16px;
                    border-radius: 8px;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                }}
                h1 {{ 
                    color: #333; 
                    text-align: center; 
                    font-size: 24px;
                    margin: 0 0 24px 0;
                }}
                label {{ 
                    display: block; 
                    margin: 16px 0 8px; 
                    font-weight: bold;
                    color: #333;
                }}
                select, input {{ 
                    width: 100%; 
                    padding: 12px;
                    margin-bottom: 8px; 
                    border: 1px solid #ddd; 
                    border-radius: 8px;
                    font-size: 16px;
                    background-color: #fff;
                }}
                select {{
                    appearance: none;
                    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%23333' viewBox='0 0 16 16'%3E%3Cpath d='M8 11L3 6h10z'/%3E%3C/svg%3E");
                    background-repeat: no-repeat;
                    background-position: right 12px center;
                    padding-right: 36px;
                }}
                .hidden {{ 
                    display: none; 
                }}
                .product-row {{ 
                    display: flex;
                    flex-direction: column;
                    margin-bottom: 16px;
                    padding: 12px;
                    background: #f8f9fa;
                    border-radius: 8px;
                }}
                .product-row label {{
                    margin: 0 0 8px 0;
                }}
                .product-row input {{ 
                    margin: 0;
                    width: 100%;
                }}
                #productContainer {{ 
                    max-height: none;
                    overflow-y: visible;
                    margin: 16px 0;
                }}
                .btn {{
                    width: 100%;
                    background-color: #007bff;
                    color: white;
                    border: none;
                    padding: 16px;
                    border-radius: 8px;
                    cursor: pointer;
                    font-size: 16px;
                    font-weight: bold;
                    margin-top: 24px;
                    transition: background-color 0.2s;
                }}
                .btn:hover, .btn:active {{
                    background-color: #0056b3;
                }}
                .product-quantity {{
                    margin: 16px 0;
                    padding: 16px;
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    background: #f8f9fa;
                }}
                .product-quantity label {{
                    display: block;
                    margin: 0 0 8px 0;
                }}
                .product-quantity input {{
                    width: 100%;
                }}
                @media (max-width: 480px) {{
                    body {{
                        padding: 8px;
                    }}
                    .container {{
                        padding: 12px;
                    }}
                    h1 {{
                        font-size: 20px;
                        margin-bottom: 16px;
                    }}
                    select, input {{
                        padding: 10px;
                    }}
                    .product-quantity {{
                        padding: 12px;
                    }}
                }}
                #uploadProgress {{
                    width: 100%;
                    height: 4px;
                    background-color: #f0f0f0;
                    border-radius: 4px;
                    margin-top: 16px;
                    display: none;
                }}
                #progressBar {{
                    width: 0%;
                    height: 100%;
                    background-color: #007bff;
                    border-radius: 4px;
                    transition: width 0.3s ease;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Invoice Upload Dashboard</h1>
                <form id="invoiceForm" method="POST" action="/upload_invoice" enctype="multipart/form-data">
                    <input type="hidden" name="user_id" value="{user_id}">
                    
                    <label for="route">Select Route:</label>
                    <select id="route" name="route" required>
                        <option value="">Select a route</option>
                        {route_options}
                    </select>

                    <label for="outlet">Select Outlet:</label>
                    <select id="outlet" name="outlet_name" required>
                        <option value="">Select an outlet</option>
                    </select>

                    <label for="invoice_date">Invoice Date:</label>
                    <input type="date" id="invoice_date" name="invoice_date" required>

                    <label for="invoice_number">Invoice Number:</label>
                    <input type="text" id="invoice_number" name="invoice_number" required>

                    <label for="invoice_file">Upload Invoice:</label>
                    <input type="file" id="invoice_file" name="invoice_file" accept=".pdf,.jpg,.jpeg,.png">

                    <div class="product-quantities">
                        <h3>Product Quantities</h3>
                        <div class="product-quantity">
                            <label for="SENSODENT_K_FR_75GM">SENSODENT K FR 75GM:</label>
                            <input type="number" id="SENSODENT_K_FR_75GM" name="SENSODENT_K_FR_75GM" value="0" min="0">
                        </div>
                        <div class="product-quantity">
                            <label for="SENSODENT_KF_CP_75GM">SENSODENT KF CP 75GM:</label>
                            <input type="number" id="SENSODENT_KF_CP_75GM" name="SENSODENT_KF_CP_75GM" value="0" min="0">
                        </div>
                        <div class="product-quantity">
                            <label for="SENSODENT_K_FR_125GM">SENSODENT K FR 125GM:</label>
                            <input type="number" id="SENSODENT_K_FR_125GM" name="SENSODENT_K_FR_125GM" value="0" min="0">
                        </div>
                        <div class="product-quantity">
                            <label for="SENSODENT_KF_CP_125GM">SENSODENT KF CP 125GM:</label>
                            <input type="number" id="SENSODENT_KF_CP_125GM" name="SENSODENT_KF_CP_125GM" value="0" min="0">
                        </div>
                        <div class="product-quantity">
                            <label for="SENSODENT_KF_CP_15G">SENSODENT KF CP 15G:</label>
                            <input type="number" id="SENSODENT_KF_CP_15G" name="SENSODENT_KF_CP_15G" value="0" min="0">
                        </div>
                        <div class="product-quantity">
                            <label for="SENSODENT_K_FR_15G">SENSODENT K FR 15G:</label>
                            <input type="number" id="SENSODENT_K_FR_15G" name="SENSODENT_K_FR_15G" value="0" min="0">
                        </div>
                        <div class="product-quantity">
                            <label for="KIDODENT_CAVITY_SHIELD">KIDODENT CAVITY SHIELD:</label>
                            <input type="number" id="KIDODENT_CAVITY_SHIELD" name="KIDODENT_CAVITY_SHIELD" value="0" min="0">
                        </div>
                    </div>

                    <button type="submit" class="btn">Upload Invoice</button>
                </form>
            </div>

            <script>
                document.getElementById('route').addEventListener('change', function() {{
                    const routeName = this.value;
                    const outletSelect = document.getElementById('outlet');
                    
                    // Clear current options
                    outletSelect.innerHTML = '<option value="">Select an outlet</option>';
                    
                    if (routeName) {{
                        fetch('/get_outlets?routeName=' + encodeURIComponent(routeName))
                            .then(response => response.json())
                            .then(outlets => {{
                                outlets.forEach(outlet => {{
                                    const option = document.createElement('option');
                                    option.value = outlet;
                                    option.textContent = outlet;
                                    outletSelect.appendChild(option);
                                }});
                            }});
                    }}
                }});

                document.getElementById('invoiceForm').addEventListener('submit', function(e) {{
                    e.preventDefault();
                    
                    const formData = new FormData(this);
                    
                    fetch('/upload_invoice', {{
                        method: 'POST',
                        body: formData
                    }})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            alert('Invoice uploaded successfully!');
                            this.reset();
                        }} else {{
                            alert('Error uploading invoice: ' + data.message);
                        }}
                    }})
                    .catch(error => {{
                        alert('Error uploading invoice: ' + error.message);
                    }});
                }});
            </script>
        </body>
        </html>
        '''

        return dashboard_page

    except pyodbc.Error as db_error:
        # Specific database-related error handling
        logger.error(f"Database error: {str(db_error)}")
        return f"Database error: {str(db_error)}", 500
    except Exception as e:
        # Catch-all for any other unexpected errors
        logger.error(f"Unexpected error in dashboard route: {str(e)}", exc_info=True)
        return f"An unexpected error occurred: {str(e)}", 500
    finally:
        # Ensure connection is closed
        if conn is not None:
            try:
                conn.close()
            except Exception as close_error:
                logger.error(f"Error closing database connection: {str(close_error)}")

# New route to fetch outlets based on route name
@app.route('/get_outlets')
def get_outlets():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        route_name = request.args.get('routeName')

        # Fetch outlets matching the route name
        cursor.execute('''
            SELECT outletName 
            FROM apOutlet 
            WHERE clientRoute = ?
        ''', (route_name,))

        outlets = [row[0] for row in cursor.fetchall()]

        return jsonify(outlets)

    except pyodbc.Error as db_error:
        # Specific database-related error handling
        logger.error(f"Database error: {str(db_error)}")
        return f"Database error: {str(db_error)}", 500
    except Exception as e:
        # Catch-all for any other unexpected errors
        logger.error(f"Unexpected error in get_outlets route: {str(e)}", exc_info=True)
        return f"An unexpected error occurred: {str(e)}", 500
    finally:
        # Ensure connection is closed
        if conn is not None:
            try:
                conn.close()
            except Exception as close_error:
                logger.error(f"Error closing database connection: {str(close_error)}")

# New route to fetch products
@app.route('/get_products')
def get_products():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Fetch products for client 79, not deleted
            cursor.execute('''
                SELECT DISTINCT productDescription 
                FROM apProduct 
                WHERE clientID = 79 AND deleted = 0
            ''')

            products = [row[0] for row in cursor.fetchall()]

            return jsonify(products)

        except pyodbc.Error as db_error:
            # Specific database-related error handling
            logger.error(f"Database error: {str(db_error)}")
            return f"Database error: {str(db_error)}", 500
        except Exception as e:
            # Catch-all for any other unexpected errors
            logger.error(f"Unexpected error in get_products route: {str(e)}", exc_info=True)
            return f"An unexpected error occurred: {str(e)}", 500
    finally:
        # Ensure connection is closed
        if conn is not None:
            try:
                conn.close()
            except Exception as close_error:
                logger.error(f"Error closing database connection: {str(close_error)}")

# Route to handle invoice upload
@app.route('/upload_invoice', methods=['POST'])
def upload_invoice():
    conn = None
    try:
        # Azure Storage connection string
        connection_string = "DefaultEndpointsProtocol=https;AccountName=ngstore;AccountKey=0kOBlNdR/pnuhQazkYliSE8BOyxm/KelSLaOuvGuMfJWRlQLUH2ZCsDd34skmg2dVq11QxODu12s+AStmuHgAQ==;EndpointSuffix=core.windows.net"
        container_name = "invoiceupload"

        # Create the BlobServiceClient object
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)

        # Get form data
        user_id = request.form.get('user_id')
        outlet_name = request.form.get('outlet_name')
        invoice_date = request.form.get('invoice_date')
        invoice_number = request.form.get('invoice_number')
        invoice_file = request.files.get('invoice_file')
        
        # Get quantities for each product
        sensodent_k_fr_75gm = request.form.get('SENSODENT_K_FR_75GM', 0)
        sensodent_kf_cp_75gm = request.form.get('SENSODENT_KF_CP_75GM', 0)
        sensodent_k_fr_125gm = request.form.get('SENSODENT_K_FR_125GM', 0)
        sensodent_kf_cp_125gm = request.form.get('SENSODENT_KF_CP_125GM', 0)
        sensodent_kf_cp_15g = request.form.get('SENSODENT_KF_CP_15G', 0)
        sensodent_k_fr_15g = request.form.get('SENSODENT_K_FR_15G', 0)
        kidodent_cavity_shield = request.form.get('KIDODENT_CAVITY_SHIELD', 0)

        if not invoice_file:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400

        # Get outlet code from apOutlet table
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT outletCode FROM apOutlet WHERE outletName = ?', (outlet_name,))
        outlet_result = cursor.fetchone()
        outlet_code = outlet_result[0] if outlet_result else None

        if not outlet_code:
            return jsonify({'success': False, 'message': 'Outlet code not found'}), 400

        # Generate filename in the format outletcode_date
        current_date = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_extension = os.path.splitext(str(invoice_file.filename))[1] or '.pdf'  # Ensure string and default to .pdf
        azure_filename = f"{outlet_code}_{current_date}{file_extension}"

        # Upload file to Azure Blob Storage
        blob_client = container_client.get_blob_client(azure_filename)
        file_contents = invoice_file.read()
        blob_client.upload_blob(file_contents, overwrite=True)

        # Database operations
        cursor.execute('''
            INSERT INTO InvoiceDetails (
                UserID, OutletCode, OutletName, InvoiceAvailable, DisplayType,
                InvoiceDate, InvoiceNumber, InvoiceDocument,
                SENSODENT_K_FR_75GM, SENSODENT_KF_CP_75GM, SENSODENT_K_FR_125GM,
                SENSODENT_KF_CP_125GM, SENSODENT_KF_CP_15G, SENSODENT_K_FR_15G,
                KIDODENT_CAVITY_SHIELD
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, outlet_code, outlet_name, True, 'Standard',
            invoice_date, invoice_number, azure_filename,
            sensodent_k_fr_75gm, sensodent_kf_cp_75gm, sensodent_k_fr_125gm,
            sensodent_kf_cp_125gm, sensodent_kf_cp_15g, sensodent_k_fr_15g,
            kidodent_cavity_shield
        ))

        conn.commit()
        return jsonify({'success': True, 'message': 'Invoice uploaded successfully'})

    except Exception as e:
        logger.error(f"Error uploading invoice: {str(e)}")
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'message': f'Error uploading invoice: {str(e)}'}), 500
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception as close_error:
                logger.error(f"Error closing database connection: {str(close_error)}")

# Security headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# Login Page Template with Mobile-Responsive Design
login_page = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f4f4f9;
        }

        .container {
            max-width: 400px;
            margin: 50px auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }

        h2 {
            text-align: center;
            color: #333;
        }

        label {
            font-size: 14px;
            color: #333;
            display: block;
            margin: 10px 0 5px;
        }

        input[type="text"], input[type="password"] {
            width: 100%;
            padding: 12px;
            margin: 8px 0 15px;
            border: 1px solid #ccc;
            border-radius: 5px;
            box-sizing: border-box;
            font-size: 16px;
        }

        button {
            width: 100%;
            padding: 14px;
            background-color: #007bff;
            color: white;
            font-size: 16px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.3s;
        }

        button:hover {
            background-color: #0056b3;
        }

        @media (max-width: 600px) {
            .container {
                width: 90%;
                padding: 20px;
            }
        }
    </style>
</head>
<body>

    <div class="container">
        <h2>Login</h2>
        <form method="post">
            <label for="UserName">User ID</label>
            <input type="text" id="userName" name="userName" required>

            <label for="password">Password</label>
            <input type="password" id="password" name="password" required>

            <button type="submit">Login</button>
        </form>
    </div>

</body>
</html>
'''

if __name__ == '__main__':
    # Get the local IP address
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print(f"\nAccess the application at:")
    print(f"Local:   http://127.0.0.1:5000")
    print(f"Network: http://{local_ip}:5000\n")
    
    # Run the app on all network interfaces
    app.run(host='0.0.0.0', port=5000, debug=True)
