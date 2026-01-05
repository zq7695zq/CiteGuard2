import React, { useCallback, useState } from 'react';
import { Upload, FileText, CheckCircle, AlertCircle } from 'lucide-react';
import { cn } from '../lib/utils';
import axios from 'axios';

interface UploadFormProps {
    onTaskCreated: (taskId: string) => void;
}

export const UploadForm: React.FC<UploadFormProps> = ({ onTaskCreated }) => {
    const [bibFile, setBibFile] = useState<File | null>(null);
    const [texFiles, setTexFiles] = useState<File[]>([]);
    const [isUploading, setIsUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>, type: 'bib' | 'tex') => {
        if (e.target.files) {
            if (type === 'bib') {
                setBibFile(e.target.files[0]);
            } else {
                setTexFiles(Array.from(e.target.files));
            }
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!bibFile) {
            setError("Please select a .bib file");
            return;
        }

        setIsUploading(true);
        setError(null);

        const formData = new FormData();
        formData.append('bib_file', bibFile);
        texFiles.forEach((file) => {
            formData.append('tex_files', file);
        });

        try {
            const response = await axios.post('http://localhost:8000/api/v1/submit/', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });
            onTaskCreated(response.data.task_id);
        } catch (err) {
            setError("Failed to upload files. Please try again.");
            console.error(err);
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <div className="w-full max-w-xl mx-auto p-6 bg-white rounded-xl shadow-lg border border-gray-100">
            <h2 className="text-2xl font-bold mb-6 text-gray-800">Start Citation Check</h2>

            <form onSubmit={handleSubmit} className="space-y-6">
                {/* Bib File Input */}
                <div className="space-y-2">
                    <label className="block text-sm font-medium text-gray-700">Bibliography File (.bib)</label>
                    <div className="relative border-2 border-dashed border-gray-300 rounded-lg p-6 hover:bg-gray-50 transition-colors">
                        <input
                            type="file"
                            accept=".bib"
                            onChange={(e) => handleFileChange(e, 'bib')}
                            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                        />
                        <div className="text-center">
                            <Upload className="mx-auto h-10 w-10 text-gray-400" />
                            <p className="mt-2 text-sm text-gray-600">
                                {bibFile ? bibFile.name : "Drag & drop or click to upload .bib"}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Tex Files Input */}
                <div className="space-y-2">
                    <label className="block text-sm font-medium text-gray-700">LaTeX Files (.tex)</label>
                    <div className="relative border-2 border-dashed border-gray-300 rounded-lg p-6 hover:bg-gray-50 transition-colors">
                        <input
                            type="file"
                            accept=".tex"
                            multiple
                            onChange={(e) => handleFileChange(e, 'tex')}
                            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                        />
                        <div className="text-center">
                            <FileText className="mx-auto h-10 w-10 text-gray-400" />
                            <p className="mt-2 text-sm text-gray-600">
                                {texFiles.length > 0
                                    ? `${texFiles.length} file(s) selected`
                                    : "Drag & drop or click to upload .tex files (Optional)"}
                            </p>
                        </div>
                    </div>
                </div>

                {error && (
                    <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 p-3 rounded-md">
                        <AlertCircle className="h-4 w-4" />
                        {error}
                    </div>
                )}

                <button
                    type="submit"
                    disabled={isUploading}
                    className={cn(
                        "w-full py-3 px-4 rounded-lg text-white font-medium transition-all",
                        isUploading
                            ? "bg-blue-400 cursor-not-allowed"
                            : "bg-blue-600 hover:bg-blue-700 shadow-md hover:shadow-lg"
                    )}
                >
                    {isUploading ? "Uploading..." : "Start Verification"}
                </button>
            </form>
        </div>
    );
};
