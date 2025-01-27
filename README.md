

## Project Overview

| Major Component  | Function                                     | Progress                                          |
|------------|---------------------------------------------|--------------------------------------------------|
| **Frontend** | User Authentication  | MVP Local Complete 
|            | Home Screen                                 | Same as above                                  |
|            | Upload Workflow                            | Same as above                                    |
|            | Editing Workflow                           | Same as above                                     |
| **Backend** | Upload Workflow (S3, SQS, DynamoDB)          | MVP Local Complete  |
|            | Textract Workflow                          | Same as above|
|            | Data Extraction & Storage                  | Same as above|
|            | Visualization Data API                     | Same as above  |

## Current Status
Currently, the frontend and backend are hosted locally.

Next steps:
1. Project Deployment Side:
   - Deploy frontend and backend to AWS.
   - Integrate with AWS API Gateway.
2. Project Feature Side:
   - Allow users to edit all the stored data and the original report.
   - Allow users to indicate multiple indicators for the same report.
   - Use existing ui-libarary to improve the ui.
   - Follow health data regulations.
3. Personal Learning Side:
   - Learn React systmateically.
   - Review code and implement best practices.

---

## How to Run Locally:

### 1. Frontend:
```
cd frontend
npm install
npm start
```
The frontend will be hosted on localhost:3000

### 2. Backend:
```
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```
The backend will be hosted on localhost:5001

### 3. AWS

There are two parts to AWS configuration:
1.	Set up AWS services, including S3, SQS, DynamoDB, Lambda, API Gateway, Cognito, etc.
- Further details will be provided in the future.
2.	Set proper AWS credentials in the .env files within the backend and frontend folders.
- Note: You can use the .env.example file as a reference.

## User Journey:

### User Authentication
- The frontend uses AWS Cognito User Pool for authentication.
- After opening the app, the user is redirected to the AWS Cognito login page.
- After successful login, the user is redirected back to the app.
- The user can sign out from the top-right corner.

### Visualization
Trending line charts to display the user’s all indicators.

#### User Side:
- The user can hover over the data points to see the exact values: test date, result, lab name.
- Lower and upper reference ranges are displayed as horizontal lines.
- *Note*: If use specifies different lower and upper reference ranges for the same indicator, the chart will use the specified range from the latest uploaded report.

#### Backend Side:
- The data is retrieved from DynamoDB and visualized on the frontend.

### Upload

#### User Side:
1.	File Upload
   - Users can select files (only jpgs are supported now) to upload.
   - After selecting a file, the user specifies the health indicator they want to track (e.g., cholesterol, blood sugar levels).

2. Fields Editing
   - The user can edit the extracted data before final submission.

#### Backend Side:

1.	S3 Bucket 1 (File Storage)

```
Uploads file -> S3 Bucket 1 (File Storage) -> S3 Event Notification -> SQS Queue

```
   - The uploaded file is stored in S3 Bucket 1 (clinical-reports).
   - This storage action triggers Lambda Function 1 for processing.

2.	Data Extraction (Lambda Function 1)
```
SQS Queue  -> Lambda Function -> Textract Service -> S3 Bucket 2 (JSON Storage)

```
   - Lambda Function 1 extracts data from the uploaded file using AWS Textract (an OCR service).
   - The extracted data is saved as a JSON file in S3 Bucket 2 (clinical-reports-results) for reference and debugging.

3.	Key Information Extraction (Lambda Function 2)
```
S3 Bucket 2 (JSON Storage) -> Lambda Function -> DynamoDB (Extracted Data)

```
   - The JSON file stored in S3 Bucket 2 triggers Lambda Function 2, which processes the data to extract specific information needed for visualization.
   - Key fields extracted include:
      - Collected Date
      - Indicator Name
      - Result
      - Reference Range (Upper & Lower)
      - Units

4.	DynamoDB Storage
   - The extracted key information is stored in DynamoDB by lambda function 2.
   - When the user submits the data, the data is updated in DynamoDB.
