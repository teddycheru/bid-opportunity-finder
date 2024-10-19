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

def scrape_tender_details(tender_url):
    """Scrape the title and details of a specific tender page."""
    response = session.get(tender_url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Scrape the title
        title_tag = soup.find('title')
        title = title_tag.text.strip() if title_tag else "No title found"
        
        # Scrape additional details like bid dates, region, and more
        details = {}
        
        # Loop through all tender detail sections
        detail_sections = soup.find_all('div', class_='tender-detail-outer')

        for section in detail_sections:
            label = section.find('div', class_='tender-detail-label').text.strip()
            value_tag = section.find('div', class_='tender-detail-value')

            # Handle cases where value_tag may not exist
            if value_tag:
                value = value_tag.text.strip()
            else:
                # If the value is empty or doesn't exist
                value = "No value"

            # Special case for "Region" - grab the link text inside if it exists
            if 'Region' in label and value_tag and value_tag.find('a'):
                value = value_tag.find('a').text.strip()

            # Add to the details dictionary
            details[label] = value

        # Handle the special case for the "Posted" field with a different class
        posted_tag = soup.find('div', class_='post-date tender-detail-value')
        if posted_tag:
            details["Posted"] = posted_tag.text.strip()
        else:
            details["Posted"] = "No value"
        
        return title, details
    else:
        print(f"Failed to retrieve tender {tender_url} with status code: {response.status_code}")
        return None, {}

# Attempt to log in
if login(username, password):
    # If login is successful, scrape all tender links
    tender_links = scrape_tender_links()

    if tender_links:
        print(f"Found {len(tender_links)} tender links. Scraping details...")

        # Scrape the title and details for each tender link
        for tender_url in tender_links:
            title, details = scrape_tender_details(tender_url)
            if title:
                print(f"URL: {tender_url}")
                print(f"Title: {title}")
                print("Details:")
                for label, value in details.items():
                    print(f"  {label}: {value}")
            time.sleep(1)  # Add delay to avoid overloading the server
    else:
        print("No tender links found.")
else:
    print("Exiting due to login failure.")
