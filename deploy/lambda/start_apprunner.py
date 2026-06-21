import os
import boto3


def lambda_handler(event, context):
    ec2 = boto3.client("ec2")
    instance_id = os.environ["EC2_INSTANCE_ID"]
    ec2.start_instances(InstanceIds=[instance_id])
    return {"status": "started", "instance_id": instance_id}
