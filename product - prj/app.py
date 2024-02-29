from flask import Flask, render_template, request, redirect, url_for
import pyodbc
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from io import BytesIO
import base64

app = Flask(__name__, template_folder='templates', static_folder='static')

# Replace these values with your SQL Server details
server = 'ABINA\\SQLEXPRESS'
database = 'master'
conn_str = f'DRIVER=SQL Server;SERVER={server};DATABASE={database};Trusted_Connection=yes;'

# Function to establish a connection to the SQL Server
def establish_connection():
    try:
        conn = pyodbc.connect(conn_str)
        return conn
    except pyodbc.Error as e:
        print(f"Error connecting to SQL Server: {e}")
        return None

def plot_busy_times():
    conn = establish_connection()
    if conn:
        cursor = conn.cursor()
        
        # Query to get total guests for each day and time
        cursor.execute('''
            SELECT date, SUM(guests) as total_guests
            FROM reservations
            GROUP BY date
        ''')
        data = cursor.fetchall()
        conn.close()

        # Extract data for plotting
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        total_guests = [0] * len(days)

        for row in data:
            day_index = datetime.strptime(row.date, '%Y-%m-%d').weekday()
            total_guests[day_index] = row.total_guests

        # Plotting
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(days, total_guests, color='skyblue')

        ax.set_title('Busy Times')
        ax.set_xlabel('Day of the Week')
        ax.set_ylabel('Total Guests')
        plt.tight_layout()

        # Save the plot to a BytesIO object
        img_io = BytesIO()
        plt.savefig(img_io, format='png')
        img_io.seek(0)

        # Convert the plot to a base64-encoded string
        img_str = base64.b64encode(img_io.read()).decode('utf-8')

        return img_str

    return None

# Function to get the total number of guests in reservations
def get_total_guests_for_time_slot(date, time):
    conn = establish_connection()
    if conn:
        cursor = conn.cursor()

        # Calculate the time slot (considering 1 hour time slots)
        reservation_time = datetime.strptime(time, '%H:%M')
        start_time = reservation_time - timedelta(hours=1)
        end_time = reservation_time

        # Clear outdated reservations
        outdated_reservations_query = '''
            DELETE FROM reservations
            WHERE date = ? AND time < ?
        '''
        cursor.execute(outdated_reservations_query, (date, start_time.strftime('%H:%M')))
        conn.commit()

        # SQL query to get the total guests in the specified time slot
        cursor.execute('''
            SELECT SUM(guests)
            FROM reservations
            WHERE date = ? AND time BETWEEN ? AND ?
        ''', (date, start_time.strftime('%H:%M'), end_time.strftime('%H:%M')))

        total_guests = cursor.fetchone()[0]
        conn.close()

        return total_guests if total_guests is not None else 0

    return 0

@app.route('/')
def index():
    busy_times_plot = plot_busy_times()
    return render_template('index.html', busy_times_plot=busy_times_plot)

@app.route('/reserve', methods=['POST'])
def reserve():
    # Retrieve form data
    name = request.form.get('name')
    date = request.form.get('date')
    time = request.form.get('time')
    guests = int(request.form.get('guests'))  # Convert to int

    # Check total number of guests in reservations
    total_guests_in_slot = get_total_guests_for_time_slot(date, time)

    # Check if there's enough space
    if total_guests_in_slot + guests <= 20:
        # Insert reservation details into the SQL Server database
        conn = establish_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO reservations (name, date, time, guests) VALUES (?, ?, ?, ?)
            ''', (name, date, time, guests))
            conn.commit()
            conn.close()

            # Fetch the updated graph after reservation
            busy_times_plot = plot_busy_times()

            # Pass reservation status, name, and updated graph to the template
            return render_template('index.html', reservation_status="Reservation successful!", name=name, busy_times_plot=busy_times_plot)
    else:
        # Display an error message
        return render_template('index.html', reservation_status="No space available. Try again with fewer guests.")

@app.route('/submit-email', methods=['POST'])
def submit_email():
    email = request.form.get('email')

    # Insert the email into the user_email table
    conn = establish_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO user_email (email) VALUES (?)', (email,))
        conn.commit()
        conn.close()

        # You can redirect the user to a thank you page or return a message
        return render_template('index.html', email_status="Email submitted successfully!")
    else:
        return render_template('index.html', email_status="Error submitting email. Please try again.")
if __name__ == '__main__':
    app.run(debug=True)
