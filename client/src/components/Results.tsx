import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export interface BoothData {
  company_name: string;
  booth: string | null;
  size: string | null;
}

interface ApiResponse {
  total_booths: number;
  booths: BoothData[];
  filename?: string; // optional since backend may not send it yet
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
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="font-medium text-gray-600">
                    Total Booths:
                  </span>
                  <p className="text-lg font-bold text-blue-600">
                    {result.total_booths || 0}
                  </p>
                </div>
              </div>
            </div>

            {/* Booths Data */}
            {result.booths && result.booths.length > 0 && (
              <div>
                <h4 className="font-semibold text-gray-800 mb-3">
                  🏪 Booth Details ({result.booths.length} found)
                </h4>
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {result.booths.map((booth, boothIndex) => (
                    <div
                      key={boothIndex}
                      className="bg-white p-3 rounded border"
                    >
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                        {Object.entries(booth).map(([key, value]) => (
                          <div key={key}>
                            <span className="font-medium text-gray-600 capitalize">
                              {key.replace(/_/g, " ")}:
                            </span>
                            <p className="text-gray-900 break-words">
                              {value ?? "N/A"}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

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
