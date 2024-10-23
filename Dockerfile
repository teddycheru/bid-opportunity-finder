# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements.txt file into the container at /app
COPY requirements.txt .

# Install any required packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . /app

# Make port 5432 available to the world outside this container (if needed)
EXPOSE 5432

# Command to run your scraper (this will be overridden by docker-compose.yml)
CMD ["python", "2merkato_bids_scraper.py"]
