DOCUMENT_STRUCTURE = {
    'Deklarationsanalyse': [
        {'Deckblatt':    ['Projekt', 'Auftraggeber', 'Dienstleistungsnummer', 'Probenahmedatum']},
        {'Stellungnahme': ['Probenahmeprotokoll', 'Laborberichte', 'Auswertung']},
        {'Anhänge':      ['Dateien']}
    ],
    'Bodenuntersuchung': [
        {'Projekt Details':    ['Untersuchungsmethoden', 'Probenentnahme']},
        {'Projekt Objectives': ['Bodenbeschaffenheit', 'Analyseergebnisse']},
        {'Anhänge':            ['Laborberichte', 'Fotos']}
    ],
    'Baugrundgutachten': [
        {'Allgemeines und Bauvorhaben': ['Anlass und Vorgaben', 'Geländeverhältnisse und Bauwerk', 'Geotechnische Kategorie', 'Geologie', 'Standortbezogene Gefährdungszonen']},
        {'Feldarbeiten': ['Geotechnische Untersuchungen', 'Untergrundverhältnisse', 'Grundwasserverhältnisse', 'Wasserdurchlässigkeit der Böden']},
        {'Bodenkennwerte und Klassifikation': ['Geotechnische Kennwerte', 'Bodenklassifikation und Homogenbereiche']},
        {'Gründungsempfehlung': ['Baugrundbeurteilung', 'Einzel- und Streifenfundamente', 'Fundamentplatte', 'Allgemeine Vorgaben für alle Gründungsvarianten', 'Angaben zur Bemessung der Gründung']},
        {'Wasserbeanspruchung und Abdichtung': ['Wasserbeanspruchung und Abdichtung']},
        {'Bauausführung': ['Herstellen der Baugrube', 'Wiedereinbau von anfallendem Bodenaushub', 'Entsorgung von Bodenaushub', 'Hinweise']},
        {'Schlussbemerkung': ['Schlussbemerkung']},
        {'Anhänge': ['Gutachten', 'Pläne']}
    ],
    'Plattendruckversuch': [
        {'Projekt Details':    ['Versuchsaufbau', 'Durchführung']},
        {'Projekt Objectives': ['Messergebnisse', 'Auswertung']},
        {'Anhänge':            ['Messprotokolle', 'Diagramme']}
    ]
}

# Save the current structure to a file for debugging
import json
import os

# Print structure contents to a debug file
try:
    with open(os.path.join(os.path.dirname(__file__), 'structure_debug.txt'), 'w') as f:
        f.write(json.dumps(DOCUMENT_STRUCTURE, indent=2))
except Exception as e:
    print(f"Error writing debug file: {e}")