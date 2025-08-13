@echo off
setlocal enabledelayedexpansion

REM Elasticsearch Setup Script for Windows
REM This script creates indices and pipelines for the blog data loading system

set ES_URL=http://localhost:9200
set USERS_INDEX=blog-users
set ARTICLES_INDEX=blog-articles
set USERS_PIPELINE=blog-users-pipeline
set ARTICLES_PIPELINE=blog-articles-pipeline

echo Setting up Elasticsearch for Blog Data Loading System
echo =====================================================

REM Check if Elasticsearch is running
echo Checking Elasticsearch connection...
curl -s "%ES_URL%" >nul 2>&1
if !errorlevel! neq 0 (
    echo ❌ Error: Cannot connect to Elasticsearch at %ES_URL%
    echo Please make sure Elasticsearch is running.
    pause
    exit /b 1
)

echo ✅ Elasticsearch is running

REM Create Users Index
echo Creating users index...
curl -X PUT "%ES_URL%/%USERS_INDEX%" -H "Content-Type: application/json" -d @es/users_mapping.json
if !errorlevel! equ 0 (
    echo ✅ Users index created successfully
) else (
    echo ❌ Failed to create users index
)

REM Create Articles Index
echo Creating articles index...
curl -X PUT "%ES_URL%/%ARTICLES_INDEX%" -H "Content-Type: application/json" -d @es/articles_mapping.json
if !errorlevel! equ 0 (
    echo ✅ Articles index created successfully
) else (
    echo ❌ Failed to create articles index
)

REM Create Users Pipeline
echo Creating users pipeline...
curl -X PUT "%ES_URL%/_ingest/pipeline/%USERS_PIPELINE%" -H "Content-Type: application/json" -d @es/users_pipeline.json
if !errorlevel! equ 0 (
    echo ✅ Users pipeline created successfully
) else (
    echo ❌ Failed to create users pipeline
)

REM Create Articles Pipeline
echo Creating articles pipeline...
curl -X PUT "%ES_URL%/_ingest/pipeline/%ARTICLES_PIPELINE%" -H "Content-Type: application/json" -d @es/articles_pipeline.json
if !errorlevel! equ 0 (
    echo ✅ Articles pipeline created successfully
) else (
    echo ❌ Failed to create articles pipeline
)

echo.
echo Setup completed! You can now:
echo 1. Load data: python main.py --load-all
echo 2. Validate data: python main.py --validate
echo 3. View data in Kibana at http://localhost:5601
echo.
echo Index information:
echo - Users index: %USERS_INDEX%
echo - Articles index: %ARTICLES_INDEX%
echo - Users pipeline: %USERS_PIPELINE%
echo - Articles pipeline: %ARTICLES_PIPELINE%

pause
