import re
from reactivex.subject import Subject
from typing import Callable
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the timer marker pattern: [TIMER: <duration_seconds> <timer_id>]
# - <duration_seconds>: Integer
# - <timer_id>: String without spaces (use underscores)
TIMER_PATTERN = re.compile(r"\[TIMER:\s*(\d+)\s+([a-zA-Z0-9_]+)\s*\]")

def parse_and_trigger_timers(
    response_text: str,
    set_timer_func: Callable[[str, int, Subject], None],
    timer_event_subject: Subject
) -> str:
    """
    Parses the LLM response text for timer markers, triggers timers,
    and returns the text with markers removed.

    Args:
        response_text: The text response from the LLM.
        set_timer_func: A callable reference to the set_timer function.
        timer_event_subject: The RxPy Subject instance for timer events.

    Returns:
        The response text with the timer markers removed.
    """
    matches = TIMER_PATTERN.finditer(response_text)
    processed_text = response_text
    offset = 0 # Keep track of index changes due to replacements

    for match in matches:
        try:
            duration_str = match.group(1)
            timer_id = match.group(2)
            duration = int(duration_str)

            if duration <= 0:
                logging.warning(f"Ignoring timer marker with non-positive duration: {match.group(0)}")
                continue

            logging.info(f"Found timer marker: ID='{timer_id}', Duration={duration}s. Triggering timer.")
            # Call the actual set_timer function
            set_timer_func(timer_id, duration, timer_event_subject)

            # Remove the marker from the text shown to the user
            # Adjust indices based on previous removals
            start_index = match.start() - offset
            end_index = match.end() - offset
            processed_text = processed_text[:start_index] + processed_text[end_index:]
            offset += (match.end() - match.start()) # Add the length of the removed marker

        except ValueError:
            logging.error(f"Invalid duration found in timer marker: {match.group(0)}. Skipping.")
        except Exception as e:
            logging.error(f"Error processing timer marker {match.group(0)}: {e}")

    return processed_text

# Example Usage (conceptual - needs integration into your main app flow)
# if __name__ == '__main__':
#     from src.timers.timer_manager import set_timer
#     from reactivex.subject import Subject as RxSubject
#
#     # This subject would be managed centrally in your application
#     test_subject = RxSubject()
#
#     # Example callback to see timer events
#     test_subject.subscribe(lambda event: print(f"EVENT RECEIVED: {event}"))
#
#     llm_response_with_timers = "Okay, first preheat your oven. Then, boil the pasta for 10 minutes [TIMER: 600 pasta_boiling]. While it boils, sauté the onions for 5 minutes [TIMER: 300 onion_sauté]. Let the sauce simmer for 20 minutes [TIMER: 1200 sauce_simmer]."
#     llm_response_no_timers = "Just mix the ingredients together."
#     llm_response_invalid_timer = "Cook for a bit [TIMER: abc invalid_id] then serve."
#
#     print("--- Processing response with timers ---")
#     cleaned_text = parse_and_trigger_timers(llm_response_with_timers, set_timer, test_subject)
#     print(f"Cleaned Text: '{cleaned_text}'")
#
#     print("\n--- Processing response without timers ---")
#     cleaned_text_no_timer = parse_and_trigger_timers(llm_response_no_timers, set_timer, test_subject)
#     print(f"Cleaned Text: '{cleaned_text_no_timer}'")
#
#     print("\n--- Processing response with invalid timer ---")
#     cleaned_text_invalid = parse_and_trigger_timers(llm_response_invalid_timer, set_timer, test_subject)
#     print(f"Cleaned Text: '{cleaned_text_invalid}'")
#
#     # Keep running for a bit to see potential timer expirations (if durations were short)
#     # In a real app, the event loop would handle this.
#     print("\nWaiting for potential timer events...")
#     import time
#     # time.sleep(5) # Example short wait
#
#     # Note: The set_timer uses rx.timer which schedules work on a background thread usually,
#     # so the main thread might exit before timers fire without proper event loop management.
#     # The example above mainly demonstrates the parsing and triggering logic. 