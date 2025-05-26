# Document structure for different topics
DOCUMENT_STRUCTURE = {
    'Deklarationsanalyse': [
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

# Cover page structure for different topics
# This defines what fields are editable on the cover page for each topic
COVER_PAGE_STRUCTURE = {
    'Baugrundgutachten': {
        'PROJEKTBESCHREIBUNG': {
            'document_subtitle': {'label': 'Dokumentuntertitel', 'type': 'text', 'required': False, 'default': 'NACH DIN 4020'},
            'project_name': {'label': 'Projektname', 'type': 'text', 'required': True},
            'project_line2': {'label': 'Projektbeschreibung Zeile 2', 'type': 'text', 'required': False},
            'property_info': {'label': 'Flurstück / Gemarkung', 'type': 'text', 'required': False},
            'street': {'label': 'Straße', 'type': 'text', 'required': False},
            'house_number': {'label': 'Hausnummer', 'type': 'text', 'required': False},
            'postal_code': {'label': 'Postleitzahl', 'type': 'text', 'required': False},
            'city': {'label': 'Stadt', 'type': 'text', 'required': False}
        },
        'AUFTRAGGEBER': {
            'client_company': {'label': 'Firma', 'type': 'text', 'required': True},
            'client_name': {'label': 'Vor- und Nachname', 'type': 'text', 'required': True},
            'client_street': {'label': 'Straße', 'type': 'text', 'required': False},
            'client_house_number': {'label': 'Hausnummer', 'type': 'text', 'required': False},
            'client_postal_code': {'label': 'Postleitzahl', 'type': 'text', 'required': False},
            'client_city': {'label': 'Stadt', 'type': 'text', 'required': False}
        },
        'AUFTRAG': {
            'order_number': {'label': 'Auftragsnummer', 'type': 'text', 'required': True},
            'creation_date': {'label': 'Erstellt am', 'type': 'date', 'required': False},
            'author': {'label': 'Erstellt durch', 'type': 'text', 'required': False}
        }
    },
    'Deklarationsanalyse': {
        'PROJEKTBESCHREIBUNG': {
            'document_subtitle': {'label': 'Dokumentuntertitel', 'type': 'text', 'required': False, 'default': 'NACH DEPV'},
            'project_name': {'label': 'Projektname', 'type': 'text', 'required': True},
            'project_line2': {'label': 'Projektbeschreibung Zeile 2', 'type': 'text', 'required': False},
            'property_info': {'label': 'Flurstück / Gemarkung', 'type': 'text', 'required': False},
            'street': {'label': 'Straße', 'type': 'text', 'required': False},
            'house_number': {'label': 'Hausnummer', 'type': 'text', 'required': False},
            'postal_code': {'label': 'Postleitzahl', 'type': 'text', 'required': False},
            'city': {'label': 'Stadt', 'type': 'text', 'required': False}
        },
        'AUFTRAGGEBER': {
            'client_company': {'label': 'Firma', 'type': 'text', 'required': True},
            'client_name': {'label': 'Vor- und Nachname', 'type': 'text', 'required': True},
            'client_street': {'label': 'Straße', 'type': 'text', 'required': False},
            'client_house_number': {'label': 'Hausnummer', 'type': 'text', 'required': False},
            'client_postal_code': {'label': 'Postleitzahl', 'type': 'text', 'required': False},
            'client_city': {'label': 'Stadt', 'type': 'text', 'required': False}
        },
        'AUFTRAG': {
            'order_number': {'label': 'Auftragsnummer', 'type': 'text', 'required': True},
            'creation_date': {'label': 'Erstellt am', 'type': 'date', 'required': False},
            'author': {'label': 'Erstellt durch', 'type': 'text', 'required': False}
        }
    },
    'Bodenuntersuchung': {
        'PROJEKTBESCHREIBUNG': {
            'document_subtitle': {'label': 'Dokumentuntertitel', 'type': 'text', 'required': False, 'default': 'NACH DIN 18196'},
            'project_name': {'label': 'Projektname', 'type': 'text', 'required': True},
            'project_line2': {'label': 'Projektbeschreibung Zeile 2', 'type': 'text', 'required': False},
            'property_info': {'label': 'Flurstück / Gemarkung', 'type': 'text', 'required': False},
            'street': {'label': 'Straße', 'type': 'text', 'required': False},
            'house_number': {'label': 'Hausnummer', 'type': 'text', 'required': False},
            'postal_code': {'label': 'Postleitzahl', 'type': 'text', 'required': False},
            'city': {'label': 'Stadt', 'type': 'text', 'required': False}
        },
        'AUFTRAGGEBER': {
            'client_company': {'label': 'Firma', 'type': 'text', 'required': True},
            'client_name': {'label': 'Vor- und Nachname', 'type': 'text', 'required': True},
            'client_street': {'label': 'Straße', 'type': 'text', 'required': False},
            'client_house_number': {'label': 'Hausnummer', 'type': 'text', 'required': False},
            'client_postal_code': {'label': 'Postleitzahl', 'type': 'text', 'required': False},
            'client_city': {'label': 'Stadt', 'type': 'text', 'required': False}
        },
        'AUFTRAG': {
            'order_number': {'label': 'Auftragsnummer', 'type': 'text', 'required': True},
            'creation_date': {'label': 'Erstellt am', 'type': 'date', 'required': False},
            'author': {'label': 'Erstellt durch', 'type': 'text', 'required': False}
        },
        'PROBENENTNAHME': {
            'sampling_location': {'label': 'Probenentnahmeort', 'type': 'text', 'required': False},
            'signature_name': {'label': 'Unterschrift Name', 'type': 'text', 'required': False},
            'company_info': {'label': 'Firmeninformationen', 'type': 'text', 'required': False}
        }
    },
    'Plattendruckversuch': {
        'PROJEKTBESCHREIBUNG': {
            'document_subtitle': {'label': 'Dokumentuntertitel', 'type': 'text', 'required': False, 'default': 'NACH DIN 18134'},
            'project_name': {'label': 'Projektname', 'type': 'text', 'required': True},
            'project_line2': {'label': 'Projektbeschreibung Zeile 2', 'type': 'text', 'required': False},
            'property_info': {'label': 'Flurstück / Gemarkung', 'type': 'text', 'required': False},
            'street': {'label': 'Straße', 'type': 'text', 'required': False},
            'house_number': {'label': 'Hausnummer', 'type': 'text', 'required': False},
            'postal_code': {'label': 'Postleitzahl', 'type': 'text', 'required': False},
            'city': {'label': 'Stadt', 'type': 'text', 'required': False}
        },
        'AUFTRAGGEBER': {
            'client_company': {'label': 'Firma', 'type': 'text', 'required': True},
            'client_name': {'label': 'Vor- und Nachname', 'type': 'text', 'required': True},
            'client_street': {'label': 'Straße', 'type': 'text', 'required': False},
            'client_house_number': {'label': 'Hausnummer', 'type': 'text', 'required': False},
            'client_postal_code': {'label': 'Postleitzahl', 'type': 'text', 'required': False},
            'client_city': {'label': 'Stadt', 'type': 'text', 'required': False}
        },
        'AUFTRAG': {
            'order_number': {'label': 'Auftragsnummer', 'type': 'text', 'required': True},
            'creation_date': {'label': 'Erstellt am', 'type': 'date', 'required': False},
            'author': {'label': 'Erstellt durch', 'type': 'text', 'required': False}
        },
        'VERSUCHSDETAILS': {
            'test_location': {'label': 'Versuchsort', 'type': 'text', 'required': False},
            'signature_name': {'label': 'Unterschrift Name', 'type': 'text', 'required': False},
            'company_info': {'label': 'Firmeninformationen', 'type': 'text', 'required': False}
        }
    }
}

# Save the current structure to a file for debugging
import json
import os

# Print structure contents to a debug file
try:
    with open(os.path.join(os.path.dirname(__file__), 'structure_debug.txt'), 'w') as f:
        f.write("DOCUMENT_STRUCTURE:\n")
        f.write(json.dumps(DOCUMENT_STRUCTURE, indent=2))
        f.write("\n\nCOVER_PAGE_STRUCTURE:\n")
        f.write(json.dumps(COVER_PAGE_STRUCTURE, indent=2))
except Exception as e:
    print(f"Error writing debug file: {e}")