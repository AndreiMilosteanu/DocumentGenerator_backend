#!/usr/bin/env python3
"""
Test runner script for the Erdbaron Document Generator API.

This script provides convenient ways to run different types of tests.
"""

import sys
import subprocess
import argparse
import os

def run_command(cmd, description):
    """Run a command and handle the result."""
    print(f"\n{'='*50}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*50)
    
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode != 0:
        print(f"\n❌ {description} failed with exit code {result.returncode}")
        return False
    else:
        print(f"\n✅ {description} completed successfully")
        return True

def main():
    parser = argparse.ArgumentParser(description="Run tests for the Document Generator API")
    parser.add_argument(
        "--type", 
        choices=["all", "unit", "integration", "auth", "models", "fast"],
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run tests with coverage report"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Run tests in verbose mode"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Run tests from specific file"
    )
    parser.add_argument(
        "--function",
        type=str,
        help="Run specific test function"
    )
    parser.add_argument(
        "--failed",
        action="store_true",
        help="Run only failed tests from last run"
    )
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Install test dependencies first"
    )
    
    args = parser.parse_args()
    
    # Install dependencies if requested
    if args.install_deps:
        install_cmd = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
        if not run_command(install_cmd, "Installing dependencies"):
            return 1
    
    # Build base pytest command
    cmd = [sys.executable, "-m", "pytest"]
    
    # Add specific test file if specified
    if args.file:
        if not args.file.startswith("tests/"):
            args.file = f"tests/{args.file}"
        cmd.append(args.file)
        if args.function:
            cmd[-1] += f"::{args.function}"
    
    # Add test type filters
    elif args.type == "unit":
        cmd.extend(["-m", "unit"])
    elif args.type == "integration":
        cmd.extend(["-m", "integration"])
    elif args.type == "auth":
        cmd.extend(["-m", "auth"])
    elif args.type == "models":
        cmd.append("tests/test_models.py")
    elif args.type == "fast":
        cmd.extend(["-m", "not slow"])
    
    # Add verbosity
    if args.verbose:
        cmd.append("-vv")
    
    # Add coverage options
    if args.coverage or args.type == "all":
        cmd.extend([
            "--cov=.",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov"
        ])
    
    # Run only failed tests
    if args.failed:
        cmd.append("--lf")
    
    # Run tests
    success = run_command(cmd, f"Running {args.type} tests")
    
    if args.coverage or args.type == "all":
        print(f"\n📊 Coverage report generated at: htmlcov/index.html")
        print("To view: open htmlcov/index.html in your browser")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 