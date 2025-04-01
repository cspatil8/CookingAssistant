import reactivex as rx
from reactivex.subject import BehaviorSubject
from typing import Callable, Dict, Any
import json  # Added import

# Define the initial conversation state.
initial_state: Dict[str, Any] = {
    'recipe': None,
    'current_step': 0,
    'messages': [],
    'timers': {}
}

# Create a BehaviorSubject to hold the conversation state.
conversation_state_subject: BehaviorSubject = BehaviorSubject(initial_state)

def get_state() -> Dict[str, Any]:
    """Return the current conversation state."""
    return conversation_state_subject.value

def update_state(updater: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
    """
    Applies an updater function to the current state and pushes the new state.
    Logs the new state to state_log.jsonl.
    
    Parameters:
        updater: A function that takes the current state dict and returns an updated state dict.
    
    Returns:
        The new state.
    """
    current_state = get_state()
    new_state = updater(current_state)

    print_state(new_state)

    conversation_state_subject.on_next(new_state)
    return new_state

def print_state(state: Dict[str, Any]):
        # Log the new state to a file
    try:
        with open('state_log.jsonl', 'a') as f:
            # Convert state to JSON string, handling potential non-serializable types gracefully
            log_entry = json.dumps(state, default=str) 
            f.write(log_entry + '\n')
    except Exception as e:
        print(f"Error writing state to log file: {e}") # Basic error handling
