from flask import Blueprint, request, jsonify, session
from app.auth.decorators import login_required
import boto3
from botocore.config import Config
import json
from datetime import datetime
import time
import uuid
import os
import logging
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key


logger = logging.getLogger(__name__)
clinical_data_bp = Blueprint('clinical_data', __name__)

def get_s3_client():
    """Create and configure S3 client with error checking"""
    required_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION', 'AWS_S3_BUCKET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    region = os.getenv('AWS_REGION')
    logger.info(f"Initializing S3 client with region: {region}")
    
    # Create a configuration object
    config = Config(
        region_name=region,
        signature_version='s3v4',
        s3={'addressing_style': 'virtual'}
    )
    
    return boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=region,
        config=config
    )

def generate_presigned_url(file_key, content_type, metadata):
    """Generate presigned URL with metadata"""
    try:
        s3_client = get_s3_client()
        bucket_name = os.getenv('AWS_S3_BUCKET')
        
        if not bucket_name:
            raise ValueError("AWS_S3_BUCKET environment variable is not set")
            
        url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket_name,
                'Key': file_key,
                'ContentType': content_type
            },
            ExpiresIn=3600
        )
        return url
        
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        raise

def store_file_metadata(file_key, metadata):
    """Store initial file metadata in S3"""
    try:
        logger.info(f"Storing metadata for file_key: {file_key}")
        s3_client = get_s3_client()
        bucket_name = os.getenv('AWS_S3_BUCKET')
        
        if not bucket_name:
            raise ValueError("AWS_S3_BUCKET environment variable is not set")
        
        metadata_content = {
            'user_id': metadata['user_id'],
            'indicators': metadata['indicators'],
            'upload_date': metadata['upload_date'],
        }
        
        metadata_key = f"metadata/{file_key}.json"
        logger.debug(f"Metadata key: {metadata_key}")
        logger.debug(f"Metadata content: {json.dumps(metadata_content)}")
        
        response = s3_client.put_object(
            Bucket=bucket_name,
            Key=metadata_key,
            Body=json.dumps(metadata_content),
            ContentType='application/json'
        )
        
        logger.info(f"Stored metadata for file {file_key} in S3 at {metadata_key}")
        logger.debug(f"S3 put_object response: {response}")
        
    except ClientError as e:
        logger.error(f"AWS ClientError: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error storing metadata: {str(e)}")
        raise

@clinical_data_bp.route('/get-upload-url', methods=['POST', 'OPTIONS'])
@login_required
def get_upload_url():
    if request.method == 'OPTIONS':
        # CORS preflight request; flask-cors handles this
        return jsonify({}), 200

    try:
        data = request.get_json()
        if not data or 'filename' not in data or 'contentType' not in data or 'indicators' not in data:
            logger.error("Missing required fields in request")
            return jsonify({'error': 'Missing required fields (filename, contentType, or indicators)'}), 400

        filename = data['filename']
        content_type = data['contentType']
        indicators = data['indicators']  # List of selected indicators
        user_id = session['user']['user_id']

        # Generate metadata
        metadata = {
            'indicators': ','.join(indicators),  # Convert list to string
            'upload_date': datetime.utcnow().isoformat(),
            'user_id': user_id
        }

        # Generate a unique file key
        file_key = f"uploads/{user_id}/{uuid.uuid4()}/{filename}"

        try:
            upload_url = generate_presigned_url(file_key, content_type, metadata)

            store_file_metadata(file_key, metadata)

            return jsonify({
                'uploadUrl': upload_url,
                'fileKey': file_key,
                'metadata': metadata
            })

        except ValueError as e:
            logger.error(f"Configuration error: {str(e)}")
            return jsonify({'error': 'Server configuration error'}), 500

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({'error': 'Invalid request'}), 400

@clinical_data_bp.route('/confirm-upload', methods=['POST'])
@login_required
def confirm_upload():
    try:
        data = request.get_json()
        if not data or 'fileKey' not in data:
            return jsonify({'error': 'Missing fileKey'}), 400

        user_id = session['user']['user_id']
        file_key = data['fileKey']
        filename = data['filename']
        content_type = data.get('contentType', 'application/octet-stream')

        # Here you would typically update your database with the upload information
        logger.info(f"Upload confirmed for user {user_id}, file {filename}")

        return jsonify({
            'message': 'Upload confirmed successfully',
            'fileKey': file_key
        })

    except Exception as e:
        logger.error(f"Error confirming upload: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    

@clinical_data_bp.route("/trending/all", methods=["GET"])
@login_required
def get_all_trending_data():
    logger.info("GET /clinical-data/trending/all called")
    if request.method == 'OPTIONS':
        # Handle CORS preflight request
        response = jsonify({})
        response.status_code = 200
        response.headers.add("Access-Control-Allow-Origin", "http://localhost:3030")
        response.headers.add("Access-Control-Allow-Methods", "GET, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type, Authorization")
        return response

    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('clinical_reports')
        
        user_id = session['user']['user_id']    

        response = table.query(
            KeyConditionExpression=Key("UserId").eq(user_id)
        )
        # Return items in a JSON structure
        return jsonify({"items": response.get("Items", [])})
    except Exception as e:
        logger.error(f"Error getting all trending data: {str(e)}")
        return jsonify({"error": str(e)}), 500

ALLOWED_UPDATE_FIELDS = ['PatientName', 'CollectedDate', 'Result', 'Units', 'LowerRange', 'UpperRange']

@clinical_data_bp.route('/<string:data_id>', methods=['GET'])
@login_required
def get_clinical_data(data_id):
    """
    Retrieve a specific clinical data entry by its ID.
    """
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('clinical_reports')

        user_id = session['user']['user_id']

        response = table.get_item(
            Key={
                'UserId': user_id,
                'PatientId#TestDateTime#Indicator': data_id
            }
        )

        if 'Item' not in response:
            logger.warning(f"Clinical data with ID {data_id} not found for user {user_id}.")
            return jsonify({'error': 'Data not found'}), 404

        return jsonify(response['Item']), 200

    except ClientError as e:
        logger.error(f"AWS ClientError while fetching clinical data: {e}")
        return jsonify({'error': 'Internal server error'}), 500
    except Exception as e:
        logger.error(f"Error fetching clinical data: {e}")
        return jsonify({'error': 'Internal server error'}), 500
    

@clinical_data_bp.route('/<string:data_id>', methods=['PUT'])
@login_required
def update_clinical_data(data_id):
    """
    Update specific fields of a clinical data entry by its ID.
    """
    try:
        data = request.get_json()
        if not data:
            logger.error("No data provided in the request body.")
            return jsonify({'error': 'No data provided'}), 400

        # Filter data to only include allowed fields with correct casing
        update_fields = {key: value for key, value in data.items() if key in ALLOWED_UPDATE_FIELDS}

        if not update_fields:
            logger.error("No valid fields provided for update.")
            return jsonify({'error': 'No valid fields provided for update'}), 400

        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('clinical_reports')

        user_id = session['user']['user_id']

        # Initialize dictionaries for expression attribute names and values
        expression_attribute_names = {}
        expression_attribute_values = {}

        # Updated reserved keywords list (removed 'result' if it was previously included)
        dynamodb_reserved_keywords = [
            'size', 'date', 'name', 'value', 'key', 'type', 'order', 'group',
            # Add 'Result' if it's confirmed to be reserved
            'Result'
        ]

        update_expression_parts = []
        for field, value in update_fields.items():
            # Check if the field is a reserved keyword
            if field in dynamodb_reserved_keywords:
                alias = f"#{field}"
                expression_attribute_names[alias] = field
                update_expression_parts.append(f"{alias} = :{field}")
            else:
                update_expression_parts.append(f"{field} = :{field}")

            # Add only one entry to ExpressionAttributeValues
            expression_attribute_values[f":{field}"] = value

        update_expression = "SET " + ", ".join(update_expression_parts)

        # Debugging logs to verify expressions
        logger.debug(f"UpdateExpression: {update_expression}")
        logger.debug(f"ExpressionAttributeNames: {expression_attribute_names}")
        logger.debug(f"ExpressionAttributeValues: {expression_attribute_values}")

        # Perform the update operation
        response = table.update_item(
            Key={
                'UserId': user_id,
                'PatientId#TestDateTime#Indicator': data_id
            },
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names or None,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues="UPDATED_NEW"
        )

        logger.info(f"Updated clinical data {data_id} for user {user_id}: {response.get('Attributes')}")

        return jsonify({
            'message': 'Data updated successfully',
            'updatedFields': response.get('Attributes')
        }), 200

    except ClientError as e:
        logger.error(f"AWS ClientError while updating clinical data: {e}")
        return jsonify({'error': 'Internal server error'}), 500
    except Exception as e:
        logger.error(f"Error updating clinical data: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@clinical_data_bp.route('/latest-upload', methods=['GET'])
@login_required
def get_latest_upload():
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('clinical_reports')
        
        user_id = session['user']['user_id']
        
        response = table.query(
            KeyConditionExpression=Key('UserId').eq(user_id),
            ScanIndexForward=False,  # Descending order
            Limit=10  # Fetch top 10 to increase the chance of getting the latest
        )
        
        items = response.get('Items', [])
        latest_entry = None
        latest_datetime = None
        
        for item in items:
            sort_key = item.get('PatientId#TestDateTime#Indicator', '')
            
            if sort_key.count('#') != 2:
                logger.error(f"Malformed sort_key '{sort_key}': Expected 3 parts separated by '#'")
                continue
            try:
                _, test_datetime_str, _ = sort_key.split('#')
                test_datetime = datetime.fromisoformat(test_datetime_str)
                
                if not latest_datetime or test_datetime > latest_datetime:
                    latest_datetime = test_datetime
                    latest_entry = item
            except ValueError:
                logger.error(f"Error parsing datetime from sort_key '{sort_key}': {e}")
                continue  # Skip items with improperly formatted sort keys
        
        if latest_entry:
            return jsonify(latest_entry), 200
        else:
            return jsonify({'error': 'No valid data found'}), 404
    
    except Exception as e:
        logger.error(f"Error fetching latest upload: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500