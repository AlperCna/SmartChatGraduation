FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Set python path so backend modules can import each other
ENV PYTHONPATH=/app

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "backend/app.py"]
