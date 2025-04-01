import reactivex as rx
import reactivex.operators as ops
from typing import Dict, Any
from reactivex.subject import Subject
import json

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
    step_info = f"\nCurrent Step: {state.get('current_step', 'Not started')}"
    message_history = "\n".join(f"{msg['role']}: {msg['text']}" for msg in state['messages'])
    return message_history + step_info

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
    llm_response_format = None
    prompt_override = None
    
    if event_type == actions.General.INIT_RECIPE:
        recipe_name_request = event['payload']['recipe_name']
        prompt_override = f"Provide the recipe for {recipe_name_request}"
        llm_response_format = Recipe
        
        def initial_updater(state):
            return {
                'recipe': None,
                'current_step': 0,
                'messages': [{'role': 'system', 'text': f"Loading recipe for {recipe_name_request}..."}],
                'timers': {}
            }
        update_state(initial_updater)
        should_call_llm = True
    
    elif event_type == actions.General.ADD_USER_MESSAGE:
        def updater(state):
            new_messages = state['messages'] + [{'role': 'user', 'text': event['payload']}]
            state['messages'] = new_messages
            return state
        update_state(updater)
        should_call_llm = True
        llm_response_format = None
    
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
        current_state = get_state()
        prompt = prompt_override if prompt_override else build_prompt_from_state(current_state)
        
        llm_response_raw = openai_provider.send_prompt(
            prompt,
            response_format=llm_response_format
        )

        if event_type == actions.General.INIT_RECIPE:
            if isinstance(llm_response_raw, Recipe):
                recipe_obj = llm_response_raw
                def update_recipe_and_message(state):
                    state['recipe'] = recipe_obj.model_dump()
                    state['messages'] = [{
                        'role': 'system',
                        'text': f"The current recipe is:\n{json.dumps(recipe_obj.model_dump(), indent=2)}"
                    }]
                    return state
                update_state(update_recipe_and_message)
                
                confirmation_msg = f"Recipe '{recipe_obj.recipe_name}' loaded."
                return rx.of(confirmation_msg)
            else:
                error_msg = f"Error: Failed to load recipe. Response: {llm_response_raw}"
                def add_error_msg_updater(state):
                     state['messages'] = state['messages'] + [{'role': 'system', 'text': error_msg}]
                     return state
                update_state(add_error_msg_updater)
                return rx.of(error_msg)

        elif isinstance(llm_response_raw, str):
            llm_response_cleaned = parse_and_trigger_timers(
                llm_response_raw,
                set_timer,
                timer_event_subject
            )
            
            def add_assistant_msg_updater(state):
                new_messages = state['messages'] + [{'role': 'assistant', 'text': llm_response_cleaned}]
                state['messages'] = new_messages
                return state
            update_state(add_assistant_msg_updater)
            
            return rx.of(llm_response_cleaned)
        else:
            error_msg = f"Error: Unexpected response type from LLM: {type(llm_response_raw)}"
            def add_error_msg_updater(state):
                 state['messages'] = state['messages'] + [{'role': 'system', 'text': error_msg}]
                 return state
            update_state(add_error_msg_updater)
            return rx.of(error_msg)

    else:
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
        timer_event_subject
    )
    conversation_response_stream = conversation_event_stream.pipe(
        ops.map(lambda event: process_event(event, timer_event_subject)), 
        ops.switch_latest()
    )
    return conversation_response_stream
