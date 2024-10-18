import os
import requests
from bs4 import BeautifulSoup
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# URLs for login and tenders page
LOGIN_URL = "https://tender.2merkato.com/login"
TENDERS_URL = "https://tender.2merkato.com/tenders/"

# Fetch credentials from environment variables
username = os.getenv("2MERKATO_USERNAME")
password = os.getenv("2MERKATO_PASSWORD")

# Print to debug if the values are loaded correctly
print(f"Loaded username: {username}")
print(f"Loaded password: {password}")

# Create a session to persist cookies
session = requests.Session()

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
        # Check if we're still on the login page by searching for login form
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

        # Filter and collect only links that start with 'https://tender.2merkato.com/tenders/'
        tender_links = [link['href'] for link in links if link['href'].startswith("/tenders/")]

        # Construct the full URL
        tender_links = [f"https://tender.2merkato.com{link}" for link in tender_links]
        return tender_links
    else:
        print(f"Failed to retrieve tenders page with status code: {response.status_code}")
        return []

def scrape_tender_title(tender_url):
    """Scrape the title of a specific tender page."""
    response = session.get(tender_url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        title_tag = soup.find('title')
        title = title_tag.text.strip() if title_tag else "No title found"
        return title
    else:
        print(f"Failed to retrieve tender {tender_url} with status code: {response.status_code}")
        return None

# Attempt to log in
if login(username, password):
    # If login is successful, scrape all tender links
    tender_links = scrape_tender_links()

    if tender_links:
        print(f"Found {len(tender_links)} tender links. Scraping titles...")

        # Scrape the title for each tender link
        for tender_url in tender_links:
            title = scrape_tender_title(tender_url)
            if title:
                print(f"URL: {tender_url}")
                print(f"Title: {title}")
            time.sleep(1)  # Add delay to avoid overloading the server
    else:
        print("No tender links found.")
else:
    print("Exiting due to login failure.")
