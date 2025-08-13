#!/bin/bash

# Elasticsearch Setup Script
# This script creates indices and pipelines for the blog data loading system

ES_URL="http://localhost:9200"
USERS_INDEX="blog-users"
ARTICLES_INDEX="blog-articles"
USERS_PIPELINE="blog-users-pipeline"
ARTICLES_PIPELINE="blog-articles-pipeline"

echo "Setting up Elasticsearch for Blog Data Loading System"
echo "====================================================="

# Check if Elasticsearch is running
echo "Checking Elasticsearch connection..."
if ! curl -s "$ES_URL" > /dev/null; then
    echo "❌ Error: Cannot connect to Elasticsearch at $ES_URL"
    echo "Please make sure Elasticsearch is running."
    exit 1
fi

echo "✅ Elasticsearch is running"

# Create Users Index
echo "Creating users index..."
curl -X PUT "$ES_URL/$USERS_INDEX" \
    -H "Content-Type: application/json" \
    -d @es/users_mapping.json

if [ $? -eq 0 ]; then
    echo "✅ Users index created successfully"
else
    echo "❌ Failed to create users index"
fi

# Create Articles Index
echo "Creating articles index..."
curl -X PUT "$ES_URL/$ARTICLES_INDEX" \
    -H "Content-Type: application/json" \
    -d @es/articles_mapping.json

if [ $? -eq 0 ]; then
    echo "✅ Articles index created successfully"
else
    echo "❌ Failed to create articles index"
fi

# Create Users Pipeline
echo "Creating users pipeline..."
curl -X PUT "$ES_URL/_ingest/pipeline/$USERS_PIPELINE" \
    -H "Content-Type: application/json" \
    -d @es/users_pipeline.json

if [ $? -eq 0 ]; then
    echo "✅ Users pipeline created successfully"
else
    echo "❌ Failed to create users pipeline"
fi

# Create Articles Pipeline
echo "Creating articles pipeline..."
curl -X PUT "$ES_URL/_ingest/pipeline/$ARTICLES_PIPELINE" \
    -H "Content-Type: application/json" \
    -d @es/articles_pipeline.json

if [ $? -eq 0 ]; then
    echo "✅ Articles pipeline created successfully"
else
    echo "❌ Failed to create articles pipeline"
fi

echo ""
echo "Setup completed! You can now:"
echo "1. Load data: python main.py --load-all"
echo "2. Validate data: python main.py --validate"
echo "3. View data in Kibana at http://localhost:5601"
echo ""
echo "Index information:"
echo "- Users index: $USERS_INDEX"
echo "- Articles index: $ARTICLES_INDEX"
echo "- Users pipeline: $USERS_PIPELINE"
echo "- Articles pipeline: $ARTICLES_PIPELINE"
