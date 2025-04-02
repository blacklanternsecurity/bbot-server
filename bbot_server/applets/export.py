from fastapi.responses import StreamingResponse

from bbot_server.utils.export import stream_csv
from bbot_server.applets._base import BaseApplet, api_endpoint


class ExportApplet(BaseApplet):
    name = "Export"
    description = "Export assets to CSV, JSON, and more"

    @api_endpoint("/csv", methods=["GET"], summary="Export assets to CSV")
    async def export_csv(self):
        cursor = self.collection.find()

        fieldnames = self.root.assets.all_fieldnames

        async def stream_csv_rows():
            async for row in stream_csv(fieldnames, cursor):
                yield row

        # stream CSV file to client
        response = StreamingResponse(
            stream_csv_rows(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="assets.csv"'},
        )

        return response
