FROM python:3.9-slim

# Set working directory inside the container
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app code
COPY app/ .

# Run the application
# Main file is named 'app.py' inside the 'app' folder
CMD ["python", "app.py"]
