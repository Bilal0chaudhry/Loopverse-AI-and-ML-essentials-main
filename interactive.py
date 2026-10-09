import sys
import json
from pathlib import Path

# Add src to python path so it can find assistant
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from assistant import ask

print("=======================================")
print("Lahore Smog Assistant Interactive CLI")
print("Type 'exit' or 'quit' to stop.")
print("=======================================")

while True:
    try:
        q = input("\nYour Question: ")
        if q.strip().lower() in ['exit', 'quit']:
            print("Goodbye!")
            break
        if not q.strip():
            continue
            
        print("\nThinking...")
        result = ask(q)
        print("-" * 40)
        print(f"ANSWER:\n{result['answer']}")
        print(f"\nSOURCES CITED: {', '.join(result['sources']) if result['sources'] else 'None'}")
        print(f"FORECAST CALLED: {result['forecast_called']}")
        print("-" * 40)
        
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye!")
        break
