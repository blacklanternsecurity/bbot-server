# Use an official Python runtime as a parent image
FROM python:3.11

# Copy the current directory contents into the container at /app
COPY . /app

# Set the working directory in the container
WORKDIR /app

# Install required packages
RUN pip install .

# Expose the port Uvicorn will run on
EXPOSE 8807

# Run the FastAPI app with Uvicorn
CMD ["bbot-server", "--host", "0.0.0.0", "--port", "8807"]
