import time
import threading
import reactivex as rx
from reactivex.subject import Subject
import argparse
import sys

from .src.pipeline.orchestrator import create_conversation_stream
from .src.timers.timer_manager import set_timer, set_test_mode
from .src.state import actions

from .src.llm.azure_openai_provider import openai_provider

def user_input_loop(user_input_subject: Subject):
    """
    Interactive input loop that reads user input from the terminal.
    Pushes each input as an ADD_USER_MESSAGE event into the user_input_subject.
    Typing 'exit' or 'quit' ends the loop.
    Also handles clearing the timer display line before taking input.
    """
    while True:
        try:
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()
            user_input = input("User: ")
            if user_input.lower() in ["exit", "quit"]:
                print("Exiting conversation.")
                user_input_subject.on_completed()
                break
            else:
                user_input_subject.on_next({
                    'type': actions.General.ADD_USER_MESSAGE,
                    'payload': user_input
                })
        except KeyboardInterrupt:
            print("\nExiting conversation.")
            user_input_subject.on_completed()
            break
        except EOFError:
            print("\nExiting conversation.")
            user_input_subject.on_completed()
            break


def main():
    parser = argparse.ArgumentParser(description='Interactive Cooking Assistant')
    parser.add_argument(
        '--test', 
        action='store_true', 
        help='Run in test mode (caps timer durations at 10s)'
    )
    parser.add_argument(
        '--recipe-name',
        type=str,
        help='Name of the recipe to initialize the assistant with'
    )
    args = parser.parse_args()

    set_test_mode(args.test)

    recipe_input_subject = Subject()
    user_input_subject = Subject()
    timer_event_subject = Subject()
    step_event_subject = Subject()
    conversation_response_stream = create_conversation_stream(
        recipe_input_subject, user_input_subject, timer_event_subject, step_event_subject
    )

    conversation_response_stream.subscribe(
        on_next=lambda response: print(f"\r{' '*80}\rAssistant: {response}"),
        on_error=lambda e: print(f"\nError: {e}"),
        on_completed=lambda: print("\nConversation complete")
    )

    print("Cooking Assistant Initialized.")

    if args.recipe_name:
        print(f"Initializing with recipe: {args.recipe_name}")
        recipe_input_subject.on_next({
            'type': actions.General.INIT_RECIPE,
            'payload': {'recipe_name': args.recipe_name}
        })
    else:
        print("No recipe specified. Type your request, or 'exit' to quit.")

    input_thread = threading.Thread(target=user_input_loop, args=(user_input_subject,))
    input_thread.daemon = True
    input_thread.start()

    input_thread.join()

    print("\nCleaning up...")
    recipe_input_subject.on_completed()
    user_input_subject.on_completed()
    timer_event_subject.on_completed()
    time.sleep(0.5)
    print("Done.")

if __name__ == '__main__':
    main()