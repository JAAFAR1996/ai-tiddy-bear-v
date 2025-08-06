# Production Logging Setup Guide

## Overview

This guide explains how to set up production-ready logging for the AI Teddy Bear system with:
- **ELK Stack** (Elasticsearch, Logstash, Kibana) for log aggregation and analysis
- **CloudWatch Logs** for AWS cloud logging
- **Structured JSON logging** with correlation tracking
- **Security-aware logging** with PII protection
- **Child safety compliance** logging (COPPA)

## Environment Variables

Set these environment variables for production:

```bash
# Log Level
LOG_LEVEL=INFO

# ELK Stack Configuration
ELASTICSEARCH_HOSTS=elasticsearch-1:9200,elasticsearch-2:9200
ELASTICSEARCH_USERNAME=elastic
ELASTICSEARCH_PASSWORD=your_password
ELASTICSEARCH_INDEX=ai-teddy-bear-logs
ELASTICSEARCH_TIMEOUT=30

# CloudWatch Configuration  
CLOUDWATCH_LOG_GROUP=/aws/ai-teddy-bear/production
AWS_REGION=us-east-1
CLOUDWATCH_RETENTION_DAYS=30

# Log Aggregation Settings
LOG_BATCH_SIZE=100
LOG_FLUSH_INTERVAL=5
LOG_MAX_QUEUE_SIZE=10000
LOG_RETENTION_DAYS=90
LOG_ARCHIVE_DAYS=30

# File Logging
LOG_DIR=./logs
ENABLE_CONSOLE_LOGGING=true
ENABLE_FILE_LOGGING=true
```

## ELK Stack Setup

### 1. Elasticsearch Configuration

Create `elasticsearch.yml`:

```yaml
cluster.name: ai-teddy-bear-logs
node.name: elasticsearch-1
network.host: 0.0.0.0
http.port: 9200
discovery.seed_hosts: ["elasticsearch-2:9300"]
cluster.initial_master_nodes: ["elasticsearch-1", "elasticsearch-2"]

# Security
xpack.security.enabled: true
xpack.security.enrollment.enabled: true

# Index lifecycle management
xpack.ilm.enabled: true
```

### 2. Logstash Configuration

Create `logstash.conf`:

```ruby
input {
  beats {
    port => 5044
  }
  
  http {
    port => 8080
    codec => json
  }
}

filter {
  # Parse JSON logs
  if [message] =~ /^\{.*\}$/ {
    json {
      source => "message"
    }
  }
  
  # Add child safety tags
  if [category] == "child_safety" {
    mutate {
      add_tag => ["child_safety", "compliance"]
    }
  }
  
  # Add security tags
  if [category] == "security" {
    mutate {
      add_tag => ["security", "alert"]
    }
  }
  
  # Enrich with GeoIP if IP address present
  if [client_ip] {
    geoip {
      source => "client_ip"
      target => "geoip"
    }
  }
  
  # Parse correlation IDs
  if [correlation_id] {
    mutate {
      add_field => { "[@metadata][correlation_id]" => "%{correlation_id}" }
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch-1:9200", "elasticsearch-2:9200"]
    user => "elastic"
    password => "${ELASTIC_PASSWORD}"
    index => "ai-teddy-bear-logs-%{+YYYY.MM.dd}"
    template_name => "ai-teddy-bear-logs"
    template_pattern => "ai-teddy-bear-logs-*"
    template => "/usr/share/logstash/templates/ai-teddy-bear-template.json"
    template_overwrite => true
  }
  
  # Output to stdout for debugging
  stdout {
    codec => rubydebug
  }
}
```

### 3. Kibana Configuration

Create `kibana.yml`:

```yaml
server.name: kibana
server.host: 0.0.0.0
elasticsearch.hosts: ["http://elasticsearch-1:9200", "http://elasticsearch-2:9200"]
elasticsearch.username: "kibana_system"
elasticsearch.password: "${KIBANA_PASSWORD}"

# Security
xpack.security.enabled: true
xpack.encryptedSavedObjects.encryptionKey: "your-encryption-key-here"
```

### 4. Docker Compose for ELK Stack

Create `docker-compose.elk.yml`:

```yaml
version: '3.8'

services:
  elasticsearch-1:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: elasticsearch-1
    environment:
      - node.name=elasticsearch-1
      - cluster.name=ai-teddy-bear-logs
      - discovery.seed_hosts=elasticsearch-2
      - cluster.initial_master_nodes=elasticsearch-1,elasticsearch-2
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
      - xpack.security.enabled=true
      - ELASTIC_PASSWORD=${ELASTIC_PASSWORD}
    ulimits:
      memlock:
        soft: -1
        hard: -1
    volumes:
      - elasticsearch-1-data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"
    networks:
      - elk

  elasticsearch-2:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: elasticsearch-2
    environment:
      - node.name=elasticsearch-2
      - cluster.name=ai-teddy-bear-logs
      - discovery.seed_hosts=elasticsearch-1
      - cluster.initial_master_nodes=elasticsearch-1,elasticsearch-2
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
      - xpack.security.enabled=true
      - ELASTIC_PASSWORD=${ELASTIC_PASSWORD}
    ulimits:
      memlock:
        soft: -1
        hard: -1
    volumes:
      - elasticsearch-2-data:/usr/share/elasticsearch/data
    networks:
      - elk

  logstash:
    image: docker.elastic.co/logstash/logstash:8.11.0
    container_name: logstash
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf:ro
      - ./templates:/usr/share/logstash/templates:ro
    ports:
      - "5044:5044"
      - "8080:8080"
    environment:
      - "LS_JAVA_OPTS=-Xmx1g -Xms1g"
      - ELASTIC_PASSWORD=${ELASTIC_PASSWORD}
    networks:
      - elk
    depends_on:
      - elasticsearch-1
      - elasticsearch-2

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    container_name: kibana
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch-1:9200
      - ELASTICSEARCH_USERNAME=kibana_system
      - ELASTICSEARCH_PASSWORD=${KIBANA_PASSWORD}
    networks:
      - elk
    depends_on:
      - elasticsearch-1
      - elasticsearch-2

volumes:
  elasticsearch-1-data:
    driver: local
  elasticsearch-2-data:
    driver: local

networks:
  elk:
    driver: bridge
```

## CloudWatch Setup

### 1. IAM Policy for CloudWatch Logs

Create IAM policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "logs:DescribeLogGroups",
                "logs:DescribeLogStreams",
                "logs:PutRetentionPolicy"
            ],
            "Resource": "arn:aws:logs:*:*:log-group:/aws/ai-teddy-bear/*"
        }
    ]
}
```

### 2. CloudWatch Dashboard

Create CloudWatch dashboard configuration:

```json
{
    "widgets": [
        {
            "type": "log",
            "properties": {
                "query": "SOURCE '/aws/ai-teddy-bear/production'\n| fields @timestamp, level, category, message\n| filter level = \"ERROR\"\n| sort @timestamp desc\n| limit 100",
                "region": "us-east-1",
                "title": "Error Logs (Last 100)",
                "view": "table"
            }
        },
        {
            "type": "log",
            "properties": {
                "query": "SOURCE '/aws/ai-teddy-bear/production'\n| fields @timestamp, child_id, message\n| filter category = \"child_safety\"\n| sort @timestamp desc\n| limit 50",
                "region": "us-east-1",
                "title": "Child Safety Events",
                "view": "table"
            }
        },
        {
            "type": "metric",
            "properties": {
                "metrics": [
                    [ "AWS/Logs", "IncomingLogEvents", "LogGroupName", "/aws/ai-teddy-bear/production" ]
                ],
                "period": 300,
                "stat": "Sum",
                "region": "us-east-1",
                "title": "Log Volume"
            }
        }
    ]
}
```

### 3. CloudWatch Alarms

```bash
# Create alarm for error rate
aws cloudwatch put-metric-alarm \
    --alarm-name "ai-teddy-bear-error-rate" \
    --alarm-description "High error rate detected" \
    --metric-name "ErrorCount" \
    --namespace "AITeddyBear/Logs" \
    --statistic "Sum" \
    --period 300 \
    --threshold 10 \
    --comparison-operator "GreaterThanThreshold" \
    --evaluation-periods 2

# Create alarm for child safety events
aws cloudwatch put-metric-alarm \
    --alarm-name "ai-teddy-bear-child-safety" \
    --alarm-description "Child safety violations detected" \
    --metric-name "ChildSafetyEvents" \
    --namespace "AITeddyBear/Logs" \
    --statistic "Sum" \
    --period 300 \
    --threshold 1 \
    --comparison-operator "GreaterThanThreshold" \
    --evaluation-periods 1
```

## Application Integration

### 1. FastAPI Application Setup

```python
from fastapi import FastAPI
from src.infrastructure.logging import (
    setup_fastapi_logging, configure_logging,
    logging_integration
)

# Configure logging
configure_logging(
    level="INFO",
    elasticsearch_hosts="elasticsearch-1:9200,elasticsearch-2:9200",
    cloudwatch_log_group="/aws/ai-teddy-bear/production"
)

# Create FastAPI app
app = FastAPI(title="AI Teddy Bear API")

# Setup comprehensive logging
setup_fastapi_logging(app, enable_all_middleware=True)

@app.on_event("startup")
async def startup_event():
    await logging_integration.start()

@app.on_event("shutdown") 
async def shutdown_event():
    await logging_integration.stop()
```

### 2. Business Logic Integration

```python
from src.infrastructure.logging import (
    get_logger, log_business_operation, child_safety_logger
)

logger = get_logger("story_service")

@log_business_operation("story_generation", child_id="child_123")
async def generate_story(child_id: str, prompt: str) -> dict:
    """Generate story with comprehensive logging."""
    
    # Log child interaction
    child_safety_logger.child_safety(
        "Story generation requested",
        child_id=child_id,
        metadata={
            "prompt_length": len(prompt),
            "safety_checked": True
        }
    )
    
    # Your business logic here
    story = await ai_provider.generate_story(prompt)
    
    # Log completion
    logger.info(
        "Story generated successfully",
        category=LogCategory.BUSINESS,
        metadata={
            "story_id": story["id"],
            "word_count": story["word_count"],
            "generation_time_ms": story["generation_time"]
        }
    )
    
    return story
```

## Monitoring and Alerting

### 1. Kibana Dashboards

Import these dashboard configurations:

- **System Overview**: Log volume, error rates, response times
- **Child Safety Monitor**: COPPA compliance, safety violations, parental controls
- **Security Dashboard**: Authentication events, security violations, audit logs
- **Performance Monitor**: API response times, provider performance, resource usage

### 2. Log Retention Policies

```python
# Elasticsearch Index Lifecycle Policy
{
    "policy": {
        "phases": {
            "hot": {
                "actions": {
                    "rollover": {
                        "max_size": "5GB",
                        "max_age": "1d"
                    }
                }
            },
            "warm": {
                "min_age": "7d",
                "actions": {
                    "allocate": {
                        "number_of_replicas": 0
                    }
                }
            },
            "cold": {
                "min_age": "30d",
                "actions": {
                    "allocate": {
                        "number_of_replicas": 0
                    }
                }
            },
            "delete": {
                "min_age": "90d"
            }
        }
    }
}
```

## Security and Compliance

### 1. PII Protection

The logging system automatically:
- Filters sensitive information (passwords, tokens, SSNs)
- Masks child data according to COPPA requirements
- Hashes identifiers while maintaining correlation
- Removes PII patterns from log messages

### 2. COPPA Compliance

- Child IDs are hashed for privacy
- Parental consent tracking in audit logs
- Age verification events logged
- Data retention policies enforced

### 3. Security Events

All security events are logged with:
- IP address and geolocation
- User agent and session information
- Action taken (blocked, allowed, flagged)
- Correlation with business events

## Deployment Checklist

- [ ] Environment variables configured
- [ ] ELK Stack deployed and configured
- [ ] CloudWatch log groups created
- [ ] IAM policies applied
- [ ] Log rotation configured
- [ ] Monitoring dashboards created
- [ ] Alerting rules configured
- [ ] Security filters tested
- [ ] COPPA compliance verified
- [ ] Performance benchmarks established

## Troubleshooting

### Common Issues

1. **Elasticsearch connection failed**
   - Check network connectivity
   - Verify credentials
   - Check cluster health

2. **CloudWatch logs not appearing**
   - Verify IAM permissions
   - Check AWS region configuration
   - Validate log group exists

3. **High log volume**
   - Increase batch size
   - Adjust flush interval
   - Check Elasticsearch cluster capacity

4. **Missing correlation IDs**
   - Ensure middleware is properly configured
   - Check context propagation in async operations
   - Verify FastAPI integration

For more troubleshooting, check the application logs and monitoring dashboards.