import re
from reactivex.subject import Subject
from typing import Callable, Dict, List, Optional, Tuple, Union
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define marker patterns:
# - Timer: [TIMER: <duration_seconds> <timer_id>]
#   - <duration_seconds>: Integer
#   - <timer_id>: String without spaces (use underscores)
# - Step: [STEP: <step_index>]
#   - <step_index>: Integer (zero-based)
TIMER_PATTERN = re.compile(r'\[TIMER:\s*(\d+)\s+([^\]]+)\]')
STEP_PATTERN = re.compile(r'\[STEP:\s*(\d+)\]')

# Define return types for clarity
TimerInfo = Dict[str, Union[str, int]]
ParseResult = Tuple[str, Dict[str, Optional[Union[List[TimerInfo], int]]]]

def parse_llm_response(response_text: str) -> ParseResult:
    """
    Parses the LLM response text for timer and step markers,
    removes the markers, and returns the cleaned text along with
    extracted timer information and the target step index.

    Args:
        response_text: The text response from the LLM.

    Returns:
        A tuple containing:
        - The response text with markers removed.
        - A dictionary with keys:
            - 'timers': A list of dictionaries, each with 'id' and 'duration'.
            - 'step_update': The integer step index if a step marker was found, else None.
    """
    processed_text = response_text
    extracted_timers: List[TimerInfo] = []
    extracted_step: Optional[int] = None
    offset = 0 # Keep track of index changes due to marker removals

    # Process Timer Markers
    timer_matches = list(TIMER_PATTERN.finditer(response_text))
    for match in timer_matches:
        try:
            duration_str = match.group(1)
            timer_id = match.group(2)
            duration = int(duration_str)

            if duration <= 0:
                logging.warning(f"Ignoring timer marker with non-positive duration: {match.group(0)}")
                continue

            logging.info(f"Found timer marker: ID='{timer_id}', Duration={duration}s.")
            extracted_timers.append({"id": timer_id, "duration": duration})

            # Remove the marker from the text
            start_index = match.start() - offset
            end_index = match.end() - offset
            processed_text = processed_text[:start_index] + processed_text[end_index:]
            offset += (match.end() - match.start())

        except ValueError:
            logging.error(f"Invalid duration found in timer marker: {match.group(0)}. Skipping.")
        except Exception as e:
            logging.error(f"Error processing timer marker {match.group(0)}: {e}")

    # Reset offset for step processing (relative to potentially modified text)
    current_offset = 0
    temp_processed_text = processed_text # Work on a copy for step removal
    
    # Process Step Markers (find only the *last* one if multiple exist)
    step_match = None
    for match in STEP_PATTERN.finditer(processed_text): # Search in text already cleaned of timers
        step_match = match

    if step_match:
        try:
            step_index_str = step_match.group(1)
            step_index = int(step_index_str)
            
            if step_index < 0:
                 logging.warning(f"Ignoring step marker with negative index: {step_match.group(0)}")
            else:
                logging.info(f"Found step marker: Index={step_index}.")
                extracted_step = step_index

                # Remove the marker from the text
                # Offset calculation here is tricky because timer removals shifted indices.
                # Instead, we rebuild the string by removing the *last* step marker found
                # from the timer-cleaned string.
                start_index = step_match.start()
                end_index = step_match.end()
                # Apply removal on the text that already had timers removed
                processed_text = processed_text[:start_index] + processed_text[end_index:]

        except ValueError:
            logging.error(f"Invalid index found in step marker: {step_match.group(0)}. Skipping.")
        except Exception as e:
            logging.error(f"Error processing step marker {step_match.group(0)}: {e}")
            
    return processed_text, {"timers": extracted_timers, "step_update": extracted_step}

# Example Usage (conceptual - update to reflect new return type)
# if __name__ == '__main__':
#     # Example text containing both markers
#     llm_response_combined = "Okay, let's move on. Simmer the sauce for 15 minutes [TIMER: 900 sauce_simmer]. Then you'll add the pasta. [STEP: 2] Remember to stir occasionally."
#     llm_response_step_only = "Great, you finished chopping. Now preheat the oven. [STEP: 1]"
#     llm_response_timer_only = "Boil water for 10 minutes [TIMER: 600 water_boil]."
#     llm_response_invalid_step = "Do something [STEP: -1] then something else."
#     llm_response_no_markers = "Just mix everything together."
# 
#     print("--- Processing combined response ---")
#     cleaned_text, commands = parse_llm_response(llm_response_combined)
#     print(f"Cleaned Text: '{cleaned_text}'")
#     print(f"Commands: {commands}")
# 
#     print("\n--- Processing step-only response ---")
#     cleaned_text, commands = parse_llm_response(llm_response_step_only)
#     print(f"Cleaned Text: '{cleaned_text}'")
#     print(f"Commands: {commands}")
# 
#     print("\n--- Processing timer-only response ---")
#     cleaned_text, commands = parse_llm_response(llm_response_timer_only)
#     print(f"Cleaned Text: '{cleaned_text}'")
#     print(f"Commands: {commands}")
# 
#     print("\n--- Processing invalid step response ---")
#     cleaned_text, commands = parse_llm_response(llm_response_invalid_step)
#     print(f"Cleaned Text: '{cleaned_text}'")
#     print(f"Commands: {commands}")
# 
#     print("\n--- Processing no markers response ---")
#     cleaned_text, commands = parse_llm_response(llm_response_no_markers)
#     print(f"Cleaned Text: '{cleaned_text}'")
#     print(f"Commands: {commands}") 