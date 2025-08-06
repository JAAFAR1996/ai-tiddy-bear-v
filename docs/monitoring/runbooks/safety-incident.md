# Safety Incident Response Runbook

## Alert: CriticalSafetyIncident / SafetyIncidentsSpike

**Severity**: Critical  
**Response Time**: < 2 minutes  
**Escalation**: Immediate notification to Safety Team

---

## Immediate Actions (0-2 minutes)

### 1. Acknowledge Alert
```bash
# Acknowledge in PagerDuty/AlertManager
curl -X POST "https://api.pagerduty.com/incidents/{incident_id}/acknowledge" \
  -H "Authorization: Token token={your_token}"
```

### 2. Check Safety Metrics
```bash
# View current safety incidents
curl http://conversation-service:8000/metrics | grep safety_incidents

# Check recent safety violations
kubectl logs -l app=conversation-service | grep "SAFETY_VIOLATION" | tail -20
```

### 3. Identify Affected Conversations
```bash
# Query recent safety incidents from database
psql -h postgres-host -d ai_teddy_bear -c "
SELECT 
    conversation_id,
    child_id,
    incident_type,
    severity,
    created_at,
    metadata
FROM safety_incidents 
WHERE created_at >= NOW() - INTERVAL '10 minutes'
ORDER BY created_at DESC;
"
```

---

## Investigation (2-10 minutes)

### 4. Analyze Incident Pattern
```bash
# Check for patterns in safety violations
kubectl logs -l app=conversation-service | grep "SAFETY_VIOLATION" | \
  jq '.incident_type' | sort | uniq -c | sort -nr

# Check if specific child IDs are involved
kubectl logs -l app=conversation-service | grep "SAFETY_VIOLATION" | \
  jq '.child_id' | sort | uniq -c | sort -nr
```

### 5. Review Conversation Content
```python
# Connect to database and review flagged content
import psycopg2
conn = psycopg2.connect("postgresql://user:pass@host/ai_teddy_bear")
cur = conn.cursor()

# Get recent flagged messages
cur.execute("""
    SELECT m.content, m.safety_score, m.metadata, c.child_id
    FROM messages m
    JOIN conversations c ON m.conversation_id = c.id
    WHERE m.safety_score < 0.5
    AND m.created_at >= NOW() - INTERVAL '10 minutes'
    ORDER BY m.created_at DESC;
""")

for row in cur.fetchall():
    print(f"Content: {row[0][:100]}...")
    print(f"Safety Score: {row[1]}")
    print(f"Child ID: {row[3]}")
    print("---")
```

### 6. Check AI Provider Responses
```bash
# Look for inappropriate AI responses
kubectl logs -l app=conversation-service | grep "AI_RESPONSE" | \
  grep -E "(safety_score|content_flag)" | tail -10
```

---

## Containment Actions (5-15 minutes)

### 7. Pause Affected Conversations
```python
# Emergency conversation pause script
import asyncio
from src.services.conversation_service import ConsolidatedConversationService

async def emergency_pause_conversations(child_ids):
    service = await get_conversation_service()
    
    for child_id in child_ids:
        try:
            # Get active conversations for child
            conversations = await service.get_active_conversations_for_child(child_id)
            
            for conv in conversations:
                # Pause conversation
                await service.pause_conversation(conv.id, reason="safety_incident")
                print(f"Paused conversation {conv.id} for child {child_id}")
                
        except Exception as e:
            print(f"Error pausing conversations for {child_id}: {e}")

# Run for affected children
affected_child_ids = ["child_id_1", "child_id_2"]  # From investigation
asyncio.run(emergency_pause_conversations(affected_child_ids))
```

### 8. Notify Parents (if required)
```python
# Send safety notification to parents
from src.services.notification_service import NotificationService

async def notify_parents_of_incident(child_ids):
    notification_service = await get_notification_service()
    
    for child_id in child_ids:
        try:
            await notification_service.send_safety_incident_notification(
                child_id=child_id,
                incident_type="content_safety",
                severity="high",
                immediate=True
            )
        except Exception as e:
            print(f"Failed to notify parent for child {child_id}: {e}")
```

---

## Resolution (15-30 minutes)

### 9. Update Safety Filters
```bash
# If pattern identified, update safety rules
# This should be done by Safety Team

# Deploy updated safety filters
kubectl apply -f k8s/safety-config.yaml

# Restart conversation service to reload config
kubectl rollout restart deployment/conversation-service
```

### 10. Review and Update AI Prompts
```python
# If AI responses are problematic, update system prompts
# Update in src/services/ai_provider_service.py

# Example safety prompt enhancement
ENHANCED_SAFETY_PROMPT = """
You are a friendly AI assistant for children aged 3-13.
CRITICAL SAFETY RULES:
- Never discuss inappropriate topics
- Always maintain child-appropriate language
- Refuse any requests for harmful content
- If unsure, err on the side of caution

Previous safety incident detected. Extra caution required.
"""
```

### 11. Database Cleanup (if needed)
```sql
-- Mark unsafe messages as hidden
UPDATE messages 
SET is_hidden = true, 
    hidden_reason = 'safety_incident',
    updated_at = NOW()
WHERE safety_score < 0.3 
AND created_at >= NOW() - INTERVAL '1 hour';

-- Log the cleanup action
INSERT INTO audit_log (action, details, performed_by, performed_at)
VALUES (
    'safety_cleanup',
    'Hidden unsafe messages following safety incident',
    'safety_team',
    NOW()
);
```

---

## Recovery (30-60 minutes)

### 12. Resume Conversations
```python
# After safety measures implemented, resume conversations
async def resume_safe_conversations(child_ids):
    service = await get_conversation_service()
    
    for child_id in child_ids:
        try:
            # Resume with enhanced safety mode
            await service.resume_conversation_with_enhanced_safety(child_id)
            print(f"Resumed safe conversations for child {child_id}")
        except Exception as e:
            print(f"Error resuming conversations for {child_id}: {e}")
```

### 13. Monitor for Recurrence
```bash
# Set up enhanced monitoring for next 24 hours
# Add temporary alert with lower threshold
cat << EOF > /tmp/enhanced_safety_alert.yml
- alert: EnhancedSafetyMonitoring
  expr: increase(conversation_service_safety_incidents_total[1m]) > 0
  for: 0s
  labels:
    severity: warning
    temporary: "true"
  annotations:
    summary: "Any safety incident during enhanced monitoring period"
EOF

# Apply enhanced monitoring
kubectl apply -f /tmp/enhanced_safety_alert.yml
```

---

## Post-Incident (1-24 hours)

### 14. Generate Incident Report
```python
# Generate comprehensive incident report
from datetime import datetime, timedelta

async def generate_safety_incident_report(incident_start_time):
    report = {
        "incident_id": f"SAFETY_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "start_time": incident_start_time,
        "end_time": datetime.now(),
        "affected_children": [],
        "incident_types": [],
        "actions_taken": [],
        "lessons_learned": []
    }
    
    # Populate report with data from investigation
    # Save to incident tracking system
    
    return report
```

### 15. Safety Team Review
- [ ] Conduct safety team review meeting
- [ ] Update safety policies if needed  
- [ ] Review AI training data for gaps
- [ ] Update parent communication if required
- [ ] Document lessons learned

### 16. Technical Improvements
- [ ] Review safety filter effectiveness
- [ ] Update monitoring thresholds if needed
- [ ] Improve incident response automation
- [ ] Update safety training for AI models

---

## Prevention

### Regular Actions
- Daily safety metrics review
- Weekly safety filter updates
- Monthly AI model retraining
- Quarterly safety audit

### Code Changes
```python
# Enhanced safety logging
logger.info(
    "SAFETY_CHECK_RESULT",
    extra={
        "conversation_id": conversation_id,
        "child_id": child_id,
        "safety_score": safety_score,
        "content_preview": content[:50],
        "filters_triggered": triggered_filters,
        "timestamp": datetime.utcnow().isoformat()
    }
)
```

---

## Contact Information

**Primary**: Safety Team (safety-team@example.com)  
**Secondary**: Backend On-Call (backend-oncall@example.com)  
**Escalation**: CTO (cto@example.com)  

**Emergency Hotline**: +1-555-SAFETY  
**Slack Channel**: #safety-incidents
