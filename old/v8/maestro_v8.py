# maestro_v8.py - Interactive chat with Maestro
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# === PROJECT DATA ===
project = {
    "name": "Downtown Office Tower",
    "disciplines": {
        "Architectural": {
            "A101 - Floor Plan": {
                "knowledge": [
                    "Lobby dimensions 40ft x 60ft",
                    "Main entrance faces north on Main Street",
                    "Reception desk centered on east wall"
                ]
            },
            "A102 - Reflected Ceiling": {
                "knowledge": [
                    "9ft ceiling height in offices",
                    "12ft ceiling in lobby",
                    "Drop ceiling grid throughout"
                ]
            }
        },
        "MEP": {
            "E101 - Electrical Plan": {
                "knowledge": [
                    "Main electrical room on Level B1",
                    "Panels in each floor's janitor closet",
                    "200A service per floor"
                ]
            },
            "M101 - HVAC Layout": {
                "knowledge": [
                    "Rooftop units on north side of building",
                    "Ductwork runs above ceiling grid",
                    "Four zones per floor"
                ]
            },
            "M102 - HVAC Specs": {
                "knowledge": [
                    "Carrier 50XC rooftop cooler",
                    "20-ton capacity per unit",
                    "R-410A refrigerant"
                ]
            }
        },
        "Structural": {
            "S101 - Foundation": {
                "knowledge": [
                    "Concrete slab on grade",
                    "24-inch deep footings",
                    "Rebar #5 at 12 inches on center"
                ]
            },
            "S102 - Framing": {
                "knowledge": [
                    "Steel frame construction",
                    "W12x26 beams typical",
                    "Roof joists at 24 inches on center"
                ]
            }
        }
    }
}


# === TOOLS ===
def list_disciplines():
    """List all disciplines in the project."""
    return list(project["disciplines"].keys())

def list_pages(discipline: str):
    """List all pages within a discipline."""
    if discipline in project["disciplines"]:
        return list(project["disciplines"][discipline].keys())
    return f"Discipline '{discipline}' not found"

def get_page_knowledge(page_name: str):
    """Get the knowledge from a specific page."""
    for discipline, pages in project["disciplines"].items():
        for name, data in pages.items():
            if page_name.lower() in name.lower() or name.lower() in page_name.lower():
                return data["knowledge"]
    return f"Page '{page_name}' not found"


# === TOOL CONFIG ===
tools = [
    {
        "function_declarations": [
            {
                "name": "list_disciplines",
                "description": "List all disciplines (like Architectural, MEP, Structural) in the project",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "list_pages", 
                "description": "List all pages within a specific discipline",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "discipline": {
                            "type": "string",
                            "description": "The discipline name (e.g., 'MEP', 'Architectural')"
                        }
                    },
                    "required": ["discipline"]
                }
            },
            {
                "name": "get_page_knowledge",
                "description": "Get detailed knowledge from a specific page",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_name": {
                            "type": "string", 
                            "description": "The page name (e.g., 'E101', 'M102 - HVAC Specs')"
                        }
                    },
                    "required": ["page_name"]
                }
            }
        ]
    }
]

tool_functions = {
    "list_disciplines": list_disciplines,
    "list_pages": list_pages,
    "get_page_knowledge": get_page_knowledge
}


# === PROCESS ONE MESSAGE (handles tool calls) ===
def process_message(chat, message):
    """Send a message and handle any tool calls until we get a final answer."""
    
    response = chat.send_message(message)
    
    # Loop while Gemini wants to call tools
    while response.candidates[0].content.parts:
        part = response.candidates[0].content.parts[0]
        
        if hasattr(part, 'function_call') and part.function_call:
            func_call = part.function_call
            func_name = func_call.name
            func_args = dict(func_call.args) if func_call.args else {}
            
            print(f"  [Tool] {func_name}({func_args})")
            
            # Execute the function
            if func_name in tool_functions:
                if func_args:
                    result = tool_functions[func_name](**func_args)
                else:
                    result = tool_functions[func_name]()
            else:
                result = f"Unknown function: {func_name}"
            
            # Send result back
            response = chat.send_message(
                genai.protos.Content(
                    parts=[genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=func_name,
                            response={"result": str(result)}
                        )
                    )]
                )
            )
        else:
            break
    
    return response.candidates[0].content.parts[0].text


# === INTERACTIVE CHAT LOOP ===
def main():
    print("=" * 60)
    print("  MAESTRO - Construction Plan Assistant")
    print(f"  Project: {project['name']}")
    print("=" * 60)
    print("Type your questions. Type 'quit' to exit.\n")
    
    # Create model and start chat (persists across questions)
    model = genai.GenerativeModel(
        "gemini-2.0-flash",
        tools=tools,
        system_instruction="""You are Maestro, an AI assistant for construction superintendents.
You help answer questions about construction plans.
Use the available tools to look up information.
Be concise and direct in your answers."""
    )
    
    chat = model.start_chat()
    
    # The loop - keeps going until user types 'quit'
    while True:
        user_input = input("\nYou: ").strip()
        
        if user_input.lower() == 'quit':
            print("\nMaestro: See you on site, boss.")
            break
        
        if not user_input:
            continue
        
        print("\nMaestro is thinking...")
        answer = process_message(chat, user_input)
        print(f"\nMaestro: {answer}")


if __name__ == "__main__":
    main()
