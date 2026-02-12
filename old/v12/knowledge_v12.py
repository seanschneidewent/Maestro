# knowledge.py - Maestro's project knowledge
# This is the project data that Maestro searches through.
# Separate from the engine (maestro) and identity (experience).

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
