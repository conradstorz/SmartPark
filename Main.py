from flask import Flask, request, abort
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import os
from pathlib import Path
import datetime

app = Flask(__name__)

# Get Twilio credentials from environment variables
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Twilio client for API calls
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Directory where SMS and MMS will be saved
SAVE_DIRECTORY = Path("messages")
SAVE_DIRECTORY.mkdir(parents=True, exist_ok=True)

# In-memory dictionary to store opt-in status (in production, this would be a database)
opt_in_status = {}

def save_message(from_number, message_body, media_url=None):
    """Save SMS/MMS messages to a text file."""
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    message_filename = SAVE_DIRECTORY / f"message_{from_number}_{timestamp}.txt"
    
    with open(message_filename, 'w') as file:
        file.write(f"From: {from_number}\n")
        file.write(f"Message: {message_body}\n")
        if media_url:
            file.write(f"Media URL: {media_url}\n")

@app.route("/sms", methods=['POST'])
def receive_sms():
    """Receive and handle incoming SMS/MMS messages."""
    from_number = request.form['From']
    message_body = request.form['Body'].strip().upper()  # Normalize the message to uppercase
    media_url = request.form.get('MediaUrl0', None)  # For MMS if present
    
    # Check if the customer has opted in
    if from_number not in opt_in_status:
        # First-time message, ask for opt-in
        response = MessagingResponse()
        response.message("Welcome! Reply YES to receive updates from us. Reply STOP at any time to unsubscribe.")
        opt_in_status[from_number] = 'pending'  # Mark them as pending opt-in
        return str(response)

    # Handle opt-in responses
    if message_body == 'YES' and opt_in_status[from_number] == 'pending':
        # User agrees to receive messages
        opt_in_status[from_number] = 'subscribed'
        response = MessagingResponse()
        response.message("Thank you for subscribing! You will now receive updates. Reply STOP at any time to unsubscribe.")
        return str(response)

    if message_body == 'STOP':
        # Unsubscribe the user
        opt_in_status[from_number] = 'unsubscribed'
        response = MessagingResponse()
        response.message("You have been unsubscribed. You will no longer receive messages. Reply YES if you wish to re-subscribe.")
        return str(response)

    # If the user is unsubscribed or pending, don't send further messages
    if opt_in_status.get(from_number) == 'unsubscribed':
        response = MessagingResponse()
        response.message("You are currently unsubscribed. Reply YES if you wish to receive messages again.")
        return str(response)

    # If the user is subscribed, process the incoming message as usual
    if opt_in_status[from_number] == 'subscribed':
        # Save the message
        save_message(from_number, message_body, media_url)

        # Create a response message to acknowledge receipt
        response = MessagingResponse()
        response.message("Your message has been received. Thank you for your reply!")
        return str(response)

@app.route("/send_sms", methods=['POST'])
def send_sms():
    """Endpoint to send an SMS using Twilio API."""
    to_number = request.form.get('to')
    message_body = request.form.get('message')

    if not to_number or not message_body:
        return "Both 'to' and 'message' fields are required", 400

    if opt_in_status.get(to_number) != 'subscribed':
        return "The recipient has not opted in or is unsubscribed.", 403

    try:
        # Send SMS via Twilio
        message = client.messages.create(
            body=message_body,
            from_=TWILIO_PHONE_NUMBER,
            to=to_number
        )

        return f"Message sent successfully: SID {message.sid}", 200

    except Exception as e:
        print(f"Error sending SMS: {e}")
        return f"Failed to send SMS: {e}", 500

if __name__ == "__main__":
    # Ensure Twilio credentials are set up
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
        raise ValueError("Twilio credentials (ACCOUNT_SID, AUTH_TOKEN, PHONE_NUMBER) must be set in environment variables.")
    
    app.run(debug=True)
