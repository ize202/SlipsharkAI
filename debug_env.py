"""
Debug script to understand the Railway deployment environment.
This will print information about directories, Python path, and other environment details.
"""
import os
import sys
import importlib.util

def debug_info():
    """Collect and print debug information"""
    print("="*50)
    print("DEPLOYMENT ENVIRONMENT DEBUG INFO")
    print("="*50)
    
    # Print current working directory
    print(f"Current working directory: {os.getcwd()}")
    
    # List directory contents
    print("\nDirectory contents:")
    for item in os.listdir('.'):
        if os.path.isdir(item):
            print(f" - DIR: {item}/")
        else:
            print(f" - FILE: {item}")
    
    # Check app directory contents if it exists
    if os.path.exists('app'):
        print("\nApp directory contents:")
        for item in os.listdir('app'):
            if os.path.isdir(os.path.join('app', item)):
                print(f" - DIR: {item}/")
            else:
                print(f" - FILE: {item}")
    
    # Print Python path
    print("\nPython path:")
    for path in sys.path:
        print(f" - {path}")
    
    # Check if functions directory exists
    functions_path = os.path.join('app', 'functions')
    print(f"\nFunctions directory exists: {os.path.exists(functions_path)}")
    if os.path.exists(functions_path):
        print("Functions directory contents:")
        for item in os.listdir(functions_path):
            print(f" - {item}")
    
    # Try to import using alternative approaches
    print("\nImport attempts:")
    try:
        import app.functions
        print(" - Direct import of app.functions: SUCCESS")
    except ImportError as e:
        print(f" - Direct import of app.functions: FAILED - {str(e)}")
    
    try:
        spec = importlib.util.find_spec("app.functions")
        print(f" - Find spec for app.functions: {'SUCCESS - ' + spec.origin if spec else 'FAILED - Not found'}")
    except Exception as e:
        print(f" - Find spec failed: {str(e)}")
    
    print("="*50)

if __name__ == "__main__":
    debug_info() 