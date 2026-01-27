import logging
import os

logger = logging.getLogger("notification_service")

# Note: In a real production scenario, you would use Twilio:
# from twilio.rest import Client
# TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID")
# TWILIO_AUTH = os.environ.get("TWILIO_AUTH_TOKEN")
# TWILIO_PHONE = os.environ.get("TWILIO_PHONE_NUMBER")

def send_sms_notification(to_phone: str, message: str) -> bool:
    """
    Sends an SMS notification. 
    Currently mocks the behavior by logging to console.
    """
    if not to_phone:
        logger.warning("No phone number provided, skipping SMS.")
        return False

    logger.info(f"--- SMS NOTIFICATION ---")
    logger.info(f"To: {to_phone}")
    logger.info(f"Message: {message}")
    logger.info(f"------------------------")

    # Mock success
    return True

def notify_team_assignment(teams: list, problem_title: str, village_name: str):
    """Notifies all teams about their assignment."""
    for team in teams:
        members = team.get('members', [])
        for member in members:
            # Recommender members have 'name' and 'person_id' directly
            # Fallback to 'profile' structure if present
            profile = member.get('profile', {})
            name = member.get('name') or profile.get('full_name') or profile.get('name') or 'Volunteer'
            phone = member.get('phone') or profile.get('phone')
            
            if phone:
                msg = f"Hello {name}, you have been assigned to: '{problem_title}' in {village_name}. Local coordinators will contact you soon."
                send_sms_notification(phone, msg)
            else:
                logger.info(f"Skipping notification for {name} (no phone number found).")

def notify_problem_resolved(villager_phone: str, problem_title: str):
    """Notifies the villager that their problem is resolved."""
    if villager_phone:
        msg = f"Good news! Your reported issue '{problem_title}' has been marked as resolved by our volunteers. Thank you for your patience."
        send_sms_notification(villager_phone, msg)
