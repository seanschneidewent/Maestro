''' V1
# maestro.py - Version 1: The simplest harness

def maestro(question, project):
    """
    A superintendent asks Maestro a question about their project.
    Maestro thinks and responds.
    """
    print("Superintendent asks: " + question)
    print("Maestro is thinking about " + project["name"] + "...")
    
    # For now, Maestro is dumb - just echoes back
    return "I heard you ask about: " + question

# Define a project
my_project = {
    "name": "Downtown Office Tower",
    "plans": ["architectural drawings"],  
    "knowledge": "contains A101",
    "superintendent": "Sean"
}

# Ask Maestro something
answer = maestro("Where are the electrical panels?", my_project)
print("Maestro says: " + answer)

'''

''' V2
# maestro.py - Version 2: Maestro searches knowledge

def maestro(question, project):
    print("Superintendent asks: " + question)
    print("Maestro is thinking about " + project["name"] + "...")
    
    # Search the knowledge for relevant info
    knowledge = project["knowledge"]
    
    if "electrical" in question.lower():
        # Look for electrical info in knowledge
        if "E1" in knowledge or "electrical" in knowledge.lower():
            return "Found electrical info: " + knowledge
        else:
            return "No electrical drawings found in this project yet."
    else:
        return "I heard: " + question + " (but I'm still learning)"

# Define a project with more knowledge
my_project = {
    "name": "Downtown Office Tower",
    "plans": ["A101", "K101", "M101"],
    "knowledge": "E101 shows main electrical room on Level B1, panels in each floor's janitor closet",
    "superintendent": "Sean"
}

answer = maestro("Where are the electrical panels?", my_project)
print("Maestro says: " + answer)
'''

''' V3
# maestro.py - Version 3: Searchable knowledge

def maestro(question, project):
    print("Superintendent asks: " + question)
    print("Maestro is thinking about " + project["name"] + "...")
    
    # Search ALL knowledge items for matches
    matches = []
    for fact in project["knowledge"]:
        # Check if any word from the question appears in this fact
        for word in question.lower().split():
            if word in fact.lower() and len(word) > 3:  # skip tiny words
                matches.append(fact)
                break  # don't add same fact twice

    if len(matches) > 0:
        return "Found " + str(len(matches)) + " relevant facts:\n" + "\n".join(matches)
    else:
        return "Nothing found for: " + question
    

# Knowledge is now a LIST of facts
my_project = {
    "name": "Downtown Office Tower",
    "plans": ["A101", "E101", "M101", "M102"],
    "knowledge": [
        "E101 shows main electrical room on Level B1",
        "Electrical panels located in each floor's janitor closet",
        "M101 shows HVAC layout with cooler units on roof",
        "M102 specs: Carrier 50XC rooftop cooler, 20-ton capacity",
        "A101 shows lobby dimensions 40ft x 60ft"
    ],
    "superintendent": "Sean"
}

answer = maestro("Where are the electrical panels?", my_project)
print("Maestro says: " + answer)
print("\n---\n")
answer2 = maestro("cooler specs?", my_project)
print("Maestro says: " + answer2)
print("\n---\n")
answer3 = maestro("What's the tonnage of the AC units?", my_project)
print("Maestro says: " + answer3)
'''

''' V4
# maestro_v4.py - AI-powered answering with Gemini
import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load API key from .env file
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def maestro(question, project):
    """
    Maestro answers questions using AI + project knowledge.
    """
    print("Superintendent asks: " + question)
    print("Maestro is thinking about " + project["name"] + "...")
    
    # Build the prompt: give Gemini the knowledge, then ask the question
    knowledge_text = "\n".join(project["knowledge"])
    
    prompt = f"""You are Maestro, an AI assistant for construction superintendents.

Here is what you know about the project "{project["name"]}":

{knowledge_text}

The superintendent asks: {question}

Answer based ONLY on the knowledge above. Be concise and direct.
If the answer isn't in the knowledge, say "I don't have that information in the current plans."
"""
    
    # Ask Gemini
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    
    return response.text

# Step 1: Define disciplines as a list
disciplines = [
    "Architectural", 
    "Canopy", 
    "Civil", 
    "Kitchen", 
    "MEP", 
    "Structural", 
    "Vapor Mitigation", 
    "Unknown"
]

# Step 2: Each discipline has pages (dictionary of lists)
pages = {
    "Architectural": ["A101", "A102", "A201"],
    "MEP": ["M101", "M102", "E101", "P101"],
    "Structural": ["S101", "S102"],
    "Civil": ["C101"],
    "Kitchen": [],
    "Canopy": [],
    "Vapor Mitigation": [],
    "Unknown": []
}

# Step 3: Function to get pages from a discipline
def get_pages(discipline):
    if discipline in pages:
        return pages[discipline]
    else:
        return "error: discipline not found"
    
# Test it
print(get_pages("MEP"))        # ["M101", "M102", "E101", "P101"]
print(get_pages("Architectural"))  # ["A101", "A102", "A201"]
print(get_pages("Fake"))       # error: discipline not found

# Project with knowledge
my_project = {
    "name": "CFA Love Field FSU",
    "disciplines": {disciplines},
    "pages": ["A101", "E101", "M101", "M102"],
    "knowledge": [
        "E101 shows main electrical room on Level B1",
        "Electrical panels located in each floor's janitor closet",
        "M101 shows HVAC layout with cooler units on roof",
        "M102 specs: Carrier 50XC rooftop cooler, 20-ton capacity",
        "A101 shows lobby dimensions 40ft x 60ft"
    ],
    "superintendent": "Sean"
}

# Test it
answer = maestro("Where are the electrical panels?", my_project)
print("\nMaestro says:\n" + answer)

print("\n---\n")

answer2 = maestro("What's the tonnage of the AC units?", my_project)
print("\nMaestro says:\n" + answer2)
'''

''' V5
# maestro_v5.py - Page routing
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Discipline → Pages structure
pages = {
    "Architectural": ["A101 - Floor Plan", "A102 - Reflected Ceiling", "A201 - Elevations"],
    "MEP": ["M101 - HVAC Layout", "M102 - HVAC Specs", "E101 - Electrical Plan", "P101 - Plumbing"],
    "Structural": ["S101 - Foundation", "S102 - Framing"],
    "Civil": ["C101 - Site Plan"],
}

def find_relevant_pages(question):
    """Ask Maestro which pages are most likely to have the answer."""
    
    # Build a text version of the structure
    structure_text = ""
    for discipline, page_list in pages.items():
        structure_text += f"\n{discipline}:\n"
        for page in page_list:
            structure_text += f"  - {page}\n"
    
    prompt = f"""You are Maestro, an AI for construction superintendents.

Here are the available plan sheets organized by discipline:
{structure_text}

The superintendent asks: {question}

Which page(s) would most likely contain the answer? 
Return ONLY the page names, one per line. If unsure, pick your best guess.
"""
    
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    return response.text

# Test it
print("Question: Where are the electrical panels?\n")
result = find_relevant_pages("Where are the electrical panels?")
print("Maestro says check:\n" + result)

print("\n---\n")

print("Question: What's the roof structure?\n")
result2 = find_relevant_pages("What's the roof structure?")
print("Maestro says check:\n" + result2)
'''

''' V6
# maestro_v6.py - Full loop: Route → Lookup → Answer
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# === PROJECT DATA ===
# Nested structure: Discipline → Page → Knowledge
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


# === STEP 1: ROUTE - Find relevant pages ===
def find_relevant_pages(question, project):
    """Ask Maestro which pages are most likely to have the answer."""
    
    # Build text version of the structure (just disciplines and page names)
    structure_text = ""
    for discipline, pages in project["disciplines"].items():
        structure_text += f"\n{discipline}:\n"
        for page_name in pages.keys():
            structure_text += f"  - {page_name}\n"
    
    prompt = f"""You are Maestro, an AI for construction superintendents.

Here are the available plan sheets for "{project["name"]}":
{structure_text}

The superintendent asks: {question}

Which page(s) would most likely contain the answer?
Return ONLY the page names, one per line. Pick 1-2 most relevant pages.
"""
    
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    return response.text.strip().split("\n")


# === STEP 2: LOOKUP - Get knowledge from those pages ===
def get_knowledge_from_pages(page_names, project):
    """Look up knowledge from the specified pages."""
    
    all_knowledge = []
    
    for discipline, pages in project["disciplines"].items():
        for page_name, page_data in pages.items():
            # Check if this page matches any of the requested pages
            for requested in page_names:
                if requested.strip() in page_name or page_name in requested.strip():
                    all_knowledge.extend(page_data["knowledge"])
    
    return all_knowledge


# === STEP 3: ANSWER - Use knowledge to answer ===
def answer_question(question, knowledge, project):
    """Answer the question using the retrieved knowledge."""
    
    knowledge_text = "\n".join(knowledge)
    
    prompt = f"""You are Maestro, an AI for construction superintendents.

Project: {project["name"]}

Here is the relevant knowledge from the plans:
{knowledge_text}

The superintendent asks: {question}

Answer based ONLY on the knowledge above. Be concise and direct.
If the answer isn't in the knowledge, say "I don't have that information."
"""
    
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    return response.text


# === FULL LOOP: Route → Lookup → Answer ===
def maestro(question, project):
    """The complete Maestro flow."""
    
    print(f"Superintendent asks: {question}")
    print("Maestro is thinking...\n")
    
    # Step 1: Route
    print("Step 1: Finding relevant pages...")
    relevant_pages = find_relevant_pages(question, project)
    print(f"  -> Checking: {relevant_pages}\n")
    
    # Step 2: Lookup
    print("Step 2: Looking up knowledge...")
    knowledge = get_knowledge_from_pages(relevant_pages, project)
    print(f"  -> Found {len(knowledge)} facts\n")
    
    # Step 3: Answer
    print("Step 3: Answering...")
    answer = answer_question(question, knowledge, project)
    
    return answer


# === TEST IT ===
print("=" * 50)
answer1 = maestro("Where are the electrical panels?", project)
print(f"\nMaestro says:\n{answer1}")

print("\n" + "=" * 50 + "\n")

answer2 = maestro("What's the tonnage of the AC units?", project)
print(f"\nMaestro says:\n{answer2}")

print("\n" + "=" * 50 + "\n")

answer3 = maestro("How tall are the ceilings in the lobby?", project)
print(f"\nMaestro says:\n{answer3}")
'''


