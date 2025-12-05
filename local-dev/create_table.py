import boto3
from backend.app.config import settings

def create_table():
    dynamodb = boto3.client(
        'dynamodb',
        endpoint_url=settings.DYNAMODB_ENDPOINT,
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
    )
    
    try:
        dynamodb.describe_table(TableName=settings.DYNAMODB_TABLE_TASKS)
        print(f"Table {settings.DYNAMODB_TABLE_TASKS} already exists.")
        return
    except dynamodb.exceptions.ResourceNotFoundException:
        # Table does not exist, proceed to create
        pass
    except Exception as e:
        print(f"Error checking table: {e}")
        return

    try:
        dynamodb.create_table(
            TableName=settings.DYNAMODB_TABLE_TASKS,
            KeySchema=[{'AttributeName': 'task_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'task_id', 'AttributeType': 'S'}],
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )
        print(f"Table {settings.DYNAMODB_TABLE_TASKS} created.")
    except Exception as e:
        print(f"Error creating table: {e}")

if __name__ == "__main__":
    create_table()
