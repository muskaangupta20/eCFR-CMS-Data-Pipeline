import json
import boto3
import xml.etree.ElementTree as ET
import re
from datetime import datetime
import urllib.request

s3 = boto3.client("s3")

BUCKET_NAME = "amazon-output-bucket-muskaan"


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def is_roman_marker(value):
    roman_values = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}
    return value.lower() in roman_values


def split_requirement_and_inline_child(rest_text):
    inline_match = re.search(r"\s+(\(\d+\))\s+", rest_text)

    if inline_match:
        requirement = rest_text[:inline_match.start()].strip().rstrip(".")
        inline_marker = inline_match.group(1)
        inline_text = rest_text[inline_match.end():].strip()
        return requirement, inline_marker, inline_text

    if "." in rest_text:
        first_sentence, remaining = rest_text.split(".", 1)
        requirement = first_sentence.strip()
        remaining = remaining.strip()

        if remaining:
            return requirement, "(1)", remaining

    return rest_text.strip().rstrip("."), None, None


def build_content(section, section_code):
    content = []

    current_top = None
    current_top_code = None
    current_second = None
    current_second_code = None

    for p in section.findall("P"):
        text = clean_text("".join(p.itertext()))
        if not text:
            continue

        marker_match = re.match(r"^\s*\(([A-Za-z0-9]+)\)\s*(.*)$", text)

        if not marker_match:
            continue

        marker_value = marker_match.group(1)
        marker = f"({marker_value})"
        rest_text = marker_match.group(2).strip()

        if marker_value.isalpha() and marker_value.islower() and not (
            is_roman_marker(marker_value) and current_second is not None
        ):
            full_code = section_code + marker
            requirement, inline_marker, inline_text = split_requirement_and_inline_child(rest_text)

            top_node = {
                "standard_code": full_code,
                "requirement": requirement,
                "sub_requirements": []
            }

            content.append(top_node)

            current_top = top_node
            current_top_code = full_code
            current_second = None
            current_second_code = None

            # handle inline numbered item
            if inline_marker and inline_text:
                second_code = full_code + inline_marker

                second_node = {
                    "code": second_code,
                    "text": inline_text,
                    "sub_requirements": []
                }

                top_node["sub_requirements"].append(second_node)

                current_second = second_node
                current_second_code = second_code

        elif marker_value.isdigit():
            if current_top is None:
                full_code = section_code + marker

                fallback_node = {
                    "standard_code": full_code,
                    "requirement": rest_text,
                    "sub_requirements": []
                }

                content.append(fallback_node)

                current_top = fallback_node
                current_top_code = full_code
                current_second = None
                current_second_code = None
            else:
                full_code = current_top_code + marker

                second_node = {
                    "code": full_code,
                    "text": rest_text,
                    "sub_requirements": []
                }

                current_top["sub_requirements"].append(second_node)

                current_second = second_node
                current_second_code = full_code

        elif is_roman_marker(marker_value):
            if current_second is not None:
                full_code = current_second_code + marker

                third_node = {
                    "code": full_code,
                    "text": rest_text
                }

                current_second["sub_requirements"].append(third_node)

            elif current_top is not None:
                full_code = current_top_code + marker

                third_node = {
                    "code": full_code,
                    "text": rest_text
                }

                current_top["sub_requirements"].append(third_node)

            else:
                full_code = section_code + marker

                content.append({
                    "standard_code": full_code,
                    "requirement": rest_text,
                    "sub_requirements": []
                })

        elif marker_value.isalpha() and marker_value.isupper():
            if current_second is not None:
                full_code = current_second_code + marker

                upper_node = {
                    "code": full_code,
                    "text": rest_text
                }

                current_second["sub_requirements"].append(upper_node)

    return content


def lambda_handler(event, context):
    url = "https://www.ecfr.gov/api/versioner/v1/full/2026-04-30/title-42.xml?part=482"

    with urllib.request.urlopen(url) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)

    uploaded = []

    for subpart in root.findall(".//DIV6[@TYPE='SUBPART']"):
        subpart_code = subpart.get("N")

        subpart_head = subpart.find("HEAD")
        subpart_text = clean_text("".join(subpart_head.itertext())) if subpart_head is not None else ""

        if "—" in subpart_text:
            subpart_name = subpart_text.split("—", 1)[1].strip()
        else:
            subpart_name = subpart_text

        for section in subpart.findall(".//DIV8[@TYPE='SECTION']"):
            section_code = section.get("N")

            head = section.find("HEAD")
            head_text = clean_text("".join(head.itertext())) if head is not None else ""

            title = re.sub(r"^§\s*\d+\.?\d*\s*", "", head_text).strip()

            content = build_content(section, section_code)

            data = {
                "regulation_id": f"42_CFR_{section_code.replace('.', '_')}",
                "regulation_source": "cms_cop",
                "code": section_code,
                "title": title,
                "description": f"This section covers {title}",
                "subpart": subpart_code,
                "subpart_name": subpart_name,
                "content": content,
                "metadata": {
                    "facility_type": "Hospital",
                    "part_label": "Part 482",
                    "title_number": "42",
                    "version": "2026-04-30",
                    "effective_date": "2026-04-30",
                    "federal_register_citation": "Not specified",
                    "extraction_date": datetime.utcnow().isoformat(),
                    "source_url": f"https://www.ecfr.gov/current/title-42/section-{section_code}"
                }
            }

            file_name = section_code.replace(".", "-") + ".json"

            s3_key = (
                f"niaho-mapper-output/cms-cop/title-42/part-482/"
                f"subpart-{subpart_code}/{file_name}"
            )

            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=s3_key,
                Body=json.dumps(data, indent=2, ensure_ascii=False),
                ContentType="application/json"
            )

            uploaded.append(s3_key)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Success",
            "files_uploaded": len(uploaded)
        })
    }
if __name__ == "__main__":
    print("Running pipeline locally")
    result = lambda_handler({}, None)
    print(json.dumps(result, indent=2))
    print("Pipeline completed")