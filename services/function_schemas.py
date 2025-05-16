# app/services/function_schemas.py
# JSON schema definitions for each section's function calling

SECTION_FUNCTIONS = {
    # 'Deckblatt' section for Deklarationsanalyse
    "Deckblatt": {
        "name": "fill_deckblatt",
        "description": "Populate the Deckblatt (cover page) section for the document.",
        "parameters": {
            "type": "object",
            "properties": {
                "Projekt": {"type": "string", "description": "Project name or identifier"},
                "Auftraggeber": {"type": "string", "description": "Client name"},
                "Dienstleistungsnummer": {"type": "string", "description": "Service number"},
                "Probenahmedatum": {"type": "string", "description": "Date of sampling"}
            },
            "required": []
        }
    },

    # 'Stellungnahme' section for Deklarationsanalyse
    "Stellungnahme": {
        "name": "fill_stellungnahme",
        "description": "Populate the Stellungnahme (statement) section with assessment information.",
        "parameters": {
            "type": "object",
            "properties": {
                "Probenahmeprotokoll": {"type": "string", "description": "Sampling protocol details"},
                "Laborberichte": {"type": "string", "description": "Laboratory report summary"},
                "Auswertung": {"type": "string", "description": "Evaluation and conclusions"}
            },
            "required": []
        }
    },

    # Common 'Projekt Details' section for other document types
    "Projekt Details": {
        "name": "fill_projekt_details",
        "description": "Populate the Projekt Details section for the document.",
        "parameters": {
            "type": "object",
            "properties": {
                "Standort": {"type": "string", "description": "Project location"},
                "Auftraggeber": {"type": "string", "description": "Client name"},
                "Untersuchungsmethoden": {"type": "string", "description": "Investigation methods (if applicable)"},
                "Probenentnahme": {"type": "string", "description": "Sampling details (if applicable)"},
                "Grundstücksdaten": {"type": "string", "description": "Plot data (if applicable)"},
                "Bauvorhaben": {"type": "string", "description": "Construction project (if applicable)"},
                "Versuchsaufbau": {"type": "string", "description": "Test setup (if applicable)"},
                "Durchführung": {"type": "string", "description": "Test execution (if applicable)"}
            },
            "required": []
        }
    },

    # Common 'Projekt Objectives' section for other document types
    "Projekt Objectives": {
        "name": "fill_projekt_objectives",
        "description": "Populate the Projekt Objectives section with goals and requirements.",
        "parameters": {
            "type": "object",
            "properties": {
                "Ziele": {"type": "string", "description": "Goals of the project"},
                "Anforderungen": {"type": "string", "description": "Requirements"},
                "Bodenbeschaffenheit": {"type": "string", "description": "Soil composition (if applicable)"},
                "Analyseergebnisse": {"type": "string", "description": "Analysis results (if applicable)"},
                "Bewertung": {"type": "string", "description": "Assessment"},
                "Empfehlungen": {"type": "string", "description": "Recommendations"},
                "Messergebnisse": {"type": "string", "description": "Measurement results (if applicable)"},
                "Auswertung": {"type": "string", "description": "Evaluation"}
            },
            "required": []
        }
    },

    # Common 'Anhänge' section for other document types
    "Anhänge": {
        "name": "fill_anhaenge",
        "description": "Populate the Anhänge section with document attachments and images.",
        "parameters": {
            "type": "object",
            "properties": {
                "Dokumente": {"type": "array", "items": {"type": "string"}, "description": "List of document filenames or URLs"},
                "Bilder": {"type": "array", "items": {"type": "string"}, "description": "List of image filenames or URLs"},
                "Laborberichte": {"type": "array", "items": {"type": "string"}, "description": "Laboratory report filenames or URLs"},
                "Fotos": {"type": "array", "items": {"type": "string"}, "description": "Photo filenames or URLs"},
                "Gutachten": {"type": "array", "items": {"type": "string"}, "description": "Expert report filenames or URLs"},
                "Pläne": {"type": "array", "items": {"type": "string"}, "description": "Plan filenames or URLs"},
                "Messprotokolle": {"type": "array", "items": {"type": "string"}, "description": "Measurement protocol filenames or URLs"},
                "Diagramme": {"type": "array", "items": {"type": "string"}, "description": "Diagram filenames or URLs"}
            },
            "required": []
        }
    }
}
