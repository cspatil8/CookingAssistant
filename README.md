# Interactive Cooking Assistant

An AI-powered cooking assistant that guides you through recipes step by step, with features like timers, idle-time suggestions, and interactive Q&A.

## Features

- **Step-by-Step Guidance**: Clear, interactive instructions for each recipe step
- **Smart Timers**: Automatic timers for steps with durations
- **Idle-Time Suggestions**: Helpful tasks to do while waiting
- **Interactive Q&A**: Ask questions about cooking techniques or ingredients
- **Multi-Model Support**: Uses different LLM models for different tasks
- **Colorful CLI Interface**: Easy-to-read colored output

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/cooking-assistant.git
cd cooking-assistant
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file with your API keys:
```
OPENAI_API_KEY=your_openai_key_here
```

## Usage

### Basic Usage

1. Run the assistant:
```bash
python -m cooking_assistant
```

2. Paste your recipe text when prompted (press Ctrl+D or Ctrl+Z when done)

### Using a Recipe File

You can also provide a recipe file:
```bash
python -m cooking_assistant --recipe path/to/recipe.txt
```

### Testing Mode

To test without real timers:
```bash
python -m cooking_assistant --simulate
```

## Interactive Commands

- `done` or `next`: Move to the next step
- `repeat`: Repeat the current step
- `quit`: Exit the program
- Ask questions: Type any question about cooking (e.g., "What does julienne mean?")

## Example Recipe Format

The assistant can handle various recipe formats. Here's an example:

```
1. Preheat the oven to 350°F (175°C)
2. Mix flour, sugar, and eggs in a bowl
3. Bake for 30 minutes
4. Let cool for 10 minutes
```

## Development

The project uses a reactive architecture with RxPY for handling concurrent events. Key components:

- `RecipeParser`: Converts raw recipe text into structured steps
- `StepManager`: Manages recipe progression and state
- `TimerService`: Handles timing functionality
- `LLMService`: Manages language model interactions
- `CLIInterface`: Handles user input/output
- `CookingAssistant`: Main orchestrator

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - see LICENSE file for details 