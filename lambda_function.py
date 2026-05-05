import json
import boto3
import xml.etree.ElementTree as ET
import re
from datetime import datetime
import urllib.request

s3 = boto3.client('s3')

BUCKET_NAME = "amazon-output-bucket-muskaan"   # change if needed


def lambda_handler(event, context):

    url = "https://www.ecfr.gov/api/versioner/v1/full/2026-04-30/title-42.xml?part=482"

    with urllib.request.urlopen(url) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)

    uploaded = []

    for subpart in root.findall(".//DIV6[@TYPE='SUBPART']"):
        subpart_code = subpart.get("N")

        subpart_head = subpart.find("HEAD")
        subpart_text = "".join(subpart_head.itertext()).strip() if subpart_head is not None else ""
        subpart_name = subpart_text.split("—", 1)[-1].strip()

        for section in subpart.findall(".//DIV8[@TYPE='SECTION']"):
            section_code = section.get("N")

            head = section.find("HEAD")
            head_text = "".join(head.itertext()).strip() if head is not None else ""

            title = re.sub(r"^§\s*\d+\.?\d*\s*", "", head_text).strip()

            content = []

            for p in section.findall("P"):
                text = "".join(p.itertext()).strip()
                if not text:
                    continue

                match = re.match(r"^\(([a-zA-Z0-9]+)\)", text)
                code = f"{section_code}({match.group(1)})" if match else section_code

                content.append({
                    "standard_code": code,
                    "requirement": text,
                    "sub_requirements": []
                })

            data = {
                "regulation_id": f"42_CFR_{section_code.replace('.', '_')}",
                "regulation_source": "cms_cop",
                "code": section_code,
                "title": title,
                "description": content[0]["requirement"] if content else "",
                "subpart": subpart_code,
                "subpart_name": subpart_name,
                "content": content,
                "metadata": {
                    "facility_type": "Hospital",
                    "part_label": "Part 482",
                    "title_number": "42",
                    "version": "2026-04-30",
                    "effective_date": "2026-04-30",
                    "extraction_date": datetime.utcnow().isoformat()
                }
            }

            file_name = section_code.replace(".", "-") + ".json"

            s3_key = f"muskaan-mapper-output/cms-cop/title-42/part-482/subpart-{subpart_code}/{file_name}"

            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=s3_key,
                Body=json.dumps(data),
                ContentType='application/json'
            )

            uploaded.append(s3_key)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Success",
            "files_uploaded": len(uploaded)
        })
    }