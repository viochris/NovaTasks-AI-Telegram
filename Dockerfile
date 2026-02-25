# Use standard Python 3.11 for compatibility with async and genai libraries
FROM python:3.11

# Set the working directory inside the container
WORKDIR /code

# Copy the requirements file into the container
COPY ./requirements.txt /code/requirements.txt

# Upgrade pip and install required libraries cleanly
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /code/requirements.txt

# Create a non-root user for security (Standard Docker Best Practice)
# This prevents the bot from running with full root permissions
RUN useradd -m -u 1000 user
USER user

# Set environment variables for the application user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Switch to the user's application directory
WORKDIR $HOME/app

# Copy the bot source code into the container and set ownership
COPY --chown=user . $HOME/app

# Start the NovaTasks Ephemeral AI Telegram Bot
# Ensures it runs the correct slot-filling architecture file
CMD ["python", "NovaTasks-AI.py"]