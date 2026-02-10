# maestro_v7.py - Agentic: Maestro decides which tools to use
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


# === TOOLS (functions Maestro can call) ===

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


# === DEFINE TOOLS FOR GEMINI ===
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

# Map function names to actual functions
tool_functions = {
    "list_disciplines": list_disciplines,
    "list_pages": list_pages,
    "get_page_knowledge": get_page_knowledge
}


# === MAESTRO - AGENTIC LOOP ===
def maestro(question):
    """Maestro decides which tools to use to answer the question."""
    
    print(f"Superintendent asks: {question}")
    print("Maestro is thinking...\n")
    
    model = genai.GenerativeModel(
        "gemini-2.0-flash",
        tools=tools,
        system_instruction="""You are Maestro, an AI assistant for construction superintendents.
You have access to tools to look up information about construction plans.
Use the tools to find the information needed to answer questions.
First list_disciplines to see what's available, then list_pages for relevant disciplines,
then get_page_knowledge for the specific pages that would have the answer."""
    )
    
    chat = model.start_chat()
    response = chat.send_message(question)
    
    # Agentic loop: keep processing until Maestro stops calling tools
    while response.candidates[0].content.parts:
        part = response.candidates[0].content.parts[0]
        
        # Check if Gemini wants to call a function
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
                print(f"  [Result] {result}\n")
            else:
                result = f"Unknown function: {func_name}"
            
            # Send result back to Gemini
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
            # No more function calls - Gemini is ready to answer
            break
    
    # Get final answer
    final_answer = response.candidates[0].content.parts[0].text
    return final_answer


# === TEST IT ===
print("=" * 60)
answer1 = maestro("Where are the electrical panels?")
print(f"\nMaestro says:\n{answer1}")

print("\n" + "=" * 60 + "\n")

answer2 = maestro("What's the tonnage of the AC units?")
print(f"\nMaestro says:\n{answer2}")

print
