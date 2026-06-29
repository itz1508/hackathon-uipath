"""Event bus with generated client."""

from generated_event_client import EventPublisher

def publish(event):
    return EventPublisher().send(event)
