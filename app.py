from flask import Flask, request, redirect, url_for, render_template_string, jsonify
import os
import logging
from dotenv import load_dotenv
import pymssql
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import pyodbc
from azure.storage.blob import BlobServiceClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Database Connection Configuration
def get_db_connection():
    try:
        # Retrieve database credentials from environment variables
        server = os.getenv('DB_SERVER')
        database = os.getenv('DB_DATABASE')
        username = os.getenv('DB_USERNAME')
        password = os.getenv('DB_PASSWORD')

        # Create SQLAlchemy engine
        connection_string = f'mssql+pymssql://{username}:{password}@{server}/{database}'
        engine = create_engine(connection_string, echo=False)
        
        # Create a session factory
        Session = sessionmaker(bind=engine)
        return Session()

    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        raise

# Login Route
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['userName']
        password = request.form['password']

        try:
            # Use SQLAlchemy session for database operations
            session = get_db_connection()
            
            # Execute query using SQLAlchemy
            query = text('SELECT userID FROM MobiUser WHERE userName = :username AND password = :password')
            result = session.execute(query, {'username': username, 'password': password}).fetchone()
            
            # Close the session
            session.close()

            if result:
                # Successful login
                return redirect(url_for('dashboard', user_id=result[0]))
            else:
                # Invalid credentials
                return render_template_string(login_page, error='Invalid username or password')

        except Exception as e:
            logger.error(f"Login query error: {str(e)}")
            return render_template_string(login_page, error='Database query error')

    return render_template_string(login_page)

# Dashboard (to show after successful login)
@app.route('/dashboard')
def dashboard():
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
        session = get_db_connection()

        # Get the current month
        current_month = datetime.now().strftime("%m")
        
        # First, verify if the user exists
        query = text('SELECT userName FROM MobiUser WHERE userID = :user_id')
        user = session.execute(query, {'user_id': user_id}).fetchone()
        
        if not user:
            logger.error(f"User with ID {user_id} not found in database")
            return f"User not found", 404

        # Fetch routes for the current user and month
        query = text('''
            SELECT DISTINCT routeName 
            FROM mobiRouteScheduleList 
            WHERE userID = :user_id AND MONTH = :current_month
        ''')
        routes = session.execute(query, {'user_id': user_id, 'current_month': current_month}).fetchall()
        
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
                #successMessage {{
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background-color: #4CAF50;  /* Vibrant Green */
                    color: white;
                    padding: 15px 25px;
                    border-radius: 5px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    z-index: 1000;
                    display: none;
                    animation: slideIn 0.5s ease-out;
                }}
                @keyframes slideIn {{
                    from {{
                        transform: translateX(100%);
                        opacity: 0;
                    }}
                    to {{
                        transform: translateX(0);
                        opacity: 1;
                    }}
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

            <div id="successMessage"></div>

            <script>
                // Function to show green success message
                function showSuccessMessage(message) {{
                    const messageContainer = document.getElementById('successMessage');
                    messageContainer.textContent = message;
                    messageContainer.style.display = 'block';
                    
                    // Automatically hide after 3 seconds
                    setTimeout(() => {{
                        messageContainer.style.display = 'none';
                    }}, 3000);
                }}

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
                            // Show green success message
                            showSuccessMessage('Invoice uploaded successfully!');
                            
                            // Reset the form
                            this.reset();
                        }} else {{
                            // Show error message
                            showSuccessMessage(data.message || 'Error uploading invoice');
                        }}
                    }})
                    .catch(error => {{
                        // Show error message for network or unexpected errors
                        showSuccessMessage('Failed to upload invoice. Please try again.');
                        console.error('Error:', error);
                    }});
                }});
            </script>
        </body>
        </html>
        '''

        # Close the session
        session.close()

        return dashboard_page

    except Exception as e:
        logger.error(f"Unexpected error in dashboard route: {str(e)}", exc_info=True)
        return f"An unexpected error occurred: {str(e)}", 500

# New route to fetch outlets based on route name
@app.route('/get_outlets')
def get_outlets():
    try:
        # Establish database connection
        session = get_db_connection()

        route_name = request.args.get('routeName')

        # Fetch outlets matching the route name
        query = text('''
            SELECT outletName 
            FROM apOutlet 
            WHERE clientRoute = :route_name
        ''')
        outlets = session.execute(query, {'route_name': route_name}).fetchall()

        # Close the session
        session.close()

        return jsonify([outlet[0] for outlet in outlets])

    except Exception as e:
        logger.error(f"Unexpected error in get_outlets route: {str(e)}", exc_info=True)
        return f"An unexpected error occurred: {str(e)}", 500

# New route to fetch products
@app.route('/get_products')
def get_products():
    try:
        # Establish database connection
        session = get_db_connection()

        try:
            # Fetch products for client 79, not deleted
            query = text('''
                SELECT DISTINCT productDescription 
                FROM apProduct 
                WHERE clientID = 79 AND deleted = 0
            ''')
            products = session.execute(query).fetchall()

            # Close the session
            session.close()

            return jsonify([product[0] for product in products])

        except Exception as e:
            logger.error(f"Unexpected error in get_products route: {str(e)}", exc_info=True)
            return f"An unexpected error occurred: {str(e)}", 500

    except Exception as e:
        logger.error(f"Unexpected error in get_products route: {str(e)}", exc_info=True)
        return f"An unexpected error occurred: {str(e)}", 500

# Route to handle invoice upload
@app.route('/upload_invoice', methods=['POST'])
def upload_invoice():
    try:
        # Azure Storage connection string
        connection_string = "DefaultEndpointsProtocol=https;AccountName=ngstore;AccountKey=0kOBlNdR/pnuhQazkYliSE8BOyxm/KelSLaOuvGuMfJWRlQLUH2ZCsDd34skmg2dVq11QxODu12s+AStmuHgAQ==;EndpointSuffix=core.windows.net"
        container_name = "invoiceupload"

        # Create the BlobServiceClient object
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)

        # Get form data
        user_id = request.form.get('user_id')
        invoice_file = request.files.get('invoice_file')
        if not invoice_file or invoice_file.filename == '':
            logger.error("No file uploaded")
            return jsonify({'success': False, 'message': 'No invoice file uploaded'}), 400

        outlet_name = request.form.get('outlet_name')
        if not outlet_name:
            logger.error("No outlet name provided")
            return jsonify({'success': False, 'message': 'Outlet name is required'}), 400

        invoice_date = request.form.get('invoice_date')
        invoice_number = request.form.get('invoice_number')
        
        # Log received form data for debugging
        logger.info(f"Received invoice upload data: user_id={user_id}, outlet_name={outlet_name}, invoice_date={invoice_date}, invoice_number={invoice_number}")

        # Get quantities for each product
        sensodent_k_fr_75gm = request.form.get('SENSODENT_K_FR_75GM', 0)
        sensodent_kf_cp_75gm = request.form.get('SENSODENT_KF_CP_75GM', 0)
        sensodent_k_fr_125gm = request.form.get('SENSODENT_K_FR_125GM', 0)
        sensodent_kf_cp_125gm = request.form.get('SENSODENT_KF_CP_125GM', 0)
        sensodent_kf_cp_15g = request.form.get('SENSODENT_KF_CP_15G', 0)
        sensodent_k_fr_15g = request.form.get('SENSODENT_K_FR_15G', 0)
        kidodent_cavity_shield = request.form.get('KIDODENT_CAVITY_SHIELD', 0)

        # Validate required fields
        if not all([user_id, invoice_date, invoice_number, invoice_file]):
            logger.error("Missing required fields for invoice upload")
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400

        # Get outlet code from apOutlet table
        session = get_db_connection()
        try:
            query = text('SELECT outletCode FROM apOutlet WHERE outletName = :outlet_name')
            outlet_result = session.execute(query, {'outlet_name': outlet_name}).fetchone()
            
            if not outlet_result:
                logger.error(f"No outlet code found for outlet name: {outlet_name}")
                session.close()
                return jsonify({'success': False, 'message': 'Outlet code not found'}), 400
            
            outlet_code = outlet_result[0]
            logger.info(f"Found outlet code: {outlet_code} for outlet name: {outlet_name}")

            # Generate filename in the format outletcode_date
            current_date = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_extension = os.path.splitext(str(invoice_file.filename))[1] or '.pdf'
            azure_filename = f"{outlet_code}_{current_date}{file_extension}"

            # Upload file to Azure Blob Storage
            blob_client = container_client.get_blob_client(azure_filename)
            file_contents = invoice_file.read()
            blob_client.upload_blob(file_contents, overwrite=True)
            logger.info(f"Successfully uploaded file to Azure Blob Storage: {azure_filename}")

            # Prepare invoice details query
            insert_query = text('''
                INSERT INTO InvoiceDetails (
                    UserID, OutletCode, OutletName, InvoiceAvailable, DisplayType,
                    InvoiceDate, InvoiceNumber, InvoiceDocument,
                    SENSODENT_K_FR_75GM, SENSODENT_KF_CP_75GM, SENSODENT_K_FR_125GM,
                    SENSODENT_KF_CP_125GM, SENSODENT_KF_CP_15G, SENSODENT_K_FR_15G,
                    KIDODENT_CAVITY_SHIELD
                ) VALUES (
                    :user_id, :outlet_code, :outlet_name, :invoice_available, :display_type,
                    :invoice_date, :invoice_number, :invoice_document,
                    :sensodent_k_fr_75gm, :sensodent_kf_cp_75gm, :sensodent_k_fr_125gm,
                    :sensodent_kf_cp_125gm, :sensodent_kf_cp_15g, :sensodent_k_fr_15g,
                    :kidodent_cavity_shield
                )
            ''')

            # Execute the insert query
            session.execute(insert_query, {
                'user_id': user_id,
                'outlet_code': outlet_code,
                'outlet_name': outlet_name,
                'invoice_available': True,
                'display_type': 'Standard',
                'invoice_date': invoice_date,
                'invoice_number': invoice_number,
                'invoice_document': azure_filename,
                'sensodent_k_fr_75gm': sensodent_k_fr_75gm,
                'sensodent_kf_cp_75gm': sensodent_kf_cp_75gm,
                'sensodent_k_fr_125gm': sensodent_k_fr_125gm,
                'sensodent_kf_cp_125gm': sensodent_kf_cp_125gm,
                'sensodent_kf_cp_15g': sensodent_kf_cp_15g,
                'sensodent_k_fr_15g': sensodent_k_fr_15g,
                'kidodent_cavity_shield': kidodent_cavity_shield
            })
            
            # Commit the transaction
            session.commit()
            logger.info(f"Successfully inserted invoice details for user {user_id}")

        except Exception as db_error:
            # Rollback the transaction in case of error
            session.rollback()
            logger.error(f"Database error during invoice upload: {str(db_error)}", exc_info=True)
            return jsonify({'success': False, 'message': f'Database error: {str(db_error)}'}), 500
        
        finally:
            # Always close the session
            session.close()

        return jsonify({'success': True, 'message': 'Invoice uploaded successfully'}), 200

    except Exception as e:
        # Log any unexpected errors
        logger.error(f"Unexpected error in upload_invoice: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Unexpected error: {str(e)}'}), 500

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
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
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
    print(f"\nAccess the application at:")
    print(f"Local:   http://localhost:5000\n")
    
    # Run the app only on localhost
    app.run(host='localhost', port=5000, debug=True)
