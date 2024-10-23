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

# 2Merkato login details
username = os.getenv("2MERKATO_USERNAME")
password = os.getenv("2MERKATO_PASSWORD")

# URLs for login and tenders page (without the page number)
BASE_TENDERS_URL = "https://tender.2merkato.com/tenders?q=&bidding=&endDate=&category[]=61bbe243cfb36d443e895a5f,61bbe243cfb36d443e895a24,61bbe243cfb36d443e895a25,61bbe243cfb36d443e895a9b,61bbe243cfb36d443e895a94,61bbe243cfb36d443e8959ed,61bbe243cfb36d443e8959f6,61bbe243cfb36d443e8959f7,61bbe243cfb36d443e895a26,61bbe243cfb36d443e895a27,61bbe243cfb36d443e895a40,61bbe243cfb36d443e895a45,&action=&language=61bbe23bcfb36d443e8959e5&tenderSource=&region=&startDate="

LOGIN_URL = "https://tender.2merkato.com/login"

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
        return

    try:
        cursor = connection.cursor()

        core_details_json = json.dumps(core_details)
        other_data_json = json.dumps(other_data)

        cursor.execute("""
            INSERT INTO tmerkato_tenders (title, core_details, other_data)
            VALUES (%s, %s, %s)
        """, (title, core_details_json, other_data_json))

        connection.commit()
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
    csrf_token = soup.find('input', {'name': '_csrf'})['value']
    return csrf_token

def login(username, password):
    """Attempt to log in with the provided credentials."""
    csrf_token = get_csrf_token()

    payload = {
        'emailOrMobile': username,
        'password': password,
        '_csrf': csrf_token,
        'captcha': ''
    }

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

def scrape_tender_links(page_number):
    """Scrape the tender page and collect all valid tender links for the given page."""
    url = f"{BASE_TENDERS_URL}&page={page_number}"
    response = session.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        links = soup.find_all('a', href=True)

        tender_links = []
        for link in links:
            href = link['href']
            full_url = f"https://tender.2merkato.com{href}" if href.startswith("/tenders/") else href

            if full_url.startswith("https://tender.2merkato.com/tenders/") and \
               not any(excluded in full_url for excluded in ["/free", "/addisland", "/home", "?action=&page="]) and \
               len(full_url.split("/tenders/")[1]) > 0:
                tender_links.append(full_url)

        return tender_links
    else:
        print(f"Failed to retrieve tenders page {page_number} with status code: {response.status_code}")
        return []

def scrape_tender_details(tender_url):
    """Scrape title, core details, additional paragraph contents, and tables of a tender page."""
    response = session.get(tender_url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')

        title_tag = soup.find('title')
        title = title_tag.text.strip() if title_tag else "No title found"

        core_details = {}
        other_data = {}

        detail_sections = soup.find_all('div', class_='tender-detail-outer')
        for section in detail_sections:
            label = section.find('div', class_='tender-detail-label').text.strip()
            value_tag = section.find('div', class_='tender-detail-value')
            
            value = value_tag.text.strip() if value_tag else "No value"
            if 'Region' in label and value_tag.find('a'):
                value = value_tag.find('a').text.strip()

            core_details[label] = value

        posted_tag = soup.find('div', class_='post-date tender-detail-value')
        core_details["Posted"] = posted_tag.text.strip() if posted_tag else "No value"

        tor_section = soup.find('a', class_='btn btn-sm btn-success')
        if tor_section and 'href' in tor_section.attrs:
            tor_link = f"https://tender.2merkato.com{tor_section['href']}"
            core_details["TOR"] = tor_link
        else:
            core_details["TOR"] = "Not attached"

        paragraphs = []
        for p in soup.find_all('p'):
            if not p.find_parent('table'):
                paragraphs.append(p.text.strip())

        other_data['paragraphs'] = paragraphs

        tables = soup.find_all('table')
        table_data = []
        for table in tables:
            headers = [th.text.strip() for th in table.find_all('th')]
            rows = []
            for row in table.find_all('tr'):
                cols = [td.text.strip() for td in row.find_all('td')]
                if cols:
                    rows.append(cols)

            if not headers and rows:
                headers = rows[0]
                rows = rows[1:]

            table_data.append({'headers': headers, 'rows': rows})

        other_data['tables'] = table_data

        return title, core_details, other_data
    else:
        print(f"Failed to retrieve tender {tender_url} with status code: {response.status_code}")
        return None, {}, {}

if login(username, password):
    page_number = 0
    while True:
        print(f"Scraping page {page_number}...")
        tender_links = scrape_tender_links(page_number)

        if not tender_links:
            print(f"No more tenders found on page {page_number}. Stopping.")
            break

        for tender_url in tender_links:
            title, core_details, other_data = scrape_tender_details(tender_url)

            if title:
                print(f"\nURL: {tender_url}")
                print(f"Title: {title}")

                print("\nCore Details:")
                for label, value in core_details.items():
                    print(f"{label}: {value}")

                print("\nOther Data:")
                for paragraph in other_data.get('paragraphs', []):
                    print(paragraph)

                insert_tender_data(title, core_details, other_data)

            time.sleep(1)  # Avoid overloading the server

        page_number += 1
else:
    print("Exiting due to login failure.")
    
if __name__ == "__main__":
    print("Script loaded. Scraping is disabled by default.")
    # Trigger scraping
    # scrape_tenders()