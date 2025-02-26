"""
Script to fix directory structure issues in deployment.
This creates necessary directories and files if they don't exist.
"""
import os
import sys

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

def fix_directory_structure():
    """Fix common directory structure issues"""
    print("="*50)
    print("FIXING DIRECTORY STRUCTURE")
    print("="*50)
    
    # Get the base directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Base directory: {base_dir}")
    
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
    
    # Create placeholder for llm_functions.py if it doesn't exist
    llm_functions_path = os.path.join(app_dir, 'functions', 'llm_functions.py')
    if not os.path.exists(llm_functions_path):
        print(f"Creating placeholder llm_functions.py")
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
    else:
        print(f"llm_functions.py already exists")
    
    # Create placeholder for betting_models.py if it doesn't exist
    models_path = os.path.join(app_dir, 'models', 'betting_models.py')
    if not os.path.exists(models_path):
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
    else:
        print(f"betting_models.py already exists")
    
    print("="*50)

if __name__ == "__main__":
    fix_directory_structure() 