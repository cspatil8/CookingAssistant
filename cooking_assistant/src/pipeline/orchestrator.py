import reactivex as rx
import reactivex.operators as ops
from typing import Dict, Any
from reactivex.subject import Subject
import json

from ..llm.azure_openai_provider import openai_provider, Recipe
from ..state.state_subject import get_state, update_state
from ..state import actions
from ..timers.timer_manager import set_timer
from ..utils.response_parser import parse_llm_response

def build_prompt_from_state(state: Dict[str, Any]) -> str:
    """
    Build a prompt string from the conversation state's message history.
    Includes the current step number in the prompt context.
    
    Parameters:
        state: The current conversation state.
        
    Returns:
        A prompt string.
    """
    # Add current step info to the prompt context for the LLM
    current_step_index = state.get('current_step', 0)
    step_info = f"\n[Current Step Index: {current_step_index}]"
    
    # Include recipe instructions if available and relevant
    recipe_context = ""
    if state.get('recipe') and isinstance(state['recipe'].get('instructions'), list):
        instructions = state['recipe']['instructions']
        if 0 <= current_step_index < len(instructions):
            recipe_context += f"\n[Current Instruction: {instructions[current_step_index]}]"
        if current_step_index > 0 and len(instructions) > 1:
             recipe_context += f"\n[Previous Instruction: {instructions[current_step_index-1]}]"
        if current_step_index < len(instructions) - 1:
             recipe_context += f"\n[Next Instruction: {instructions[current_step_index+1]}]"

    message_history = "\n".join(f"{msg['role']}: {msg['text']}" for msg in state['messages'])
    return message_history + recipe_context + step_info

def process_event(event: Dict[str, Any], timer_event_subject: Subject):
    """
    Process an event, potentially call LLM, parse response for timers/steps, and update state.
    
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
            # Reset state for a new recipe
            return {
                'recipe': None,
                'current_step': 0, # Start at step 0
                'messages': [{'role': 'system', 'text': f"Loading recipe for {recipe_name_request}..."}],
                'timers': {}
            }
        update_state(initial_updater)
        should_call_llm = True
    
    elif event_type == actions.General.ADD_USER_MESSAGE:
        def updater(state):
            new_messages = state['messages'] + [{'role': 'user', 'text': event['payload']}]
            # Limit message history length if needed (e.g., keep last N messages)
            # MAX_HISTORY = 20
            # state['messages'] = new_messages[-MAX_HISTORY:]
            state['messages'] = new_messages
            return state
        update_state(updater)
        should_call_llm = True
        llm_response_format = None # General conversation
    
    elif event_type == actions.Tools.SET_TIMER:
        # This action type is now primarily triggered internally after parsing
        # We might not need this elif block anymore if no external source sets timers.
        # However, let's keep it for now for potential future use/debugging.
        timer_id = event['payload']['timer_id']
        duration = event['payload']['duration']
        print(f"Orchestrator: Directly setting timer {timer_id} for {duration}s")
        # This might lead to double setting if called externally AND parsed from LLM.
        # Consider removing direct calls via this action type.
        set_timer(timer_id, duration, timer_event_subject)
        # No state update needed here for the timer itself, just triggering.
        # No LLM call needed.
        return rx.empty() # Explicitly return empty observable
    
    elif event_type == actions.Tools.TIMER_EXPIRED:
        def updater(state):
            timer_id = event['payload']['timer_id']
            system_text = f"Timer '{timer_id}' expired."
            # Remove timer from state might not be necessary if state tracks active timers
            # state.get('timers', {}).pop(timer_id, None) 
            new_messages = state['messages'] + [{'role': 'system', 'text': system_text}]
            state['messages'] = new_messages
            # Optionally update timers state if needed
            if 'timers' in state and timer_id in state['timers']:
                 del state['timers'][timer_id] # Remove expired timer from conceptual state
            return state
        update_state(updater)
        # No LLM call needed for timer expiration itself.
        # Optional: Could trigger an LLM call here to ask "What's next?" based on expiration.
        return rx.empty() # Explicitly return empty observable

    # We don't need a handler for UPDATE_STEP because the step is updated 
    # directly within the LLM response processing block below.

    if should_call_llm:
        current_state = get_state()
        prompt = prompt_override if prompt_override else build_prompt_from_state(current_state)
        
        print(f"\n--- Sending Prompt to LLM ---\n{prompt}\n-----------------------------")

        llm_response_raw = openai_provider.send_prompt(
            prompt,
            response_format=llm_response_format
        )
        
        print(f"\n--- Raw LLM Response ---\n{llm_response_raw}\n--------------------------")

        if event_type == actions.General.INIT_RECIPE:
            if isinstance(llm_response_raw, Recipe):
                recipe_obj = llm_response_raw
                def update_recipe_and_message(state):
                    state['recipe'] = recipe_obj.model_dump()
                    # Start conversation with the first instruction or recipe overview
                    first_instruction = recipe_obj.instructions[0] if recipe_obj.instructions else "No instructions provided."
                    state['messages'] = [{
                        'role': 'assistant',
                        'text': f"OK. I have the recipe for '{recipe_obj.recipe_name}'. Let's start!\n\nStep 1: {first_instruction}"
                    }]
                    state['current_step'] = 0 # Explicitly set to 0
                    return state
                update_state(update_recipe_and_message)
                
                # The message to display/emit from this observable
                first_message_text = f"OK. I have the recipe for '{recipe_obj.recipe_name}'. Let's start!\n\nStep 1: {recipe_obj.instructions[0] if recipe_obj.instructions else 'No instructions provided.'}"
                return rx.of(first_message_text)
            else:
                error_msg = f"Error: Failed to load recipe. Response: {llm_response_raw}"
                def add_error_msg_updater(state):
                     state['messages'] = state['messages'] + [{'role': 'system', 'text': error_msg}]
                     return state
                update_state(add_error_msg_updater)
                return rx.of(error_msg)

        elif isinstance(llm_response_raw, str):
            # Parse the response for markers (timers, steps)
            llm_response_cleaned, commands = parse_llm_response(llm_response_raw)
            
            print(f"\n--- Parsed Commands ---\n{commands}\n-------------------------")
            print(f"\n--- Cleaned LLM Response ---\n{llm_response_cleaned}\n----------------------------")

            # Trigger any timers found
            timers_to_set = commands.get('timers', [])
            for timer_info in timers_to_set:
                print(f"Orchestrator: Triggering timer '{timer_info['id']}' for {timer_info['duration']}s")
                set_timer(timer_info['id'], timer_info['duration'], timer_event_subject)
            
            # Update state with assistant message and potential step change
            def add_assistant_msg_and_update_step_updater(state):
                # Add the cleaned message
                new_messages = state['messages'] + [{'role': 'assistant', 'text': llm_response_cleaned}]
                state['messages'] = new_messages
                
                # Update the current step if indicated by the LLM
                step_update_index = commands.get('step_update')
                if step_update_index is not None:
                    print(f"Orchestrator: Updating current step to {step_update_index}")
                    state['current_step'] = step_update_index
                    
                # Update active timers conceptually in state if needed (optional)
                # for timer_info in timers_to_set:
                #    state.setdefault('timers', {})[timer_info['id']] = timer_info['duration']
                    
                return state
            update_state(add_assistant_msg_and_update_step_updater)
            
            # Return the cleaned text to be displayed/emitted
            return rx.of(llm_response_cleaned) 
        else:
            # Handle unexpected non-string, non-Recipe response
            error_msg = f"Error: Unexpected response type from LLM: {type(llm_response_raw)}"
            def add_error_msg_updater(state):
                 state['messages'] = state['messages'] + [{'role': 'system', 'text': error_msg}]
                 return state
            update_state(add_error_msg_updater)
            return rx.of(error_msg)

    else:
        # If no LLM call was needed (e.g., timer expired), return empty observable
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
