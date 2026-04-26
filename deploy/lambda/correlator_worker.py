import boto3, json, os
from app.correlation.correlator import correlate_once

def lambda_handler(event, context):
    correlate_once()
    return {"status": "correlation_done"}
