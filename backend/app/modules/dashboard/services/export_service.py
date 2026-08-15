import csv
import io
import json
from typing import Any, Dict, List


class ExportService:
    def export_csv(self, reports: List[Dict[str, Any]]) -> str:
        output = io.StringIO()
        if not reports:
            return ""

        fieldnames = list(reports[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in reports:
            clean_row = {}
            for k, v in row.items():
                if hasattr(v, "isoformat"):
                    clean_row[k] = v.isoformat()
                else:
                    clean_row[k] = v
            writer.writerow(clean_row)

        return output.getvalue()

    def export_json(self, reports: List[Dict[str, Any]]) -> str:
        clean_reports = []
        for row in reports:
            clean_row = {}
            for k, v in row.items():
                if hasattr(v, "isoformat"):
                    clean_row[k] = v.isoformat()
                else:
                    clean_row[k] = v
            clean_reports.append(clean_row)

        return json.dumps(clean_reports, indent=2)


export_service = ExportService()
