import React from "react";

export interface PlacesData {
  place_id?: string;
  name?: string;
  website?: string;
  phone?: string;
  address?: string;
  email?: string;
}

export interface BoothData {
  company_name: string;
  booth: string | null;
  size: string | null;
  places_data?: PlacesData | null;
}

interface ApiResponse {
  total_booths: number;
  booths: BoothData[];
  filename?: string;
  extraction_method?: string;
  processing_time?: number;
  enrichment_time?: number;
  places_api_calls?: number;
}

interface ResultsProps {
  results: ApiResponse[];
}

const Results: React.FC<ResultsProps> = ({ results }) => {
  if (!results || results.length === 0) {
    return (
      <div className="mt-6 p-4 border rounded-lg bg-gray-50">
        <h2 className="text-lg font-semibold mb-2">Processing Results</h2>
        <p className="text-gray-500">No results to display yet.</p>
      </div>
    );
  }

  // Calculate enrichment stats
  const calculateStats = (booths: BoothData[]) => {
    const total = booths.length;
    const enriched = booths.filter((booth) => booth.places_data).length;
    const withEmail = booths.filter((booth) => booth.places_data?.email).length;
    const withPhone = booths.filter((booth) => booth.places_data?.phone).length;
    const withWebsite = booths.filter(
      (booth) => booth.places_data?.website
    ).length;

    return { total, enriched, withEmail, withPhone, withWebsite };
  };

  return (
    <div className="mt-6">
      <h2 className="text-xl font-bold mb-4">Extraction Results</h2>
      <p className="text-sm text-gray-600 mb-4">
        Processed {results.length} file{results.length !== 1 ? "s" : ""}
      </p>

      {results.map((result, index) => {
        const stats = calculateStats(result.booths);

        return (
          <div key={index} className="mb-8 border rounded-lg p-4 bg-white">
            <div className="mb-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                📄 {result.filename || `File ${index + 1}`}
              </h3>
              <div className="flex flex-wrap gap-4 text-sm mb-4">
                <div className="bg-blue-100 px-3 py-1 rounded">
                  <span className="font-medium">Total Booths: </span>
                  <span className="font-bold">{result.total_booths || 0}</span>
                </div>
                <div className="bg-green-100 px-3 py-1 rounded">
                  <span className="font-medium">Enriched: </span>
                  <span className="font-bold">{stats.enriched}</span>
                  <span className="text-gray-600 ml-1">
                    (
                    {stats.total > 0
                      ? Math.round((stats.enriched / stats.total) * 100)
                      : 0}
                    %)
                  </span>
                </div>
                <div className="bg-purple-100 px-3 py-1 rounded">
                  <span className="font-medium">📧 Emails: </span>
                  <span className="font-bold">{stats.withEmail}</span>
                </div>
                <div className="bg-orange-100 px-3 py-1 rounded">
                  <span className="font-medium">📞 Phones: </span>
                  <span className="font-bold">{stats.withPhone}</span>
                </div>
                <div className="bg-cyan-100 px-3 py-1 rounded">
                  <span className="font-medium">🌐 Websites: </span>
                  <span className="font-bold">{stats.withWebsite}</span>
                </div>
              </div>

              {/* Processing Time Stats */}
              <div className="flex flex-wrap gap-4 text-sm">
                {result.processing_time && (
                  <div className="bg-gray-100 px-3 py-1 rounded">
                    <span className="font-medium">Processing: </span>
                    <span>{result.processing_time}s</span>
                  </div>
                )}
                {result.enrichment_time && (
                  <div className="bg-gray-100 px-3 py-1 rounded">
                    <span className="font-medium">Enrichment: </span>
                    <span>{result.enrichment_time}s</span>
                  </div>
                )}
                {result.places_api_calls && (
                  <div className="bg-gray-100 px-3 py-1 rounded">
                    <span className="font-medium">API Calls: </span>
                    <span>{result.places_api_calls}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Booths Table */}
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse border border-gray-200">
                <thead>
                  <tr className="bg-gray-100">
                    <th className="border border-gray-300 px-4 py-2 text-left">
                      Company
                    </th>
                    <th className="border border-gray-300 px-4 py-2 text-left">
                      Booth
                    </th>
                    <th className="border border-gray-300 px-4 py-2 text-left">
                      Size
                    </th>
                    <th className="border border-gray-300 px-4 py-2 text-left">
                      📧 Email
                    </th>
                    <th className="border border-gray-300 px-4 py-2 text-left">
                      📞 Phone
                    </th>
                    <th className="border border-gray-300 px-4 py-2 text-left">
                      🌐 Website
                    </th>
                    <th className="border border-gray-300 px-4 py-2 text-left">
                      📍 Address
                    </th>
                    <th className="border border-gray-300 px-4 py-2 text-left">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {result.booths.map((booth, boothIndex) => {
                    const placesData = booth.places_data;
                    const hasData = Boolean(placesData);
                    const dataCount = placesData
                      ? [
                          placesData.email,
                          placesData.phone,
                          placesData.website,
                          placesData.address,
                        ].filter(Boolean).length
                      : 0;

                    return (
                      <tr
                        key={boothIndex}
                        className={
                          boothIndex % 2 === 0 ? "bg-white" : "bg-gray-50"
                        }
                      >
                        <td className="border border-gray-300 px-4 py-2 font-medium">
                          {booth.company_name}
                        </td>
                        <td className="border border-gray-300 px-4 py-2">
                          {booth.booth || "-"}
                        </td>
                        <td className="border border-gray-300 px-4 py-2">
                          {booth.size || "-"}
                        </td>
                        <td className="border border-gray-300 px-4 py-2">
                          {placesData?.email ? (
                            <a
                              href={`mailto:${placesData.email}`}
                              className="text-blue-600 hover:underline text-sm break-all"
                            >
                              {placesData.email}
                            </a>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </td>
                        <td className="border border-gray-300 px-4 py-2">
                          {placesData?.phone ? (
                            <a
                              href={`tel:${placesData.phone}`}
                              className="text-gray-900 hover:text-blue-600 text-sm"
                            >
                              {placesData.phone}
                            </a>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </td>
                        <td className="border border-gray-300 px-4 py-2">
                          {placesData?.website ? (
                            <a
                              href={placesData.website}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:underline text-sm break-all max-w-xs truncate inline-block"
                            >
                              {placesData.website}
                            </a>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </td>
                        <td className="border border-gray-300 px-4 py-2 max-w-xs">
                          {placesData?.address ? (
                            <span className="text-sm text-gray-700 line-clamp-2">
                              {placesData.address}
                            </span>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </td>
                        <td className="border border-gray-300 px-4 py-2">
                          {hasData ? (
                            <div className="flex items-center gap-1">
                              <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                              <span className="text-xs text-green-700 font-medium">
                                {dataCount}/4
                              </span>
                            </div>
                          ) : (
                            <div className="flex items-center gap-1">
                              <span className="w-2 h-2 bg-gray-400 rounded-full"></span>
                              <span className="text-xs text-gray-500">
                                No data
                              </span>
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Export Button */}
            <div className="mt-4 flex justify-between items-center">
              <button
                onClick={() => {
                  const enrichedBooths = result.booths.filter(
                    (booth) => booth.places_data?.email
                  );
                  if (enrichedBooths.length === 0) {
                    alert("No companies with emails to export");
                    return;
                  }

                  const csvContent = [
                    [
                      "Company",
                      "Booth",
                      "Email",
                      "Phone",
                      "Website",
                      "Address",
                    ].join(","),
                    ...enrichedBooths.map((booth) =>
                      [
                        booth.company_name,
                        booth.booth || "",
                        booth.places_data?.email || "",
                        booth.places_data?.phone || "",
                        booth.places_data?.website || "",
                        booth.places_data?.address || "",
                      ]
                        .map(
                          (field) => `"${String(field).replace(/"/g, '""')}"`
                        )
                        .join(",")
                    ),
                  ].join("\n");

                  const blob = new Blob([csvContent], { type: "text/csv" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `${result.filename || "booths"}_with_emails.csv`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm font-medium"
                disabled={stats.withEmail === 0}
              >
                📧 Export {stats.withEmail} Companies with Emails
              </button>

              <button
                onClick={() => {
                  const allBooths = result.booths;
                  const csvContent = [
                    [
                      "Company",
                      "Booth",
                      "Size",
                      "Email",
                      "Phone",
                      "Website",
                      "Address",
                      "Enriched",
                    ].join(","),
                    ...allBooths.map((booth) =>
                      [
                        booth.company_name,
                        booth.booth || "",
                        booth.size || "",
                        booth.places_data?.email || "",
                        booth.places_data?.phone || "",
                        booth.places_data?.website || "",
                        booth.places_data?.address || "",
                        booth.places_data ? "Yes" : "No",
                      ]
                        .map(
                          (field) => `"${String(field).replace(/"/g, '""')}"`
                        )
                        .join(",")
                    ),
                  ].join("\n");

                  const blob = new Blob([csvContent], { type: "text/csv" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `${result.filename || "booths"}_all_data.csv`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
                className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded text-sm font-medium"
              >
                📊 Export All Data
              </button>
            </div>

            {/* Raw data toggle */}
            <details className="mt-4">
              <summary className="cursor-pointer text-sm text-gray-500 hover:text-gray-700">
                Show Raw Data
              </summary>
              <pre className="mt-2 text-xs bg-gray-100 p-3 rounded border overflow-x-auto max-h-40">
                {JSON.stringify(result, null, 2)}
              </pre>
            </details>
          </div>
        );
      })}
    </div>
  );
};

export default Results;
