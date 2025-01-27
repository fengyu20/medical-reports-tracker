import boto3
import os
from datetime import datetime, UTC, timedelta
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import tempfile

load_dotenv()

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION')
        )
        self.bucket_name = os.getenv('AWS_S3_BUCKET')

    def upload_file(self, file, user_id, indicators=None, cognito_token=None):
        """
        Uploads a file to S3 with user ID, indicators, and Cognito token embedded in the metadata.
        """
        temp_file = None
        try:
            # Create a temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            file.save(temp_file.name)
            
            # Generate file key
            timestamp = datetime.now(UTC).strftime('%Y%m%d%H%M%S')
            file_key = f"uploads/{user_id}/{timestamp}_{file.filename}"
            
            # Prepare upload parameters with metadata
            upload_args = {
                'Bucket': self.bucket_name,
                'Key': file_key,
                'Body': open(temp_file.name, 'rb'),
                'ContentType': file.content_type,
                'Metadata': {
                    'UserId': user_id,
                    'UploadDate': timestamp,
                    'Indicators': ','.join(indicators) if indicators else '',
                    'CognitoToken': cognito_token if cognito_token else ''
                }
            }
            
            # Upload to S3
            self.s3_client.upload_fileobj(**upload_args)
            
            return file_key

        except Exception as e:
            print(f"Error uploading file: {str(e)}")
            raise
        finally:
            if temp_file:
                temp_file.close()
                os.unlink(temp_file.name)

    def generate_presigned_url(self, file_key, expiration=3600):
        """
        Generate a presigned URL for the S3 object
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': file_key
                },
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            print(f"Error generating presigned URL: {str(e)}")
            raise

    def cleanup_old_files(self, user_id, days_old=7):
        """
        Cleanup files older than specified days
        """
        try:
            # Calculate cutoff date
            cutoff_date = datetime.now(UTC) - timedelta(days=days_old)
            
            # List objects in user's folder
            paginator = self.s3_client.get_paginator('list_objects_v2')
            prefix = f"uploads/{user_id}/"
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                for obj in page.get('Contents', []):
                    if obj['LastModified'].replace(tzinfo=UTC) < cutoff_date:
                        self.s3_client.delete_object(
                            Bucket=self.bucket_name,
                            Key=obj['Key']
                        )
                        print(f"Deleted old file: {obj['Key']}")
                        
        except Exception as e:
            print(f"Error in cleanup: {str(e)}")
            # Don't raise the error as this is a cleanup task

# Initialize S3 service
s3_service = S3Service()

# Export functions that use the service
def upload_file_to_s3(file, user_id, indicators=None, cognito_token=None):
    return s3_service.upload_file(file, user_id, indicators, cognito_token)

def generate_presigned_url(file_key, expiration=3600):
    return s3_service.generate_presigned_url(file_key, expiration)

def cleanup_old_files(user_id, days_old=7):
    return s3_service.cleanup_old_files(user_id, days_old)
