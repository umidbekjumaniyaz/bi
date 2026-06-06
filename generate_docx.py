import markdown
import subprocess
import os

with open("Report.md", "r", encoding="utf-8") as f:
    md_content = f.read()

# Convert markdown to HTML
html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code', 'nl2br'])

# Wrap in basic HTML structure with styles for textutil
html_template = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>BI Report</title>
<style>
body {{ font-family: 'Times New Roman', Times, serif; line-height: 1.6; font-size: 12pt; }}
h1, h2, h3, h4 {{ color: #2c3e50; font-family: Arial, Helvetica, sans-serif; }}
h1 {{ border-bottom: 2px solid #2c3e50; padding-bottom: 5px; }}
h2 {{ border-bottom: 1px solid #bdc3c7; padding-bottom: 3px; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
th, td {{ border: 1px solid #bdc3c7; padding: 8px; text-align: left; }}
th {{ background-color: #ecf0f1; font-weight: bold; }}
pre {{ background-color: #f8f9fa; padding: 15px; border: 1px solid #e9ecef; border-radius: 4px; font-family: Courier, monospace; font-size: 10pt; white-space: pre-wrap; }}
code {{ font-family: Courier, monospace; background-color: #f8f9fa; padding: 2px 4px; border-radius: 3px; }}
blockquote {{ border-left: 4px solid #3498db; padding-left: 15px; color: #7f8c8d; font-style: italic; }}
</style>
</head>
<body>
{html_content}
</body>
</html>
"""

with open("temp_report.html", "w", encoding="utf-8") as f:
    f.write(html_template)

print("HTML template generated. Converting to DOCX with textutil...")

result = subprocess.run(["textutil", "-convert", "docx", "temp_report.html", "-output", "ASSBI_Distinction_Report.docx"])

if result.returncode == 0:
    print("Successfully generated ASSBI_Distinction_Report.docx")
    os.remove("temp_report.html")
else:
    print("Error generating DOCX")
