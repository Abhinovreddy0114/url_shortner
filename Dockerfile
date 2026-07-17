# Use an official, lightweight Python image
FROM python:3.12-slim

# Set working directory inside the container
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application directories and files
COPY app.py .
COPY templates/ templates/
COPY static/ static/

# Expose Flask's port
EXPOSE 5001

# Command to start the application
CMD ["python", "app.py"]
