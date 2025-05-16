#!/usr/bin/env python
import sys
import os
from pathlib import Path

# Add the parent directory to the Python path to import project modules
sys.path.append(str(Path(__file__).parent.parent))

from templates.structure import DOCUMENT_STRUCTURE

def test_structure():
    """
    Test the document structure to verify section and subsection definitions
    """
    print("Testing DOCUMENT_STRUCTURE validation...")
    
    # Check if 'Deklarationsanalyse' exists
    if 'Deklarationsanalyse' not in DOCUMENT_STRUCTURE:
        print("ERROR: 'Deklarationsanalyse' not found in DOCUMENT_STRUCTURE")
        return
    
    print(f"Topic: Deklarationsanalyse")
    sections = DOCUMENT_STRUCTURE['Deklarationsanalyse']
    
    print(f"Number of sections: {len(sections)}")
    for idx, sec_obj in enumerate(sections):
        sec_name = list(sec_obj.keys())[0]
        subsections = sec_obj[sec_name]
        print(f"  Section {idx+1}: {sec_name}")
        print(f"    Subsections: {subsections}")
    
    # Test section validation logic similar to the API
    test_sections = ['Deckblatt', 'Stellungnahme', 'Invalid Section']
    test_subsections = {
        'Deckblatt': ['Projekt', 'Auftraggeber', 'Invalid Subsection'],
        'Stellungnahme': ['Probenahmeprotokoll', 'Laborberichte', 'Invalid Subsection'],
        'Invalid Section': ['Test']
    }
    
    print("\nValidation Test:")
    topic = 'Deklarationsanalyse'
    
    for section in test_sections:
        section_valid = False
        
        for sec_obj in DOCUMENT_STRUCTURE[topic]:
            sec_name = list(sec_obj.keys())[0]
            if sec_name == section:
                section_valid = True
                print(f"  Section '{section}': VALID")
                
                # Test subsections
                for subsection in test_subsections[section]:
                    subsection_valid = False
                    if subsection in sec_obj[sec_name]:
                        subsection_valid = True
                        print(f"    Subsection '{subsection}': VALID")
                    else:
                        print(f"    Subsection '{subsection}': INVALID")
                        
                break
        
        if not section_valid:
            print(f"  Section '{section}': INVALID")

if __name__ == "__main__":
    test_structure() 