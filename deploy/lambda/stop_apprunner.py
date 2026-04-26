import os
import boto3


def lambda_handler(event, context):
    ec2 = boto3.client("ec2")
    instance_id = os.environ["EC2_INSTANCE_ID"]
    ec2.stop_instances(InstanceIds=[instance_id])
    return {"status": "stopped", "instance_id": instance_id}
