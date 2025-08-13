# Elasticsearch Data Loading System

A comprehensive system for loading blog data (Users and Articles) into Elasticsearch with:

- **Data validation** and relationship integrity checks
- **Index/pipeline management** with automated setup
- **Optional FastAPI server** for natural language search with LLM integration
- **Clean architecture** with modular design

## 🎯 Design Pattern

This system uses a **Modular Service Architecture** with these principles:

- **Core System**: Data loading with single DataLoader class (required)
- **Optional API Layer**: FastAPI with LLM integration for natural language search
- **Clean Separation**: Core functionality independent of API features
- **Comprehensive validation**: Schema validation + relationship integrity checks
- **Automated setup**: Index and pipeline creation with graceful error handling
- **Centralized logging**: Timestamped logs across all services with DEBUG support
- **Robust error handling**: Graceful fallbacks for Elasticsearch and LLM operations

## 📁 Project Structure

```
├── main.py                     # Main entry point with CLI and API server
├── requirements.txt            # All dependencies (core + API)
├── requirements-core.txt       # Core dependencies only
├── .env.example               # Environment variables template
├── setup_elasticsearch.sh     # Linux/Mac setup script
├── setup_elasticsearch.bat    # Windows setup script
├── api/
│   ├── __init__.py
│   └── main.py                # FastAPI application
├── services/
│   ├── __init__.py
│   ├── search_service.py      # Elasticsearch search operations
│   └── llm_service.py         # Azure OpenAI integration
├── config/
│   ├── __init__.py
│   └── prompts.py             # LLM prompts with CoT examples
├── data/
│   ├── data_schema.json       # Updated JSON schema (flexible validation)
│   └── generated.json         # Source data file
├── ingest/
│   ├── __init__.py
│   ├── models.py              # Pydantic models (User, Article, BlogData)
│   ├── data_loader.py         # Main DataLoader class
│   └── data_validator.py      # Comprehensive relationship validator
├── es/
│   ├── users_mapping.json     # Elasticsearch users index mapping
│   ├── articles_mapping.json  # Elasticsearch articles index mapping
│   ├── users_pipeline.json    # Users ingest pipeline
│   ├── articles_pipeline.json # Articles ingest pipeline
│   └── create_index.http      # HTTP requests for manual setup
├── utils/
│   ├── __init__.py
│   └── logger.py              # Centralized logging system
└── logs/                      # Log files (created automatically)
```

## 🚀 Setup Instructions

### Step 1: Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

**Note**: Make sure you're in the project directory when creating the virtual environment.

### Step 2: Configure Environment (Optional - for API features)

```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your Azure OpenAI credentials (only needed for API server)
# AZURE_OPENAI_API_KEY=your_key_here
# AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
# AZURE_OPENAI_API_VERSION=2024-02-15-preview
# AZURE_OPENAI_COMPLETION_DEPLOYMENT=your-deployment-name
```

### Step 3: Install Dependencies

```bash
# Install all dependencies (including optional API features)
pip install -r requirements.txt
```

### Step 4: Start Elasticsearch

```bash
docker compose up -d
```

Verify:

* [http://localhost:9200](http://localhost:9200) → Elasticsearch
* [http://localhost:5601](http://localhost:5601) → Kibana

### Step 5: Setup Elasticsearch Indices and Pipelines

Choose one of these methods:

#### Option A: Using Python (Recommended)

```bash
python main.py --setup
```

#### Option B: Using Shell Scripts

```bash
# Linux/Mac
./setup_elasticsearch.sh

# Windows
setup_elasticsearch.bat
```

#### Option C: Using HTTP Requests

Use the `es/create_index.http` file with REST Client VSCode extension or similar tools.

#### Option D: Using curl commands

```bash
# Create users index
curl -XPUT localhost:9200/blog-users -H "Content-Type: application/json" -d @es/users_mapping.json

# Create articles index
curl -XPUT localhost:9200/blog-articles -H "Content-Type: application/json" -d @es/articles_mapping.json

# Create users pipeline
curl -XPUT localhost:9200/_ingest/pipeline/blog-users-pipeline -H "Content-Type: application/json" -d @es/users_pipeline.json

# Create articles pipeline
curl -XPUT localhost:9200/_ingest/pipeline/blog-articles-pipeline -H "Content-Type: application/json" -d @es/articles_pipeline.json
```

### Step 6: Validate and Load Data

```bash
# Validate data
python main.py --validate

# First time: Load all data (with setup)
python main.py --load-all

# Subsequent runs: Load data only (faster)
python main.py --load-data
```

### Step 7: Start API Server (Optional)

```bash
# Start the FastAPI server for natural language search with LLM
python main.py --api

# Custom host/port
python main.py --api --host localhost --port 8000
```

The API will be available at:

- **API Server**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Example Queries**: http://localhost:8000/examples

## 📋 Usage Examples

### Basic Operations

```bash
# Setup indices and pipelines only
python main.py --setup

# Validate data with comprehensive relationship checks
python main.py --validate

# Validate data without relationship checks (faster)
python main.py --validate --skip-validation

# Load all data (setup + validation + loading)
python main.py --load-all

# Load data only (assumes indices/pipelines already exist)
python main.py --load-data

# Load only users
python main.py --load-users

# Load only articles
python main.py --load-articles

# Start API server for natural language search
python main.py --api
```

## 🔧 Configuration Options

| Option                  | Default                    | Description                                      |
| ----------------------- | -------------------------- | ------------------------------------------------ |
| `--es-url`            | `http://localhost:9200`  | Elasticsearch connection URL                     |
| `--users-index`       | `blog-users`             | Index name for users                             |
| `--articles-index`    | `blog-articles`          | Index name for articles                          |
| `--users-pipeline`    | `blog-users-pipeline`    | Pipeline name for users                          |
| `--articles-pipeline` | `blog-articles-pipeline` | Pipeline name for articles                       |
| `--data-file`         | `data/generated.json`    | Path to data file                                |
| `--log-level`         | `INFO`                   | Log level (DEBUG, INFO, WARNING, ERROR)          |
| `--skip-validation`   | `False`                  | Skip comprehensive relationship validation       |
| `--api`               | `False`                  | Start FastAPI server for natural language search |
| `--host`              | `localhost`              | API server host                                  |
| `--port`              | `8000`                   | API server port                                  |

## 🤖 API Features & Natural Language Search (Optional)

### LLM Integration

- **Query Refinement**: Convert natural language queries to Elasticsearch DSL using Azure OpenAI
- **Result Analysis**: Generate insights and summaries from search results
- **Chain of Thought**: Prompts with reasoning examples located in `config/prompts.py`
- **Error Handling**: Graceful fallbacks for LLM and Elasticsearch errors

### API Endpoints

- `POST /search/natural` - Natural language search with LLM processing
- `POST /search/elasticsearch` - Direct Elasticsearch DSL queries
- `GET /health` - System health check including LLM status
- `GET /examples` - Example queries for testing
- `GET /indices` - Available indices information

### Example Usage

```bash
# Natural language search
curl -X POST "http://localhost:8000/search/natural" \
  -H "Content-Type: application/json" \
  -d '{"query": "Find popular articles about Agents", "size": 5}'

# User-focused queries
curl -X POST "http://localhost:8000/search/natural" \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me active users with low social influence"}'
```

### Service Architecture

- **SearchService**: Clean interface for Elasticsearch operations
- **LLMService**: Azure OpenAI integration with proper error handling
- **FastAPI**: RESTful API with automatic documentation
- **Centralized Configuration**: All prompts and settings in dedicated config files

## 📊 Data Models & Validation

### User Model

- **Flexible fields**: All fields are optional (no required validation)
- **Relationship arrays**: `likes`, `dislikes`, `bookmarks`, `following`, `followers` can contain 0 values
- **Computed fields**: Automatically calculates engagement metrics for Elasticsearch
- **Validation**: Email format, relationship integrity, no self-following

### Article Model

- **Flexible fields**: All fields are optional (no required validation)
- **Flexible tags**: Simple string array without enum restrictions
- **Enhanced search**: Automatically creates searchable content fields
- **Validation**: Author references, engagement metrics consistency

### Validation

The system performs validation at multiple levels:

1. **JSON Schema validation**: Basic structure and type checking
2. **Pydantic model validation**: Type safety and field validation
3. **Relationship validation**: Cross-reference integrity checks
   - User likes/dislikes/bookmarks reference existing articles
   - Article authors reference existing users
   - Following/follower relationships are valid
   - No self-referencing relationships
   - Engagement metrics consistency

## 🏗️ Elasticsearch Configuration

### Index Mappings

**Users Index Features:**

- Full-text search on names
- Keyword fields for exact matches
- Date parsing for timestamps
- Computed engagement metrics
- Social influence scoring

**Articles Index Features:**

- Full-text search on title and content
- Keyword tags for filtering
- Date parsing for timestamps
- Engagement ratio calculations
- Reading time estimation
- Content categorization

### Ingest Pipelines

**Users Pipeline:**

- Adds processing timestamp
- Calculates user activity level (high/medium/low)
- Computes social influence score

**Articles Pipeline:**

- Adds processing timestamp
- Calculates reading time based on content length
- Computes popularity score from engagement metrics
- Sets technical content flag based on tags

## Data Validators

The system includes comprehensive data validation capabilities through the `DataValidator` class, ensuring data integrity and consistency across all entities:

### Validation Types

**1. Schema Validation:**
- JSON schema compliance checking
- Pydantic model validation for type safety
- Field format validation (emails, dates, etc.)

**2. Relationship Validation:**
- Cross-reference integrity between users and articles
- Author ID validation (articles must reference existing users)
- Social graph consistency (following/follower relationships)
- Engagement reference validation (likes/dislikes/bookmarks reference valid articles)

**3. Logic Validation:**
- Prevents self-referencing relationships (users can't follow themselves)
- Detects conflicting user actions (liking and disliking same articles)
- Validates engagement metrics consistency (likes counts vs actual user interactions)
- Checks for impossible data (likes exceeding views)

### Cross-Reference Validation

The validator performs sophisticated cross-entity checks:

- **Article → User References**: Every article's `author_id` must exist in the users dataset
- **User → Article References**: All user likes, dislikes, and bookmarks must reference existing articles
- **Social Graph Integrity**: Following/follower relationships are checked for symmetry and validity
- **Engagement Consistency**: Article engagement counts are validated against actual user interactions

### Validation Output

The system provides detailed validation reporting:

```bash
# Example validation output
2024-08-13 12:00:00 - INFO - Starting comprehensive data validation
2024-08-13 12:00:00 - INFO - Validating 20 users and 50 articles
2024-08-13 12:00:00 - INFO - Found 20 unique user IDs and 50 unique article IDs
2024-08-13 12:00:00 - INFO - Validating user data...
2024-08-13 12:00:00 - INFO - Validating article data...
2024-08-13 12:00:00 - INFO - Validating cross-references...
2024-08-13 12:00:00 - WARNING - User 1: User both likes and dislikes articles: [5]
2024-08-13 12:00:00 - INFO - Validation completed: 0 errors, 3 warnings
2024-08-13 12:00:00 - INFO - ✓ Data validation passed
```

### Validation Statistics

The validator tracks comprehensive statistics:
- Total entities validated
- Unique ID counts and duplicates detected
- Cross-reference success/failure rates
- Warning and error categorization
- Performance metrics for large datasets


### Logging

- **Centralized logging** with timestamped files in `logs/` directory
- **Console + file output** for comprehensive tracking
- **Configurable log levels** via command line
- **Automatic log file naming**: `elasticsearch_loader_YYYYMMDD_HHMMSS.log`
- **Detailed validation reporting** with error and warning summaries

## 🌐 Kibana Integration

After loading data, you can explore it in Kibana:

1. **Open Kibana**: http://localhost:5601
2. **Create Index Patterns**:
   - `blog-users*` for users data
   - `blog-articles*` for articles data
3. **Explore Data**:
   - Use Discover to browse documents
   - Create visualizations for engagement metrics
   - Build dashboards for user activity and content performance

### Sample Kibana Queries

```json
# Find highly engaged users
GET blog-users/_search
{
  "query": {
    "range": {
      "engagement_score": {
        "gte": 10
      }
    }
  }
}

# Find popular published articles
GET blog-articles/_search
{
  "query": {
    "bool": {
      "must": [
        {"term": {"is_published": true}},
        {"range": {"popularity_score": {"gte": 100}}}
      ]
    }
  }
}

# Search technical articles
GET blog-articles/_search
{
  "query": {
    "bool": {
      "must": [
        {"term": {"is_technical": true}},
        {"match": {"searchable_content": "python elasticsearch"}}
      ]
    }
  }
}
```

## 🛠️ Troubleshooting

### Common Issues

1. **Elasticsearch connection failed**

   ```bash
   # Check if Elasticsearch is running
   curl http://localhost:9200
   ```
2. **Data validation errors**

   ```bash
   # Run with detailed logging
   python main.py --validate --log-level DEBUG
   ```
3. **Index creation failed**

   ```bash
   # Check Elasticsearch logs and permissions
   # Ensure mapping files exist in es/ directory
   ```
4. **Permission errors**

   ```bash
   # Ensure logs directory is writable
   mkdir logs
   chmod 755 logs
   ```

## 📈 Performance Considerations

- **Bulk loading**: Uses Elasticsearch bulk API with configurable chunk sizes
- **Pipeline processing**: Ingest pipelines add computed fields efficiently
- **Validation optimization**: Relationship validation can be skipped for faster loading
- **Memory usage**: Streaming bulk operations for large datasets
- **Index settings**: Single shard for development, adjust for production

## 🎯 Key Features

- ✅ **Comprehensive**: Full data validation with relationship integrity
- ✅ **Automated**: Index and pipeline creation with graceful error handling
- ✅ **Flexible**: Optional fields, configurable validation
- ✅ **Robust**: Multi-level error handling and logging with debug support
- ✅ **Fast**: Bulk loading with pipeline processing
- ✅ **Clean**: Simple architecture, well-documented
- ✅ **Production-ready**: Proper mappings and ingest pipelines
- ✅ **Debug-friendly**: Comprehensive logging for troubleshooting
- ✅ **Error-resilient**: Continues operation even when some components fail

## 📚 Complete Step-by-Step Example

Here's a complete workflow from setup to data exploration:

```bash
# 1. Setup environment
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# 2. Start Elasticsearch (make sure it's running)

# 3. Setup indices and pipelines
python main.py --setup

# 4. Validate data thoroughly
python main.py --validate

# 5. Load all data (first time with setup)
python main.py --load-all

# 5b. Or load data only (if indices already exist)
python main.py --load-data

# 6. Check results
# - View logs in logs/ directory
# - Open Kibana at http://localhost:5601
# - Create index patterns: blog-users*, blog-articles*
# - Explore your data!
```

## 🔧 Recent Improvements & Fixes

### Enhanced Error Handling

- **Index Creation**: Gracefully handles existing indices and version compatibility issues
- **Pipeline Creation**: Continues operation even when pipelines fail due to Elasticsearch version differences
- **LLM Integration**: Robust JSON parsing with support for double curly braces format
- **Bulk Operations**: Enhanced error reporting for failed document indexing

### Debug Logging System

- **Comprehensive Coverage**: All services now include detailed debug logging
- **Step-by-step Tracking**: API endpoints log each processing step
- **Raw Response Logging**: LLM responses are logged for troubleshooting
- **Error Context**: Detailed error information with context and suggestions

### LLM Prompt Improvements

- **Double Curly Braces Support**: Prompts now use `{{` and `}}` format for better LLM responses
- **Clear Instructions**: Prompts explicitly request JSON-only responses
- **Better Examples**: More realistic query examples for improved LLM understanding

## 📄 License

This project is licensed under the **MIT License**. See [`LICENSE`](./LICENSE) for details.

## 🧠 Author

Built by [Nguyen Quang Phu (pdz1804)](https://github.com/pdz1804).

## 🙋‍♂️ Contact

Reach out or open an [issue](https://github.com/pdz1804/search-rec-sys-blog/issues) for support or ideas.

