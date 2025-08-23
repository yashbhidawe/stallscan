import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export interface BoothData {
  company_name: string;
  booth: string | null;
  size: string | null;
  email: string | null; // You'll need to handle this separately
  phone: string | null;
  website: string | null;
  address: string | null;
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
  console.log("Results component received:", results);

  if (!results || results.length === 0) {
    return (
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Processing Results</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-500">No results to display yet.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle>Extraction Results</CardTitle>
        <p className="text-sm text-gray-600">
          Processed {results.length} file{results.length !== 1 ? "s" : ""}
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        {results.map((result, index) => (
          <div key={index} className="border rounded-lg p-4 bg-gray-50">
            <div className="mb-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                📄 {result.filename || `File ${index + 1}`}
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="font-medium text-gray-600">
                    Total Booths:
                  </span>
                  <p className="text-lg font-bold text-blue-600">
                    {result.total_booths || 0}
                  </p>
                </div>
                {result.processing_time && (
                  <div>
                    <span className="font-medium text-gray-600">
                      Processing Time:
                    </span>
                    <p className="text-green-600">{result.processing_time}s</p>
                  </div>
                )}
                {result.enrichment_time && (
                  <div>
                    <span className="font-medium text-gray-600">
                      Enrichment Time:
                    </span>
                    <p className="text-purple-600">{result.enrichment_time}s</p>
                  </div>
                )}
                {result.places_api_calls && (
                  <div>
                    <span className="font-medium text-gray-600">
                      API Calls:
                    </span>
                    <p className="text-orange-600">{result.places_api_calls}</p>
                  </div>
                )}
              </div>
            </div>
            {/* Booths Data */}
            // In your Results component, modify the booth display: // In your
            Results component, modify the booth display:
            {result.booths.map((booth, boothIndex) => (
              <div
                key={boothIndex}
                className="bg-white p-4 rounded-lg border shadow-sm"
              >
                {/* Company Name */}
                <h5 className="font-semibold text-lg text-gray-900 mb-4">
                  {booth.company_name}
                </h5>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                  {/* Left Column: Booth Info */}
                  <div className="space-y-3">
                    {booth.booth && (
                      <div>
                        <span className="font-medium text-gray-600">
                          Booth Number:
                        </span>
                        <p className="text-gray-900 font-mono">{booth.booth}</p>
                      </div>
                    )}

                    {booth.size && (
                      <div>
                        <span className="font-medium text-gray-600">
                          Stall Size:
                        </span>
                        <p className="text-gray-900">{booth.size}</p>
                      </div>
                    )}

                    {booth.email && (
                      <div>
                        <span className="font-medium text-gray-600">
                          Email:
                        </span>
                        <a
                          href={`mailto:${booth.email}`}
                          className="text-blue-600 hover:underline break-all"
                        >
                          {booth.email}
                        </a>
                      </div>
                    )}
                  </div>

                  {/* Right Column: Contact Info */}
                  <div className="space-y-3">
                    {booth.phone && (
                      <div>
                        <span className="font-medium text-gray-600">
                          Phone:
                        </span>
                        <a
                          href={`tel:${booth.phone}`}
                          className="text-gray-900 hover:text-blue-600"
                        >
                          {booth.phone}
                        </a>
                      </div>
                    )}

                    {booth.website && (
                      <div>
                        <span className="font-medium text-gray-600">
                          Website:
                        </span>
                        <a
                          href={booth.website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:underline break-all"
                        >
                          {booth.website}
                        </a>
                      </div>
                    )}

                    {booth.address && (
                      <div>
                        <span className="font-medium text-gray-600">
                          Address:
                        </span>
                        <p className="text-gray-900">{booth.address}</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {/* Debug raw JSON */}
            <details className="mt-4">
              <summary className="cursor-pointer text-sm text-gray-500 hover:text-gray-700">
                Show Raw Data
              </summary>
              <pre className="mt-2 text-xs bg-white p-3 rounded border overflow-x-auto max-h-40">
                {JSON.stringify(result, null, 2)}
              </pre>
            </details>
          </div>
        ))}
      </CardContent>
    </Card>
  );
};

export default Results;
