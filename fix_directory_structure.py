"""
Script to fix directory structure issues in deployment.
This creates necessary directories and files if they don't exist.
"""
import os
import sys
import glob
import shutil

def ensure_directory(path):
    """Ensure the directory exists"""
    if not os.path.exists(path):
        print(f"Creating directory: {path}")
        os.makedirs(path)
    else:
        print(f"Directory already exists: {path}")

def ensure_init_file(dir_path):
    """Ensure __init__.py exists in the directory"""
    init_path = os.path.join(dir_path, '__init__.py')
    if not os.path.exists(init_path):
        print(f"Creating __init__.py in {dir_path}")
        with open(init_path, 'w') as f:
            f.write('# Auto-generated __init__.py\n')
    else:
        print(f"__init__.py already exists in {dir_path}")

def find_file(filename, search_paths=None):
    """Find a file in various locations"""
    if search_paths is None:
        # Default search paths - include both case variations
        search_paths = [
            '.',
            './app',
            './app/functions',
            './app/Functions',  # Added uppercase version
            '/app',
            '/app/app',
            '/app/app/functions',
            '/app/app/Functions',  # Added uppercase version
            '/src',
            '/src/app',
            '/src/app/functions',
            '/src/app/Functions'   # Added uppercase version
        ]
    
    print(f"Searching for {filename} in multiple locations...")
    for path in search_paths:
        full_path = os.path.join(path, filename)
        if os.path.exists(full_path):
            print(f"Found {filename} at {full_path}")
            return full_path
    
    # Try using glob to find the file anywhere
    print(f"Using glob to search for {filename}...")
    for pattern in ['**/' + filename, '**/*/' + filename, '**/*/*/' + filename]:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            print(f"Found {filename} using glob at {matches[0]}")
            return matches[0]
    
    print(f"Could not find {filename} in any location")
    return None

def fix_directory_structure():
    """Fix common directory structure issues"""
    print("="*50)
    print("FIXING DIRECTORY STRUCTURE")
    print("="*50)
    
    # Get the base directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Base directory: {base_dir}")
    
    # Print current directory contents for debugging
    print("\nCurrent directory contents:")
    for item in os.listdir('.'):
        if os.path.isdir(item):
            print(f" - DIR: {item}/")
            # Print first level of subdirectories
            try:
                for subitem in os.listdir(item):
                    print(f"   - {subitem}")
            except:
                print(f"   (Could not list contents)")
        else:
            print(f" - FILE: {item}")
    
    # Ensure app directory exists
    app_dir = os.path.join(base_dir, 'app')
    ensure_directory(app_dir)
    ensure_init_file(app_dir)
    
    # Ensure subdirectories exist with __init__.py
    subdirs = ['functions', 'workflows', 'models', 'config', 'utils', 'middleware', 'services', 'prompts']
    for subdir in subdirs:
        dir_path = os.path.join(app_dir, subdir)
        ensure_directory(dir_path)
        ensure_init_file(dir_path)
    
    # Handle case sensitivity issue - create symbolic link if needed
    functions_lower = os.path.join(app_dir, 'functions')
    functions_upper = os.path.join(app_dir, 'Functions')
    
    # Check if we have the uppercase directory but not the lowercase
    if os.path.exists(functions_upper) and not os.path.exists(functions_lower):
        print(f"Creating lowercase functions directory to match imports")
        ensure_directory(functions_lower)
        ensure_init_file(functions_lower)
    
    # Check if we have the lowercase directory but not the uppercase
    if os.path.exists(functions_lower) and not os.path.exists(functions_upper):
        print(f"Creating uppercase Functions directory to match Git tracking")
        ensure_directory(functions_upper)
        ensure_init_file(functions_upper)
    
    # Look for llm_functions.py in various locations
    llm_functions_source = find_file('llm_functions.py')
    llm_functions_path_lower = os.path.join(app_dir, 'functions', 'llm_functions.py')
    llm_functions_path_upper = os.path.join(app_dir, 'Functions', 'llm_functions.py')
    
    # Copy to both locations to ensure it works regardless of case
    if llm_functions_source:
        # Copy to lowercase path
        if llm_functions_source != llm_functions_path_lower:
            print(f"Copying {llm_functions_source} to {llm_functions_path_lower}")
            try:
                shutil.copy2(llm_functions_source, llm_functions_path_lower)
                print(f"Successfully copied llm_functions.py to lowercase path")
            except Exception as e:
                print(f"Error copying file to lowercase path: {str(e)}")
                create_placeholder_llm_functions(llm_functions_path_lower)
        
        # Copy to uppercase path
        if llm_functions_source != llm_functions_path_upper:
            print(f"Copying {llm_functions_source} to {llm_functions_path_upper}")
            try:
                shutil.copy2(llm_functions_source, llm_functions_path_upper)
                print(f"Successfully copied llm_functions.py to uppercase path")
            except Exception as e:
                print(f"Error copying file to uppercase path: {str(e)}")
                create_placeholder_llm_functions(llm_functions_path_upper)
    else:
        # Create placeholders in both locations
        if not os.path.exists(llm_functions_path_lower):
            create_placeholder_llm_functions(llm_functions_path_lower)
        if not os.path.exists(llm_functions_path_upper):
            create_placeholder_llm_functions(llm_functions_path_upper)
    
    # Look for betting_models.py in various locations
    models_source = find_file('betting_models.py')
    models_path = os.path.join(app_dir, 'models', 'betting_models.py')
    
    if models_source and models_source != models_path:
        print(f"Copying {models_source} to {models_path}")
        try:
            shutil.copy2(models_source, models_path)
            print(f"Successfully copied betting_models.py")
        except Exception as e:
            print(f"Error copying file: {str(e)}")
            # Create placeholder as fallback
            create_placeholder_betting_models(models_path)
    elif not os.path.exists(models_path):
        create_placeholder_betting_models(models_path)
    else:
        print(f"betting_models.py already exists at {models_path}")
    
    print("="*50)

def create_placeholder_llm_functions(llm_functions_path):
    """Create placeholder for llm_functions.py"""
    print(f"Creating placeholder llm_functions.py at {llm_functions_path}")
    with open(llm_functions_path, 'w') as f:
        f.write('''"""
Placeholder for LLM functions - will be replaced with actual implementation
"""
import logging

logger = logging.getLogger(__name__)

async def analyze_query(user_input):
    """Placeholder analyze_query function"""
    logger.warning("Using placeholder analyze_query function")
    return {"is_deep_research": False}

async def quick_research(query_analysis):
    """Placeholder quick_research function"""
    logger.warning("Using placeholder quick_research function")
    return {"deep_research_recommended": False}

async def deep_research(query_analysis, data_points):
    """Placeholder deep_research function"""
    logger.warning("Using placeholder deep_research function")
    return {}

async def generate_final_response(user_input, result, is_deep_research=False):
    """Placeholder generate_final_response function"""
    logger.warning("Using placeholder generate_final_response function")
    return {"conversational_response": "This is a placeholder response."} 
''')

def create_placeholder_betting_models(models_path):
    """Create placeholder for betting_models.py"""
    print(f"Creating placeholder betting_models.py")
    with open(models_path, 'w') as f:
        f.write('''"""
Placeholder for betting models - will be replaced with actual implementation
"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class QueryAnalysis(BaseModel):
    """Placeholder QueryAnalysis model"""
    is_deep_research: bool = False

class DataPoint(BaseModel):
    """Placeholder DataPoint model"""
    source: str
    data: Dict[str, Any]

class QuickResearchResult(BaseModel):
    """Placeholder QuickResearchResult model"""
    deep_research_recommended: bool = False
    
    def model_dump_json(self):
        """Placeholder method"""
        return "{}"
    
    def pop(self, key, default=None):
        """Placeholder method"""
        return default

class DeepResearchResult(BaseModel):
    """Placeholder DeepResearchResult model"""
    
    def model_dump_json(self):
        """Placeholder method"""
        return "{}"
        
    def pop(self, key, default=None):
        """Placeholder method"""
        return default
''')

if __name__ == "__main__":
    fix_directory_structure() 