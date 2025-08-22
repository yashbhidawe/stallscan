import React, { useState, useCallback } from "react";
import { Upload, File, X, AlertCircle, CheckCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import Results, { type BoothData } from "./Results";

interface UploadedFile {
  file: File;
  id: string;
}

interface StallData {
  filename: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  booths: BoothData[];
  total_booths: number;
  extraction_method: string;
  processing_time: number;
}

const PDFUploader: React.FC = () => {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string>("");
  const [success, setSuccess] = useState<string>("");
  const [isUploading, setIsUploading] = useState(false);
  const [results, setResults] = useState<StallData[]>([]);

  const validateFile = (file: File): string | null => {
    if (file.type !== "application/pdf") {
      return "Only PDF files are allowed";
    }

    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
      return "File size must be less than 10MB";
    }

    return null;
  };

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files) return;

      setError("");
      setSuccess(""); // Clear success message when new files are added
      const newFiles: UploadedFile[] = [];

      Array.from(files).forEach((file) => {
        const validationError = validateFile(file);
        if (validationError) {
          setError(validationError);
          return;
        }

        // Check for duplicates
        const isDuplicate = uploadedFiles.some(
          (uploadedFile) =>
            uploadedFile.file.name === file.name &&
            uploadedFile.file.size === file.size
        );

        if (!isDuplicate) {
          newFiles.push({
            file,
            id: `${file.name}-${Date.now()}-${Math.random()
              .toString(36)
              .substr(2, 9)}`,
          });
        }
      });

      setUploadedFiles((prev) => [...prev, ...newFiles]);
    },
    [uploadedFiles]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragOver(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles]
  );

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files);
  };

  const removeFile = (id: string) => {
    setUploadedFiles((prev) => prev.filter((file) => file.id !== id));
    setError("");
    setSuccess("");
  };

  const uploadFiles = async () => {
    if (uploadedFiles.length === 0) {
      setError("Please select at least one PDF file");
      return;
    }

    setIsUploading(true);
    setError("");
    setSuccess("");

    try {
      const formData = new FormData();
      formData.append("file", uploadedFiles[0].file); // use key "file"

      const response = await fetch("http://localhost:8000/extract", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }

      const result = await response.json();
      console.log("Upload successful:", result);

      // Extract the results array from the API response
      if (result && result.results && Array.isArray(result.results)) {
        setResults(result.results);
        console.log("Setting results:", result.results);
      } else {
        console.error("Unexpected API response format:", result);
        setError("Unexpected response format from server");
      }

      // Show success message with details from API response
      const successMsg =
        result.message ||
        `Successfully processed ${uploadedFiles.length} file${
          uploadedFiles.length !== 1 ? "s" : ""
        }!`;
      const stallInfo = result.total_stalls_found
        ? ` Found ${result.total_stalls_found} stalls.`
        : "";
      setSuccess(successMsg + stallInfo);

      // Clear files after successful upload (with a small delay to show success)
      setTimeout(() => {
        setUploadedFiles([]);
      }, 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const resetUploader = () => {
    setUploadedFiles([]);
    setResults([]);
    setError("");
    setSuccess("");
  };

  return (
    <div className="w-full max-w-2xl mx-auto p-6">
      <Card>
        <CardHeader>
          <CardTitle>Upload Floor Plan PDFs</CardTitle>
          <CardDescription>
            Upload PDF files to extract stall information and company details
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Upload Area */}
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            className={`
              border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
              ${
                isDragOver
                  ? "border-primary bg-primary/5"
                  : "border-gray-300 hover:border-primary hover:bg-gray-50"
              }
            `}
          >
            <input
              type="file"
              accept=".pdf"
              multiple
              onChange={handleFileInput}
              className="hidden"
              id="file-upload"
            />
            <label htmlFor="file-upload" className="cursor-pointer">
              <Upload className="w-12 h-12 mx-auto text-gray-400 mb-4" />
              <p className="text-lg font-medium text-gray-900 mb-2">
                Drop PDF files here or click to browse
              </p>
              <p className="text-sm text-gray-500">
                Supports multiple files up to 10MB each
              </p>
            </label>
          </div>

          {/* Success Alert */}
          {success && (
            <Alert className="border-green-200 bg-green-50">
              <CheckCircle className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-800">
                {success}
              </AlertDescription>
            </Alert>
          )}

          {/* Error Alert */}
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Uploaded Files List */}
          {uploadedFiles.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-gray-900">
                Selected Files ({uploadedFiles.length})
              </h3>
              <div className="space-y-2">
                {uploadedFiles.map(({ file, id }) => (
                  <div
                    key={id}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <div className="flex items-center space-x-3">
                      <File className="w-5 h-5 text-red-500" />
                      <div>
                        <p className="text-sm font-medium text-gray-900">
                          {file.name}
                        </p>
                        <p className="text-xs text-gray-500">
                          {formatFileSize(file.size)}
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeFile(id)}
                      className="text-gray-400 hover:text-red-500"
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex justify-end space-x-2">
            {results.length > 0 && (
              <Button
                variant="outline"
                onClick={resetUploader}
                disabled={isUploading}
              >
                Upload New Files
              </Button>
            )}
            <Button
              onClick={uploadFiles}
              disabled={uploadedFiles.length === 0 || isUploading}
              className="min-w-32"
            >
              {isUploading
                ? "Uploading..."
                : `Upload ${uploadedFiles.length} file${
                    uploadedFiles.length !== 1 ? "s" : ""
                  }`}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results Component */}
      {results.length > 0 && <Results results={results} />}
    </div>
  );
};

export default PDFUploader;
