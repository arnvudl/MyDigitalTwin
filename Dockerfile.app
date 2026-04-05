FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Expose the Dash port
EXPOSE 8050

# Run the Dash app
CMD ["python", "-m", "app.app"]