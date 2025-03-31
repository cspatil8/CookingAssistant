import reactivex as rx
import reactivex.operators as ops
from reactivex.subject import Subject
from ..state import actions
import sys

# Global flag for test mode
IS_TEST_MODE = False
MAX_TIMER_DURATION_TEST = 10  # seconds

# Dictionary to keep track of active timers and their remaining time for display
active_timers = {}

def set_test_mode(is_test: bool):
    """Sets the global test mode flag."""
    global IS_TEST_MODE
    IS_TEST_MODE = is_test
    if IS_TEST_MODE:
        print("--- Timer Test Mode Active (Max Duration: 10s) ---")

def display_timers():
    """Clears the line and displays the current status of all active timers."""
    timer_strings = [f"{id}: {rem}s" for id, rem in active_timers.items() if rem > 0]
    output = "Active Timers: " + " | ".join(timer_strings) + "        " # Padding spaces
    # Use carriage return to overwrite the line
    sys.stdout.write("\r" + output)
    sys.stdout.flush()

def set_timer(timer_id: str, duration: int, timer_event_subject: Subject):
    """
    Schedules a timer that counts down visibly and emits a TIMER_EXPIRED event.
    In test mode, duration is capped.
    """
    actual_duration = duration
    if IS_TEST_MODE and duration > MAX_TIMER_DURATION_TEST:
        print(f"\n[Test Mode] Capping timer '{timer_id}' from {duration}s to {MAX_TIMER_DURATION_TEST}s")
        actual_duration = MAX_TIMER_DURATION_TEST
    elif timer_id in active_timers:
        print(f"\nTimer '{timer_id}' already exists. Replacing.")
        # In a more complex scenario, you might want to handle this differently
        # (e.g., cancel the previous timer explicitly)
        
    if actual_duration <= 0:
        print(f"\nTimer '{timer_id}' requested with duration <= 0. Ignoring.")
        return
        
    active_timers[timer_id] = actual_duration # Initialize remaining time
    display_timers()

    rx.interval(1).pipe( # Emit every 1 second
        ops.take(actual_duration) # Take only 'actual_duration' emissions
    ).subscribe(
        on_next=lambda tick: [
            # Decrement remaining time
            active_timers.update({timer_id: actual_duration - 1 - tick}),
            # Update display
            display_timers()
        ],
        on_completed=lambda: [
            # Timer finished
            active_timers.pop(timer_id, None), # Remove from active display
            sys.stdout.write(f"\rTimer '{timer_id}' expired!{' '*50}\n"), # Clear line and print expiry
            sys.stdout.flush(),
            display_timers(), # Update display to remove the finished timer
            # Emit the event *after* printing completion
            timer_event_subject.on_next({
                'type': actions.Tools.TIMER_EXPIRED,
                'payload': {'timer_id': timer_id}
            })
        ],
        on_error=lambda e: [
             active_timers.pop(timer_id, None),
             print(f"\nError in timer '{timer_id}': {e}"),
             display_timers()
        ]
    )
