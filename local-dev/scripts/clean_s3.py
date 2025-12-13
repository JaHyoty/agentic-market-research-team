#!/usr/bin/env python3
import boto3
import os

def get_local_s3():
    return boto3.resource(
        's3',
        endpoint_url=os.environ.get('AWS_ENDPOINT_URL', 'http://localhost:4566'),
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1'
    )

def clean_buckets():
    s3 = get_local_s3()
    buckets = ['market-research-artifacts', 'market-research-reports']
    
    for bucket_name in buckets:
        try:
            bucket = s3.Bucket(bucket_name)
            print(f"Cleaning bucket: {bucket_name}...")
            bucket.objects.all().delete()
            print(f"Bucket {bucket_name} cleaned.")

            # Now clean reports directory
            reports_dir = "../reports"
            if os.path.exists(reports_dir):
                for file in os.listdir(reports_dir):
                    filepath = os.path.join(reports_dir, file)
                    try:
                        if os.path.isfile(filepath):
                            os.remove(filepath)

                        elif os.path.isdir(filepath):
                            os.rmdir(filepath)
                    except Exception as e:
                        print(f"Error cleaning file {filepath}: {e}")
        except Exception as e:
            print(f"Error cleaning bucket {bucket_name}: {e}")
    
    print("All buckets and reports cleaned.")

if __name__ == "__main__":
    clean_buckets()
