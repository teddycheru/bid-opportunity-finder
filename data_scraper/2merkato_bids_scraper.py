import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from dotenv import load_dotenv
import psycopg2  # Import psycopg2 for PostgreSQL
from psycopg2 import OperationalError
import json

# Load environment variables from .env file
load_dotenv()

# Database connection details from environment variables
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# URLs for login and tenders page
LOGIN_URL = "https://tender.2merkato.com/login"
TENDERS_URL = "https://tender.2merkato.com/tenders/"

# Fetch credentials from environment variables for the login
username = os.getenv("2MERKATO_USERNAME")
password = os.getenv("2MERKATO_PASSWORD")

# Create a session to persist cookies
session = requests.Session()

def create_db_connection():
    """Create and return a database connection."""
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return connection
    except OperationalError as e:
        print(f"Operational error: {e}")
        return None
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def insert_tender_data(title, core_details, other_data):
    """Insert scraped tender data into the PostgreSQL database."""
    connection = create_db_connection()
    if connection is None:
        print("Failed to connect to the database. Exiting.")
        return  # Exit the function if the connection fails

    try:
        cursor = connection.cursor()

        # Convert dictionaries to JSON strings
        core_details_json = json.dumps(core_details)
        other_data_json = json.dumps(other_data)

        # Insert data into the tmerkato_tenders table
        cursor.execute("""
            INSERT INTO tmerkato_tenders (title, core_details, other_data)
            VALUES (%s, %s, %s)
        """, (title, core_details_json, other_data_json))  # Use the JSON strings here

        connection.commit()  # Commit the changes
        print("Data inserted successfully.")
    except Exception as e:
        print(f"Error inserting data into database: {e}")
    finally:
        cursor.close()
        connection.close()

def get_csrf_token():
    """Fetch the CSRF token from the login page."""
    login_page = session.get(LOGIN_URL)
    soup = BeautifulSoup(login_page.content, 'html.parser')
    
    # Find the hidden CSRF token
    csrf_token = soup.find('input', {'name': '_csrf'})['value']
    return csrf_token

def login(username, password):
    """Attempt to log in with the provided credentials."""
    csrf_token = get_csrf_token()

    # Prepare the login payload with CSRF token and credentials
    payload = {
        'emailOrMobile': username,   # Field for username
        'password': password,        # Field for password
        '_csrf': csrf_token,         # CSRF token
        'captcha': ''                # Placeholder for captcha
    }

    # Send the POST request to login
    login_response = session.post(LOGIN_URL, data=payload)

    if login_response.status_code == 200:
        soup = BeautifulSoup(login_response.content, 'html.parser')
        if soup.find('form', id='authForm'):
            print("Login failed. Please check credentials.")
            return False
        else:
            print("Login successful.")
            return True
    else:
        print(f"Login request failed with status code: {login_response.status_code}")
        return False

def scrape_tender_links():
    """Scrape the tender page and collect all valid tender links."""
    response = session.get(TENDERS_URL)

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        links = soup.find_all('a', href=True)

        tender_links = [link['href'] for link in links if link['href'].startswith("/tenders/")]
        tender_links = [f"https://tender.2merkato.com{link}" for link in tender_links]
        return tender_links
    else:
        print(f"Failed to retrieve tenders page with status code: {response.status_code}")
        return []

def scrape_tender_details(tender_url):
    """Scrape title, core details, additional paragraph contents, and tables of a tender page."""
    response = session.get(tender_url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')

        # Scrape the title
        title_tag = soup.find('title')
        title = title_tag.text.strip() if title_tag else "No title found"

        # Separate core details and other data
        core_details = {}
        other_data = {}

        # Scrape the details section
        detail_sections = soup.find_all('div', class_='tender-detail-outer')
        for section in detail_sections:
            label = section.find('div', class_='tender-detail-label').text.strip()
            value_tag = section.find('div', class_='tender-detail-value')

            value = value_tag.text.strip() if value_tag else "No value"

            if 'Region' in label and value_tag.find('a'):
                value = value_tag.find('a').text.strip()

            # Store the value in core_details
            core_details[label] = value

        # Scrape the "Posted" date
        posted_tag = soup.find('div', class_='post-date tender-detail-value')
        core_details["Posted"] = posted_tag.text.strip() if posted_tag else "No value"

        # Scrape paragraph content, excluding those inside tables
        paragraphs = []
        for p in soup.find_all('p'):
            if not p.find_parent('table'):  # Check if the parent is not a table
                paragraphs.append(p.text.strip())

        other_data['paragraphs'] = paragraphs

        # Scrape tables
        tables = soup.find_all('table')
        table_data = []
        for table in tables:
            # Extract table headers and rows
            headers = [th.text.strip() for th in table.find_all('th')]
            rows = []
            for row in table.find_all('tr'):
                cols = [td.text.strip() for td in row.find_all('td')]
                if cols:  # Only add rows that have data
                    rows.append(cols)

            # If no headers found, use the first row as headers
            if not headers and rows:
                headers = rows[0]  # Use the first row as headers
                rows = rows[1:]  # Remove the first row from the data rows

            table_data.append({'headers': headers, 'rows': rows})

        other_data['tables'] = table_data  # Ensure to save the table data in other_data

        return title, core_details, other_data
    else:
        print(f"Failed to retrieve tender {tender_url} with status code: {response.status_code}")
        return None, {}, {}

if login(username, password):
    # If login is successful, scrape all tender links
    tender_links = scrape_tender_links()

    if tender_links:
        print(f"Found {len(tender_links)} tender links. Scraping details...")

        # Scrape the details for each tender link
        for tender_url in tender_links:
            title, core_details, other_data = scrape_tender_details(tender_url)

            if title:
                print(f"\nURL: {tender_url}")
                print(f"Title: {title}")

                # Print core details
                print("\nCore Details:")
                for label, value in core_details.items():
                    print(f"{label}: {value}")

                # Print the other data (paragraphs, tables, etc.)
                print("\nOther Data:")
                for paragraph in other_data.get('paragraphs', []):
                    print(paragraph)

                # Insert the data into PostgreSQL
                insert_tender_data(title, core_details, other_data)

            # Add delay to avoid overloading the server
            time.sleep(1)
    else:
        print("No tender links found.")
else:
    print("Exiting due to login failure.")
