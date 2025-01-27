import json
import boto3
import logging
import os
import urllib.parse
from datetime import datetime
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
textract_client = boto3.client('textract')
sns_client = boto3.client('sns')

# Environment variables
RESULT_BUCKET = os.environ.get('RESULT_BUCKET')      # Destination bucket for Textract results
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')      # SNS topic ARN for Textract notifications
ROLE_ARN = os.environ.get('ROLE_ARN')                # IAM role ARN for Textract

# Validate environment variables
if not RESULT_BUCKET or not SNS_TOPIC_ARN or not ROLE_ARN:
    logger.error("One or more required environment variables (RESULT_BUCKET, SNS_TOPIC_ARN, ROLE_ARN) are missing.")
    raise ValueError("Missing required environment variables.")

def lambda_handler(event, context):
    """
    Lambda function to process SQS messages from S3 Event Notifications and Textract notifications.
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    for sqs_record in event.get('Records', []):
        try:
            message_body = json.loads(sqs_record.get('body', '{}'))
            
            # Flag to determine if the message has been processed
            processed = False
            
            # Check if the message is an S3 Event Notification
            if 'Records' in message_body:
                for record in message_body['Records']:
                    if record.get('eventSource') == 'aws:s3':
                        logger.info("Handling S3 Event Notification.")
                        handle_s3_event(record)
                        processed = True
                        break  # Assuming each message contains only one relevant record
            
            # If not processed yet, check if it's a Textract Job Notification
            if not processed:
                if 'JobId' in message_body and 'Status' in message_body:
                    logger.info("Handling Textract Job Notification.")
                    handle_textract_notification(message_body)
                    processed = True
            
            if not processed:
                logger.warning("Unknown message format. Skipping.")
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for record {sqs_record}: {e}")
        except Exception as e:
            logger.error(f"Error processing record {sqs_record}: {e}")
            # Optionally, handle the exception (e.g., move message to a dead-letter queue)
            continue

def handle_s3_event(s3_record):
    """
    Processes S3 Event Notifications and initiates Textract jobs.
    """
    s3_bucket = s3_record['s3']['bucket']['name']
    s3_key = urllib.parse.unquote_plus(s3_record['s3']['object']['key'])

    logger.info(f"Processing S3 object: s3://{s3_bucket}/{s3_key}")

    # Extract user_id, unique_id, and filename from the key
    try:
        key_parts = s3_key.split('/')
        if len(key_parts) < 5:
            raise ValueError("Invalid key structure. Expected format: metadata/uploads/<user_id>/<unique_id>/<filename>")
        
        user_id = key_parts[2]         # 'c129000e-30b1-702e-33ae-eec0ec14be40'
        unique_id = key_parts[3]       # '948c83b7-426f-4e9c-821e-ba0efec45db8'
        filename = key_parts[4]        # 'report_2.jpg.json'

        # Derive main file key (include 'uploads/' prefix and remove '.json' suffix)
        main_file_key = derive_main_file_key(s3_key)  # 'uploads/c129000e-30b1-702e-33ae-eec0ec14be40/948c83b7-426f-4e9c-821e-ba0efec45db8/report_2.jpg'
        logger.info(f"Derived main_file_key: {main_file_key}")

        # Ensure the main_file_key is in the correct format
        if not main_file_key.endswith(('.jpg', '.jpeg', '.png', '.pdf')):
            raise ValueError(f"Unsupported file type for Textract: {main_file_key}")

        # Prepare the result prefix to avoid duplicate 'uploads/'
        original_filename = os.path.splitext(os.path.basename(main_file_key))[0]  # 'report_2'
        result_prefix = construct_result_key(main_file_key)
        logger.info(f"Constructed result_prefix: {result_prefix}")

        # Start Textract job with NotificationChannel and OutputConfig
        response = textract_client.start_document_analysis(
            DocumentLocation={'S3Object': {'Bucket': s3_bucket, 'Name': main_file_key}},
            FeatureTypes=['FORMS', 'TABLES'],  # Customize as needed
            NotificationChannel={
                "SNSTopicArn": SNS_TOPIC_ARN,
                "RoleArn": ROLE_ARN
            },
            OutputConfig={
                'S3Bucket': RESULT_BUCKET,
                'S3Prefix': result_prefix
            }
        )
        job_id = response['JobId']
        logger.info(f"Textract job started successfully with ID: {job_id}, results will be saved under: s3://{RESULT_BUCKET}/{result_prefix}")

    except Exception as e:
        logger.error(f"Error processing S3 object: {e}")
        raise

def derive_main_file_key(metadata_key):
    """
    Derives the main file key from the metadata JSON key.
    Example:
        metadata/uploads/c129000e-30b1-702e-33ae-eec0ec14be40/948c83b7-426f-4e9c-821e-ba0efec45db8/report_2.jpg.json
        -> uploads/c129000e-30b1-702e-33ae-eec0ec14be40/948c83b7-426f-4e9c-821e-ba0efec45db8/report_2.jpg
    """
    expected_prefix = 'metadata/uploads/'
    expected_suffix = '.json'

    if not metadata_key.startswith(expected_prefix) or not metadata_key.endswith(expected_suffix):
        raise ValueError(f"Invalid metadata key format: {metadata_key}")

    # Strip the 'metadata/uploads/' prefix and '.json' suffix, then prepend 'uploads/'
    main_file_key = 'uploads/' + metadata_key[len(expected_prefix):-len(expected_suffix)]
    logger.info(f"Derived main_file_key: {main_file_key}")
    return main_file_key

def construct_result_key(main_file_key, suffix='_textract.json'):
    """
    Constructs the S3 key for the result files by replacing the prefix and adding a suffix.
    Example:
        uploads/user_id/unique_id/report_1.jpg -> textract-results/uploads/user_id/unique_id/report_1_textract.json
    """
    if not main_file_key.startswith('uploads/'):
        raise ValueError(f"Invalid main file key format: {main_file_key}")

    # Replace 'uploads/' with 'textract-results/uploads/' and add suffix before the file extension
    parts = main_file_key.split('/')
    filename = parts[-1]
    filename_base, _ = os.path.splitext(filename)
    new_filename = f"{filename_base}{suffix}"
    result_key = '/'.join(['textract-results/uploads'] + parts[1:-1] + [new_filename])
    logger.info(f"Constructed result_key: {result_key}")
    return result_key

def handle_textract_notification(message_body):
    """
    Handles Textract job completion notifications and saves results to S3.
    """
    job_id = message_body.get('JobId')
    status = message_body.get('Status', 'FAILED')
    metadata_key = message_body.get('MetadataKey')  # Ensure this is passed correctly

    logger.info(f"Textract Job ID: {job_id}, Status: {status}")

    if status != 'SUCCEEDED':
        logger.error(f"Textract job {job_id} failed or did not succeed. Status: {status}")
        raise ValueError(f"Textract job {job_id} failed or did not succeed. Status: {status}")

    try:
        # Derive main_file_key from metadata_key
        main_file_key = derive_main_file_key(metadata_key)
        logger.info(f"Derived main_file_key from metadata: {main_file_key}")

        # Fetch Textract results
        textract_result = get_textract_results(job_id)
        logger.info(f"Textract job {job_id} results retrieved successfully.")
    except Exception as e:
        logger.error(f"Failed to retrieve Textract results for Job ID {job_id}: {e}")
        raise

    try:
        # Construct the result key
        result_key = construct_result_key(main_file_key)
        logger.info(f"Constructed result key: s3://{RESULT_BUCKET}/{result_key}")

        # Save results to S3
        save_textract_to_s3(textract_result, RESULT_BUCKET, result_key)
        logger.info(f"Textract results saved to s3://{RESULT_BUCKET}/{result_key}")
    except Exception as e:
        logger.error(f"Failed to save Textract results to S3 for Job ID {job_id}: {e}")
        raise

def get_textract_results(job_id):
    """
    Retrieves Textract job results.
    """
    try:
        response = textract_client.get_document_analysis(JobId=job_id)
        blocks = response.get('Blocks', [])
        
        # Handle pagination if necessary
        next_token = response.get('NextToken')
        while next_token:
            paginated_response = textract_client.get_document_analysis(JobId=job_id, NextToken=next_token)
            blocks.extend(paginated_response.get('Blocks', []))
            next_token = paginated_response.get('NextToken')
        
        return blocks
    except ClientError as e:
        logger.error(f"Error fetching Textract results for Job ID {job_id}: {e}")
        raise

def save_textract_to_s3(textract_result, bucket, key):
    """
    Saves Textract results to the specified S3 bucket and key.
    """
    try:
        s3_client.put_object(
            Body=json.dumps(textract_result),
            Bucket=bucket,
            Key=key,
            ContentType='application/json'
        )
        logger.info(f"Successfully saved Textract results to s3://{bucket}/{key}")
    except ClientError as e:
        logger.error(f"Error saving Textract results to S3: {e}")
        raise