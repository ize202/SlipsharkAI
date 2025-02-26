"""
Main entry point for the Sports Research API.
This file is used to start the FastAPI application.
"""
import os
import sys
import logging
import traceback
import glob
import subprocess
import shutil

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logger.info(f"Added to Python path: {os.path.dirname(os.path.abspath(__file__))}")

# Print environment information
logger.info("Environment Information:")
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"Python version: {sys.version}")
logger.info(f"Python path: {sys.path}")

# Check if we're in a Git repository
try:
    git_info = subprocess.check_output(["git", "remote", "-v"], stderr=subprocess.STDOUT).decode()
    logger.info(f"Git remote info: {git_info}")
    
    git_branch = subprocess.check_output(["git", "branch", "--show-current"], stderr=subprocess.STDOUT).decode().strip()
    logger.info(f"Current Git branch: {git_branch}")
    
    git_status = subprocess.check_output(["git", "status", "--short"], stderr=subprocess.STDOUT).decode()
    logger.info(f"Git status: {git_status}")
except Exception as e:
    logger.info(f"Not a Git repository or Git not available: {str(e)}")

# Handle case sensitivity issue between app/functions and app/Functions
logger.info("Checking for case sensitivity issues in directory structure...")
base_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.join(base_dir, 'app')
functions_lower = os.path.join(app_dir, 'functions')
functions_upper = os.path.join(app_dir, 'Functions')

# Check both paths
logger.info(f"Checking lowercase path: {functions_lower}")
logger.info(f"Checking uppercase path: {functions_upper}")

# Create directories if they don't exist
if not os.path.exists(functions_lower):
    logger.info(f"Creating lowercase functions directory")
    os.makedirs(functions_lower, exist_ok=True)
    with open(os.path.join(functions_lower, '__init__.py'), 'w') as f:
        f.write('# Auto-generated __init__.py\n')

if not os.path.exists(functions_upper):
    logger.info(f"Creating uppercase Functions directory")
    os.makedirs(functions_upper, exist_ok=True)
    with open(os.path.join(functions_upper, '__init__.py'), 'w') as f:
        f.write('# Auto-generated __init__.py\n')

# Check for llm_functions.py in both locations
llm_functions_lower = os.path.join(functions_lower, 'llm_functions.py')
llm_functions_upper = os.path.join(functions_upper, 'llm_functions.py')

# If file exists in one location but not the other, copy it
if os.path.exists(llm_functions_lower) and not os.path.exists(llm_functions_upper):
    logger.info(f"Copying llm_functions.py from lowercase to uppercase path")
    shutil.copy2(llm_functions_lower, llm_functions_upper)
elif os.path.exists(llm_functions_upper) and not os.path.exists(llm_functions_lower):
    logger.info(f"Copying llm_functions.py from uppercase to lowercase path")
    shutil.copy2(llm_functions_upper, llm_functions_lower)

# Check for key files
logger.info("Checking for key files:")
for file_pattern in ["app/functions/llm_functions.py", "app/Functions/llm_functions.py", "app/models/betting_models.py"]:
    if os.path.exists(file_pattern):
        logger.info(f"Found {file_pattern}")
        # Check file size
        size = os.path.getsize(file_pattern)
        logger.info(f"{file_pattern} size: {size} bytes")
        # Check first few lines
        try:
            with open(file_pattern, 'r') as f:
                first_lines = [next(f) for _ in range(5)]
                logger.info(f"{file_pattern} first few lines: {first_lines}")
        except Exception as e:
            logger.info(f"Error reading {file_pattern}: {str(e)}")
    else:
        logger.info(f"File not found: {file_pattern}")

try:
    # First try to fix the directory structure if needed
    logger.info("Ensuring directory structure is correct...")
    try:
        from fix_directory_structure import fix_directory_structure
        fix_directory_structure()
    except Exception as e:
        logger.error(f"Failed to fix directory structure: {str(e)}")
        traceback.print_exc()
    
    # Try to import the FastAPI app
    logger.info("Trying to import FastAPI app...")
    try:
        from app.api import app
        logger.info("Successfully imported FastAPI app!")
    except ImportError as e:
        logger.error(f"Failed to import app/api.py: {str(e)}")
        traceback.print_exc()
        
        # Try to create a minimal FastAPI app as a fallback
        logger.info("Creating minimal FastAPI app as fallback...")
        from fastapi import FastAPI
        app = FastAPI(
            title="Sports Research API (Fallback)",
            description="Minimal fallback mode due to import errors",
        )
        
        @app.get("/")
        async def root():
            return {
                "status": "error",
                "message": "Running in fallback mode due to import errors",
                "error": str(e)
            }
        
        @app.get("/health")
        async def health():
            return {
                "status": "unhealthy",
                "error": "Running in fallback mode",
                "details": str(e)
            }
        
        @app.get("/debug")
        async def debug():
            """Endpoint to get debug information about the deployment environment"""
            debug_info = {
                "cwd": os.getcwd(),
                "python_path": sys.path,
                "env_vars": {k: v for k, v in os.environ.items() 
                            if not ("key" in k.lower() or "secret" in k.lower() or "password" in k.lower())},
                "directory_structure": {}
            }
            
            # Get directory structure
            for root_dir in [".", "/app", "/app/app"]:
                if os.path.exists(root_dir):
                    structure = {}
                    for root, dirs, files in os.walk(root_dir):
                        structure[root] = {
                            "dirs": dirs,
                            "files": files
                        }
                    debug_info["directory_structure"][root_dir] = structure
            
            return debug_info
    
    # This allows the app to be run with `python main.py`
    if __name__ == "__main__":
        import uvicorn
        port = int(os.environ.get("PORT", 8000))
        logger.info(f"Starting uvicorn server on port {port}...")
        uvicorn.run(app, host="0.0.0.0", port=port)
except Exception as e:
    logger.critical(f"Critical error in main.py: {str(e)}")
    traceback.print_exc()
    
    # Try to create an absolute minimal application as a last resort
    try:
        import uvicorn
        from fastapi import FastAPI
        emergency_app = FastAPI(title="Emergency Fallback API")
        
        @emergency_app.get("/")
        async def emergency_root():
            return {
                "status": "critical_error",
                "message": "Application failed to start properly",
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        
        @emergency_app.get("/debug")
        async def debug():
            """Emergency debug endpoint"""
            debug_info = {
                "cwd": os.getcwd(),
                "python_path": sys.path,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "directory_listing": {}
            }
            
            # List directories
            for path in [".", "/app", "/app/app"]:
                if os.path.exists(path):
                    try:
                        debug_info["directory_listing"][path] = os.listdir(path)
                    except:
                        debug_info["directory_listing"][path] = "Error listing directory"
            
            return debug_info
        
        port = int(os.environ.get("PORT", 8000))
        logger.info(f"Starting emergency fallback on port {port}...")
        uvicorn.run(emergency_app, host="0.0.0.0", port=port)
    except Exception as final_e:
        logger.critical(f"Failed to start emergency fallback: {str(final_e)}")
        sys.exit(1) 