import io
import csv
from fastapi.responses import StreamingResponse

from bbot_server.scans import Scan
from bbot_server.applets._base import BaseApplet, api_endpoint


class Export(BaseApplet):
    description = "Export assets to CSV, JSON, and more"

    @api_endpoint("/csv", methods=["GET"], summary="Export assets to CSV")
    async def export_csv(self) -> list[Scan]:
        cursor = self.collection.find()

        async def stream_csv():
            # Create a CSV writer object
            output = io.StringIO()
            writer = csv.writer(output)

            # Write the header
            writer.writerow(["host"])  # Add more headers if needed
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

            # Write each asset as a row in the CSV
            async for asset in cursor:
                writer.writerow([asset["host"]])  # Add more fields if needed
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)

        # stream CSV file to client
        response = StreamingResponse(
            stream_csv(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="assets.csv"'}
        )

        return response
