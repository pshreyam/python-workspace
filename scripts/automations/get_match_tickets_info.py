# /// script
# requires-python = ">=3.13"
# dependencies = [
#  "requests",
#  "loguru",
#  "twilio",
#  "tenacity",
# ]
# ///

import os
import requests
from loguru import logger
from twilio.rest import Client
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


TICKET_URL = os.getenv("TICKET_URL")

# Known ticket IDs that we're not interested in (comma-separated from env var)
known_ids_str = os.getenv("KNOWN_TICKET_IDS", "")
KNOWN_TICKET_IDS = {tid.strip() for tid in known_ids_str.split(",") if tid.strip()}

# Account SID and Auth Token (from console.twilio.com)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN")
# Twilio from number (from console.twilio.com)
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
# Your phone number
TWILIO_TO_NUMBER = os.getenv("TWILIO_TO_NUMBER")

# Check if debug mode is enabled or not
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
# Stop the execution of cron
STOP_EXECUTION = os.getenv("STOP_EXECUTION", "false").lower() == "true"


# Initialize Twilio client
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_message(message: str) -> None:
    """Send message via Twilio.
    
    Args:
        message (str): The message to send.
    """
    if DEBUG_MODE:
        logger.info("Debug mode is enabled. Skipping sending message and printing to console.")
        logger.info(f"Message: {message}")
        return

    logger.info(f"Sending message: {message} ...")
    
    message = client.messages.create(
        to=TWILIO_TO_NUMBER,
        from_=TWILIO_FROM_NUMBER,
        body=message,
    )
    logger.info(f"Message sent successfully (SID: {message.sid})")


def send_webhook_notification(new_tickets: list[dict]) -> None:
    """Send webhook notification about new tickets."""
    webhook_url = os.getenv("WEBHOOK_URL")
    
    if not webhook_url:
        logger.warning("WEBHOOK_URL not set, skipping notification")
        return
    
    # Prepare message
    message_lines = ["🎫 **New Match Tickets Available!**\n"]
    for ticket in new_tickets:
        title = ticket.get("title", "Unknown")
        ticket_id = ticket.get("idx", "Unknown")
        message_lines.append(f"• {title} (ID: {ticket_id})")
    
    message = "\n".join(message_lines)
    
    # Determine webhook type and format payload accordingly
    # Discord webhook format
    if "discord.com" in webhook_url:
        payload = {
            "content": message,
            "username": "Ticket Monitor"
        }
    # Slack webhook format
    elif "slack.com" in webhook_url:
        payload = {
            "text": message
        }
    # Generic webhook (JSON)
    else:
        payload = {
            "message": message,
            "tickets": new_tickets
        }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=60)
        response.raise_for_status()
        logger.info("Webhook notification sent successfully")
    except requests.RequestException as e:
        logger.error(f"Failed to send webhook notification: {e}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.RequestException),
    before_sleep=lambda retry_state: logger.warning(
        f"Request failed, retrying... (attempt {retry_state.attempt_number}/3)"
    )
)
def fetch_tickets() -> dict:
    """Fetch tickets from API with retry logic.
    
    Returns:
        dict: The response JSON containing ticket data
    """
    req = requests.get(TICKET_URL, timeout=60)
    req.raise_for_status()
    return req.json()


def main() -> None:
    logger.info("Checking for new match tickets...")

    if STOP_EXECUTION:
        logger.info("STOP_EXECUTION is enabled. Skipping execution.")
        return

    try:
        response = fetch_tickets()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch tickets after 3 attempts: {e}")
        send_message(message="FAILED")
        return
    except Exception as e:
        logger.error(f"Failed to fetch tickets after 3 attempts: {e}")
        send_message(message="FAILED")
        return

    if response.get("status", True) is False:
        logger.error(f"Failed to fetch tickets: {response.get('message')}")
        send_message(message="FAILED")
        return
 
    tickets = response.get("children", [])
    new_tickets = []

    # Check for new tickets
    for ticket in tickets:
        ticket_id = str(ticket.get("idx")).strip()
        ticket_title = str(ticket.get("title")).strip()

        if ticket_id in KNOWN_TICKET_IDS:
            logger.debug(f"Skipping known ticket: {ticket_title} ({ticket_id})")
            continue
        
        logger.info(f"🆕 Found new ticket: {ticket_title} ({ticket_id})")
        new_tickets.append(ticket)

    # Prepare message for new tickets
    new_ticket_message = f"{len(new_tickets)} 🆕 TICKETS"
    
    logger.info(f"Total tickets: {len(tickets)}, New tickets: {len(new_tickets)}")
    
    # Send webhook notification if there are new tickets
    if not new_tickets:
        logger.info("No new tickets found")
        return

    # Try sending SMS. If it fails send webhook.
    try:
        send_message(message=new_ticket_message)
    except Exception as e:
        logger.error(f"Failed to send message: {e}. Trying to send webhook notification...")
        try:
            send_webhook_notification(new_tickets=new_tickets)
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            logger.critical("Failed to send notification. Please check once.")


if __name__ == "__main__":
    main()
