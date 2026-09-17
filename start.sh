#!/bin/bash
# Quick start script for local development

set -e

echo "=================================="
echo "PromptPay Payment Verification"
echo "=================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Copying from .env.example..."
    cp .env.example .env
    echo "✅ Created .env file. Please edit it with your configuration."
    echo ""
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
    echo ""
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Run tests
echo "Running tests..."
pytest tests/ -v --tb=short
echo ""

echo "=================================="
echo "Setup complete!"
echo ""
echo "To start the API server:"
echo "  source venv/bin/activate"
echo "  uvicorn app.main:app --reload"
echo ""
echo "To start with Docker:"
echo "  docker-compose up -d"
echo ""
echo "To run IMAP worker:"
echo "  python worker/imap_worker.py"
echo ""
echo "See README.md for full documentation."
echo "=================================="
