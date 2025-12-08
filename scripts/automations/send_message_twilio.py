# /// script
# requires-python = ">=3.13"
# dependencies = [
#  "twilio",
# ]
# ///

import os

from twilio.rest import Client


# Your Account SID and Auth Token from console.twilio.com
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_TO_NUMBER = os.getenv("TWILIO_TO_NUMBER")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_message(message: str) -> None:
    message = client.messages.create(
        to=TWILIO_TO_NUMBER,
        from_=TWILIO_FROM_NUMBER,
        body=message
    )
    print(message.sid)


def main() -> None:
    send_message(message="Hello from Python!")


if __name__ == "__main__":
    main()
