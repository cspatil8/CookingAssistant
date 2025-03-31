import reactivex as rx
import reactivex.operators as ops
from typing import Dict, Any
from reactivex.subject import Subject

from ..llm.azure_openai_provider import openai_provider, Recipe
from ..state.state_subject import get_state, update_state
from ..state import actions
from ..timers.timer_manager import set_timer
from ..utils.response_parser import parse_and_trigger_timers

def build_prompt_from_state(state: Dict[str, Any]) -> str:
    """
    Build a prompt string from the conversation state's message history.
    
    Parameters:
        state: The current conversation state.
        
    Returns:
        A prompt string.
    """
    foo = "\n".join(f"{msg['role']}: {msg['text']}" for msg in state['messages'])
    return foo

def process_event(event: Dict[str, Any], timer_event_subject: Subject):
    """
    Process an event, potentially call LLM, parse response for timers, and update state.
    
    Parameters:
        event: A dict containing 'type' and 'payload'.
        timer_event_subject: The Subject for timer events.
    
    Returns:
        An observable that emits the cleaned LLM response or nothing if no LLM call was needed.
    """
    event_type = event.get('type')
    should_call_llm = False
    
    if event_type == actions.General.INIT_RECIPE:
        def updater(state):
            return {
                'recipe': event['payload']['recipe_name'],
                'current_step': 0,
                'messages': [{'role': 'system', 'text': f"Recipe initialized: {event['payload']['recipe_name']}"}],
                'timers': {}
            }
        update_state(updater)
        should_call_llm = True # Call LLM after initializing recipe
    
    elif event_type == actions.General.ADD_USER_MESSAGE:
        def updater(state):
            new_messages = state['messages'] + [{'role': 'user', 'text': event['payload']}]
            state['messages'] = new_messages
            return state
        update_state(updater)
        should_call_llm = True # Call LLM after user message
    
    elif event_type == actions.Tools.SET_TIMER:
        # This case might be redundant if timers are only set via LLM parsing
        # but we leave it for potential manual timer setting.
        def updater(state):
            state['timers'][event['payload']['timer_id']] = event['payload']['duration']
            return state
        update_state(updater)
        # No LLM call needed for setting a timer directly
    
    elif event_type == actions.Tools.TIMER_EXPIRED:
        def updater(state):
            timer_id = event['payload']['timer_id']
            system_text = f"Timer '{timer_id}' expired."
            # Optionally remove timer from state
            state.get('timers', {}).pop(timer_id, None) 
            new_messages = state['messages'] + [{'role': 'system', 'text': system_text}]
            state['messages'] = new_messages
            return state
        update_state(updater)
        # No LLM call needed for timer expiration
        # Optional: Could trigger an LLM call here to ask "What's next?"

    if should_call_llm:
        # Build prompt from the potentially updated state
        prompt = build_prompt_from_state(get_state())
        
        # Call LLM (this is blocking for now, consider async/await or Rx improvements later)
        llm_response_raw = openai_provider.send_prompt(
            prompt, 
            response_format="recipe" if event_type == actions.General.INIT_RECIPE else None
        )
        
        # Parse the response for timers and trigger them
        llm_response_cleaned = parse_and_trigger_timers(
            llm_response_raw,
            set_timer,           # Pass the actual set_timer function
            timer_event_subject  # Pass the subject instance
        )
        
        # Update state with the cleaned assistant message
        def add_assistant_msg_updater(state):
            new_messages = state['messages'] + [{'role': 'assistant', 'text': llm_response_cleaned}]
            state['messages'] = new_messages
            return state
        update_state(add_assistant_msg_updater)
        
        # Return the cleaned response in an observable
        return rx.of(llm_response_cleaned)
    else:
        # If no LLM call was made, return an empty observable
        return rx.empty()

def create_conversation_stream(recipe_input_subject: Subject,
                               user_input_subject: Subject,
                               timer_event_subject: Subject):
    """
    Merge multiple event sources, process them (now passing timer_event_subject), 
    and apply switch_latest.
    """
    conversation_event_stream = rx.merge(
        recipe_input_subject,
        user_input_subject,
        timer_event_subject # Timer events trigger state updates but not usually LLM calls directly
    )
    conversation_response_stream = conversation_event_stream.pipe(
        # Pass timer_event_subject to process_event
        ops.map(lambda event: process_event(event, timer_event_subject)), 
        ops.switch_latest()
    )
    return conversation_response_stream
