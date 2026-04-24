#!/bin/bash

# MESH Protocol Development Server
# Starts both the API server and the Next.js client

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting MESH Protocol Development Environment${NC}"
echo ""

# Install Python dependencies
echo -e "${GREEN}Installing Python dependencies...${NC}"
pip install fastapi uvicorn aiosqlite pydantic --quiet

# Install Node dependencies if needed
if [ ! -d "client/node_modules" ]; then
    echo -e "${GREEN}Installing Node dependencies...${NC}"
    cd client && npm install && cd ..
fi

# Start the API server in background
echo -e "${GREEN}Starting MESH API Server on port 12000...${NC}"
cd server
MESH_NODE_ID=node1 MESH_NODE_URL=http://localhost:12000 python main.py --port 12000 &
SERVER_PID=$!
cd ..

# Give server time to start
sleep 2

# Start Next.js client
echo -e "${GREEN}Starting Next.js Client on port 12001...${NC}"
cd client
NEXT_PUBLIC_API_URL=http://localhost:12000 npm run dev -- -p 12001 &
CLIENT_PID=$!
cd ..

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}MESH Protocol is running!${NC}"
echo ""
echo "  API Server:  http://localhost:12000"
echo "  Web Client:  http://localhost:12001"
echo ""
echo "  API Docs:    http://localhost:12000/docs"
echo "  Node Info:   http://localhost:12000/.well-known/mesh-node"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for both processes
wait
