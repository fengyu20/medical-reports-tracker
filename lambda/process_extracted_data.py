import json
import boto3
import logging
import os
import re
import hashlib
from decimal import Decimal, InvalidOperation
from fuzzywuzzy import process
from botocore.exceptions import ClientError
import time
import functools
from botocore.config import Config

# Configure structured logging
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'message': record.getMessage(),
            'function': record.funcName,
            'line': record.lineno
        }
        return json.dumps(log_record)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
formatter = JsonFormatter()
handler.setFormatter(formatter)
logger.addHandler(handler)

# AWS SDK retry configuration
aws_config = Config(
    retries={
        'max_attempts': 10,
        'mode': 'standard'
    }
)

# Initialize AWS clients with retry configuration
s3_client = boto3.client('s3', region_name='eu-west-3', config=aws_config)
dynamodb = boto3.resource('dynamodb', region_name='eu-west-3', config=aws_config)
sns_client = boto3.client('sns', region_name='eu-west-3', config=aws_config)

# Environment variables
ORIGINAL_BUCKET_NAME = os.environ.get('ORIGINAL_BUCKET_NAME')  # The Original S3 Bucket name
DYNAMODB_TABLE_NAME = "clinical_reports"  
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')  # Optional: For SNS notifications

# Define processing states
PROCESSING_STARTED = 'PROCESSING_STARTED'
PROCESSING_FAILED = 'PROCESSING_FAILED'
PROCESSING_COMPLETED = 'PROCESSING_COMPLETED'

def retry_decorator(max_attempts=3, delay=2, exceptions=(Exception,)):
    """
    Retry decorator with exponential backoff.
    """
    def decorator_retry(func):
        @functools.wraps(func)
        def wrapper_retry(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempts += 1
                    logger.warning(f"Attempt {attempts} failed with error: {e}. Retrying in {delay} seconds...")
                    time.sleep(delay)
            logger.error(f"All {max_attempts} attempts failed.")
            raise
        return wrapper_retry
    return decorator_retry

def log_processing_step(user_id, key, step, message=None):
    """
    Log processing steps with user_id and key context.
    """
    if message:
        logger.info(f"User: {user_id}, Key: {key}, Step: {step}, Message: {message}")
    else:
        logger.info(f"User: {user_id}, Key: {key}, Step: {step}")

def mark_state(state, user_id, key):
    """
    Update and log the processing state.
    """
    log_processing_step(user_id, key, state)

def get_metadata_key(original_key):
    """
    Generate metadata key based on the original S3 key.
    Prepends 'metadata/' to the original key and appends '.json'.
    """
    # Prepend 'metadata/' and append '.json' to the original key
    metadata_key = f"metadata/{original_key}.json"
    
    logger.info(f"Generated metadata key: {metadata_key}")
    return metadata_key

def validate_metadata(metadata):
    """
    Validate the metadata dictionary.
    Raise ValueError if validation fails.
    """
    required_fields = ['user_id', 'upload_date', 'indicators']  # Updated required fields
    missing_fields = [field for field in required_fields if field not in metadata]
    if missing_fields:
        raise ValueError(f"Missing required metadata field(s): {', '.join(missing_fields)}")
    # 'patient_id' is now optional
    # Add more validation rules as needed
    # Add more validation rules as needed

@retry_decorator(max_attempts=5, delay=3, exceptions=(ClientError,))
def lambda_handler(event, context):
    """
    Lambda function handler to process S3 Textract result notifications and store in DynamoDB.
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    # Validate environment variables
    if not ORIGINAL_BUCKET_NAME:
        logger.error("Environment variable 'ORIGINAL_BUCKET_NAME' is not set.")
        raise EnvironmentError("Missing 'ORIGINAL_BUCKET_NAME' environment variable.")
    
    try:
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        table.load()  # This will throw an exception if the table doesn't exist
        logger.info(f"DynamoDB Table '{DYNAMODB_TABLE_NAME}' is accessible.")
    except ClientError as e:
        logger.error(f"DynamoDB Table '{DYNAMODB_TABLE_NAME}' does not exist or is inaccessible: {e}")
        raise

    for record in event.get('Records', []):
        try:
            # Parse the S3 event message
            message_body = json.loads(record.get('body', '{}'))
            s3_records = message_body.get('Records', [])
            for s3_record in s3_records:
                # Extract bucket and key from the S3 event
                bucket = s3_record['s3']['bucket']['name']
                key = s3_record['s3']['object']['key']

                # Ensure the record is from the Textract results bucket
                if bucket != 'clinical-reports-results':  # Replace with your Textract results bucket name if different
                    logger.warning(f"Ignoring message from bucket: {bucket}")
                    continue  # Skip irrelevant messages

                logger.info(f"Processing Textract result S3 object: s3://{bucket}/{key}")

                # Parse S3 key to extract user_id and original_file_key
                user_id, original_file_key = parse_s3_key(key)

                original_key_1 = get_original_file_key(key)
        
                if original_key_1 != original_file_key:
                    logger.error(f"Original file key mismatch: {original_key_1} != {original_file_key}")
                    continue

                # Log processing started
                mark_state(PROCESSING_STARTED, user_id, key)

                # Read Textract result JSON from S3
                textract_data = read_textract_json(bucket, key)

                # Generate metadata key based on original file key
                metadata_key = get_metadata_key(original_file_key)

                # Retrieve metadata from the Original S3 Bucket
                metadata_bucket = ORIGINAL_BUCKET_NAME  # Retrieve metadata from the Original Bucket

                logger.debug(f"Attempting to retrieve metadata from bucket: {metadata_bucket}, key: {metadata_key}")

                try:
                    metadata_response = s3_client.get_object(Bucket=metadata_bucket, Key=metadata_key)
                    metadata_content = metadata_response['Body'].read().decode('utf-8')
                    metadata = json.loads(metadata_content)
                    logger.info(f"Successfully retrieved metadata from {metadata_bucket}/{metadata_key}")
                except ClientError as e:
                    if e.response['Error']['Code'] == 'NoSuchKey':
                        logger.error(f"Metadata file {metadata_key} does not exist in bucket {metadata_bucket}.")
                        mark_state(PROCESSING_FAILED, user_id, key)
                        log_processing_step(user_id, key, PROCESSING_FAILED, "Metadata file missing.")
                        # Optional: Notify via SNS
                        if SNS_TOPIC_ARN:
                            notify_missing_metadata(metadata_key, metadata_bucket)
                        continue  # Skip further processing
                    else:
                        logger.error(f"AWS Client Error while fetching metadata: {e}")
                        raise

                # Validate metadata
                try:
                    validate_metadata(metadata)
                except ValueError as ve:
                    logger.error(f"Metadata validation failed: {ve}")
                    mark_state(PROCESSING_FAILED, user_id, key)
                    log_processing_step(user_id, key, PROCESSING_FAILED, f"Metadata validation failed: {ve}")
                    continue  # Skip further processing

                # Extract the 'indicators' from metadata
                user_indicator = metadata.get('indicators')

                # Ensure that 'user_indicator' is present
                if not user_indicator:
                    logger.error("No 'indicators' field found in metadata.")
                    mark_state(PROCESSING_FAILED, user_id, key)
                    log_processing_step(user_id, key, PROCESSING_FAILED, "Missing 'indicators' in metadata.")
                    continue  # Skip further processing

                # Extract relevant data using custom extraction logic with dynamic indicator
                extracted_data = extract_text_with_queries(textract_data, user_indicator)

                if "Error" in extracted_data:
                    logger.error(extracted_data["Error"])
                    mark_state(PROCESSING_FAILED, user_id, key)
                    log_processing_step(user_id, key, PROCESSING_FAILED, extracted_data["Error"])
                    continue  # Skip storing data if extraction failed

                # Store results in DynamoDB using custom store_extracted_data
                store_extracted_data(
                    extracted_data,
                    original_file_key,
                    user_id,
                    metadata.get('upload_date', 0),
                    dynamodb,
                    metadata
                )

                # Mark processing completed
                mark_state(PROCESSING_COMPLETED, user_id, key)

        except KeyError as e:
            logger.error(f"Missing expected key: {e}")
        except ClientError as e:
            logger.error(f"AWS Client Error: {e}")
        except Exception as e:
            logger.error(f"Error processing record: {e}")

    return {"status": "success", "message": "All messages processed successfully"}

def read_textract_json(bucket, key):
    """
    Read JSON content from S3.
    """
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read()
        textract_data = json.loads(content)
        logger.info(f"Successfully read Textract JSON from s3://{bucket}/{key}")
        return textract_data
    except ClientError as e:
        logger.error(f"Error reading JSON from S3: {e}")
        raise

def parse_s3_key(s3_key):
    """
    Parse S3 key to extract user ID and original file key.
    Assumes the key structure: textract-results/uploads/<user_id>/<unique_id>/report_<number>_textract.json/...
    """
    try:
        parts = s3_key.split('/')
        if len(parts) < 5:
            raise ValueError("Invalid S3 key structure.")

        user_id = parts[2]
        unique_id = parts[3]
        textract_filename = parts[4]  # e.g., report_3_textract.json

        # Extract the report number using regex
        match = re.match(r'report_(\d+)_textract\.json', textract_filename)
        if not match:
            raise ValueError("Textract filename does not match expected pattern.")

        report_number = match.group(1)
        original_file_key = f"uploads/{user_id}/{unique_id}/report_{report_number}.jpg"

        logger.info(f"Parsed S3 key. User ID: {user_id}, Original File Key: {original_file_key}")
        return user_id, original_file_key
    except Exception as e:
        logger.error(f"Error parsing S3 key '{s3_key}': {e}")
        raise

def safe_decimal_conversion(value, default=Decimal(0)):
    """
    Safely convert a string to Decimal.
    If conversion fails, return the default value.
    
    Parameters:
    - value (str): The string to convert.
    - default (Decimal): The default value to return if conversion fails.
    
    Returns:
    - Decimal: The converted Decimal value or the default.
    """
    try:
        # Remove any non-numeric characters except for the decimal point and negative sign
        cleaned_value = re.sub(r'[^\d\.\-]', '', value)
        return Decimal(cleaned_value)
    except (InvalidOperation, ValueError) as e:
        logger.warning(f"Failed to convert '{value}' to Decimal. Using default value {default}. Error: {e}")
        return default
    
def extract_text_with_queries(textract_data, user_indicator):
    """
    Extract text and fields from Textract data using custom extraction logic.

    Parameters:
    - textract_data (dict): The JSON response from AWS Textract.
    - user_indicator (str): The indicator to search for within the Textract data.

    Returns:
    - dict: Extracted data with the specified indicator.
    """
    try:
        # Extract LINE blocks from Textract response
        blocks = textract_data.get('Blocks', [])
        line_blocks = [block for block in blocks if block['BlockType'] == 'LINE']
        logger.info(f"Extracted {len(line_blocks)} LINE blocks from Textract data.")

        # Extract text from LINE blocks
        lines = [line['Text'].strip() for line in line_blocks if 'Text' in line]

        # Define regex patterns for static fields
        queries = {
            "Laboratory Name": r"(?i)laboratory name[:\-]?\s*(.*)",
            "Patient Name": r"(?i)patient name[:\-]?\s*(.*)",
            "Collected On Date": r"(?i)collected on[:\-]?\s*(.*)"
        }

        # Initialize extracted data dictionary
        extracted_data = {}

        # Extract static fields using regex patterns
        for line in lines:
            for query, pattern in queries.items():
                if query not in extracted_data:  # Avoid overwriting once found
                    match = re.search(pattern, line)
                    if match:
                        extracted_data[query] = match.group(1).strip()
                        logger.info(f"Extracted {query}: {extracted_data[query]}")

        # Handle dynamic indicators
        indicators, results, ranges, units = [], [], [], []

        for i, line in enumerate(lines):
            if re.match(r"^[a-zA-Z\s]+$", line):
                next_line = lines[i + 1] if i + 1 < len(lines) else ""
                if re.match(r"^\d+(\.\d+)?$", next_line):
                    indicators.append(line)

            if re.match(r"^\d+(\.\d+)?$", line):
                results.append(line)
            elif re.match(r"^\d+\s*[-–]\s*\d+$", line):
                ranges.append(line)
            elif re.match(r"[a-zA-Z]+\/[a-zA-Z]+$", line):
                units.append(line)

        # Use the dynamic user_indicator for fuzzy matching
        matched_indicator = process.extractOne(user_indicator, indicators, scorer=process.fuzz.partial_ratio)
        if matched_indicator and matched_indicator[1] >= 80:
            matched_indicator = matched_indicator[0]
            logger.info(f"Matched indicator: {matched_indicator} with confidence {matched_indicator[1]}")
        else:
            matched_indicator = None
            logger.warning(f"Indicator '{user_indicator}' not found or low confidence match.")

        if matched_indicator:
            idx = indicators.index(matched_indicator)
            extracted_data[matched_indicator] = {
                "Result": results[idx] if idx < len(results) else "0",  # Default to "0" if missing
                "Range": ranges[idx] if idx < len(ranges) else "0",    # Default to "0" if missing
                "Units": units[idx] if idx < len(units) else "units"    # Default to "N/A" if missing
            }
        else:
            extracted_data["Error"] = f"Indicator '{user_indicator}' not found."

        logger.info(f"Extracted data: {extracted_data}")
        return extracted_data

    except Exception as e:
        logger.error(f"Error during Textract query extraction: {e}")
        raise

def generate_patient_id(patient_name, collected_date, user_id):
    """
    Generate a unique patient ID.
    If patient_name is not available, leave it blank.
    """
    patient_name = patient_name or ""
    raw_id = f"{user_id}_{patient_name}_{collected_date}"
    patient_id = hashlib.sha256(raw_id.encode()).hexdigest()[:10]
    logger.info(f"Generated Patient ID: {patient_id}")
    return patient_id

def store_extracted_data(data, original_file_key, user_id, timestamp, dynamodb_resource, metadata):
    """
    Store extracted data in DynamoDB.
    """
    try:
        logger.info(f"Using DynamoDB Table: {DYNAMODB_TABLE_NAME} in region: {dynamodb_resource.meta.client.meta.region_name}")
        table = dynamodb_resource.Table(DYNAMODB_TABLE_NAME)

        patient_name = data.get("Patient Name", "") 
        upload_date = metadata.get('upload_date')
        laboratory_name = data.get("Laboratory Name")
        collected_date = data.get("Collected On Date", "2025-01-21")
        
        # Generate patient_id if not present in metadata
        patient_id = metadata.get('patient_id')
        if not patient_id:
            patient_id = generate_patient_id(patient_name, upload_date, user_id)
        
        for indicator, values in data.items():
            if indicator not in ["Laboratory Name", "Patient Name", "Collected On Date", "Error"]:
                # Safely handle Range conversion
                range_str = values.get("Range", "0")
                lower_range = safe_decimal_conversion(range_str.split("-")[0] if "-" in range_str else range_str)
                upper_range = safe_decimal_conversion(range_str.split("-")[1]) if "-" in range_str else Decimal(0)
                # collected_date = values.get("Collected On Date", "2025-01-21")
                # Safely handle Result conversion
                result_str = values.get("Result", "0")
                result = safe_decimal_conversion(result_str)

                units = values.get("Units", "N/A")
                
                sort_key = f"{patient_id}#{upload_date}#{indicator}"

                item = {
                    "UserId": user_id,
                    "PatientId#TestDateTime#Indicator": sort_key,
                    "PatientId": patient_id,
                    "PatientName": patient_name,
                    "CollectedDate": collected_date,
                    "UploadDate": upload_date,
                    "LaboratoryName": laboratory_name,
                    "Indicator": indicator,
                    "Result": result,
                    "Units": units,
                    "LowerRange": lower_range,
                    "UpperRange": upper_range,
                    "S3FileKey": original_file_key,
                }

                logger.info(f"Attempting to store item in DynamoDB: {item}")
                table.put_item(Item=item)
                logger.info(f"Stored data for Indicator: {indicator} in DynamoDB.")

        logger.info("All extracted data successfully stored in DynamoDB.")

    except ClientError as e:
        logger.error(f"AWS Client Error while storing data: {e}")
        raise
    except Exception as e:
        logger.error(f"Error storing data in DynamoDB: {e}")
        raise

def notify_missing_metadata(metadata_key, metadata_bucket):
    """
    Send an SNS notification about the missing metadata file.
    """
    try:
        message = f"Metadata file {metadata_key} does not exist in bucket {metadata_bucket}."
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=message,
            Subject="Missing Metadata File Alert"
        )
        logger.info(f"Sent SNS notification about missing metadata file: {metadata_key}")
    except ClientError as e:
        logger.error(f"Error sending SNS notification: {e}")

def get_original_file_key(textract_key):
    """
    Convert Textract result S3 key to the original file S3 key.
    Handles additional path segments after '_textract.json'.
    """
    try:
        # Replace the prefix
        original_key = textract_key.replace('textract-results/uploads/', 'uploads/')
        
        # Find the position of '_textract.json' and truncate any additional segments
        split_token = '_textract.json'
        split_index = original_key.find(split_token)
        if split_index == -1:
            raise ValueError("Textract key does not contain '_textract.json'.")

        base_key = original_key[:split_index]
        original_key = f"{base_key}.jpg"
        
        logger.info(f"Converted Textract Key '{textract_key}' to Original File Key '{original_key}'")
        return original_key
    except Exception as e:
        logger.error(f"Error converting Textract key to original file key: {e}")
        raise