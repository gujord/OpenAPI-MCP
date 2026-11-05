#!/bin/bash
set -e

echo "🐳 Starting OpenAPI-MCP Docker Services"
echo "======================================="

# Build and start services
echo "Building and starting services..."
docker-compose up --build -d

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Check service health
echo "Checking service health..."

# Check weather API
if curl -f http://localhost:8001/health > /dev/null 2>&1; then
    echo "✅ Weather API (port 8001): HEALTHY"
else
    echo "❌ Weather API (port 8001): NOT READY"
fi

# Check petstore API  
if curl -f http://localhost:8002/health > /dev/null 2>&1; then
    echo "✅ Petstore API (port 8002): HEALTHY"
else
    echo "❌ Petstore API (port 8002): NOT READY"
fi

echo ""
echo "🎉 Services started successfully!"
echo ""
echo "MCP Client Configuration:"
echo "========================"
echo '{
  "mcpServers": {
    "weather": {
      "command": "npx",
      "args": ["mcp-remote", "http://127.0.0.1:8001/mcp"]
    },
    "petstore": {
      "command": "npx", 
      "args": ["mcp-remote", "http://127.0.0.1:8002/mcp"]
    }
  }
}'
echo ""
echo "To stop services: docker-compose down"
echo "To view logs: docker-compose logs -f"