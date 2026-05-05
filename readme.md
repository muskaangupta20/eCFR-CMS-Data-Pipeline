# eCFR CMS Data Pipeline – Title 42 Part 482

## Overview
This project implements a serverless data pipeline using AWS Lambda and Amazon S3 to extract, transform, and store regulatory data from the eCFR API.

## Architecture
eCFR API → AWS Lambda (Python) → Amazon S3

## Pipeline Steps

### 1. Extract
- Source: eCFR API  
- Endpoint:  
https://www.ecfr.gov/api/versioner/v1/full/2026-04-30/title-42.xml?part=482  
- Data format: XML

### 2. Transform
- Parsed XML using Python ElementTree
- Extracted:
  - Subparts (A–E)
  - Sections (e.g., 482.1)
  - Paragraph-level requirements
- Converted into structured JSON format

### 3. Load
- Stored JSON files in Amazon S3
- File structure:

muskaan-mapper-output/cms-cop/title-42/part-482/subpart-{A|B|C|D|E}/

Example:
s3://amazon-output-bucket-muskaan/muskaan-mapper-output/cms-cop/title-42/part-482/subpart-A/482-1.json

## Deployment

Deployed using AWS CLI:

```bash
zip function.zip lambda_function.py
aws lambda update-function-code --function-name ecfr-transform --zip-file fileb://function.zip