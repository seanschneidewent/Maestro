# tools.py - Maestro's tool definitions and functions
# What Maestro can DO — the actions available to him.
from knowledge_v12 import project


# === TOOL FUNCTIONS ===
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


# === TOOL DECLARATIONS (what Gemini sees) ===
tool_declarations = [
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
            },
            {
                "name": "learn",
                "description": "Learn from feedback. Use when the superintendent corrects your behavior, tells you to do something differently, or teaches you something about how to work. This permanently updates your experience.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "learning_mission": {
                            "type": "string",
                            "description": "What to learn (e.g., 'Don't ask which discipline to check — just go look autonomously')"
                        }
                    },
                    "required": ["learning_mission"]
                }
            }
        ]
    }
]

# === TOOL FUNCTION MAP (name → function) ===
tool_functions = {
    "list_disciplines": list_disciplines,
    "list_pages": list_pages,
    "get_page_knowledge": get_page_knowledge,
    # "learn" is added by the engine since it needs access to experience
}
