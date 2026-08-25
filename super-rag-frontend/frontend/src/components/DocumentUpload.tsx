import { useState, useRef, useCallback } from 'react';
import { Upload, X, File as FileIcon, CheckCircle2, AlertCircle } from 'lucide-react';
import { collectionsApi } from '../api/client';
import './DocumentUpload.css';

interface DocumentUploadProps {
  collectionId: string;
  onUploadSuccess?: () => void;
}

interface FileWithStatus {
  file: File;
  status: 'pending' | 'uploading' | 'success' | 'error';
  error?: string;
}

export default function DocumentUpload({ collectionId, onUploadSuccess }: DocumentUploadProps) {
  const [files, setFiles] = useState<FileWithStatus[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB

  const validateFile = (file: File): string | null => {
    if (file.size > MAX_FILE_SIZE) {
      return `File size exceeds 100MB limit: ${file.name}`;
    }
    return null;
  };

  const handleFiles = useCallback((fileList: FileList | null) => {
    if (!fileList) return;

    const newFiles: FileWithStatus[] = [];
    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i];
      const error = validateFile(file);
      if (error) {
        alert(error);
        continue;
      }
      newFiles.push({ file, status: 'pending' });
    }

    setFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [handleFiles]);

  const handleRemoveFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleUpload = useCallback(async () => {
    if (files.length === 0 || isUploading) return;

    const pendingFiles = files.filter((f) => f.status === 'pending');
    if (pendingFiles.length === 0) return;

    setIsUploading(true);

    setFiles((prev) =>
      prev.map((f) => (f.status === 'pending' ? { ...f, status: 'uploading' as const } : f))
    );

    try {
      const filesToUpload = pendingFiles.map((f) => f.file);
      await collectionsApi.uploadDocuments(collectionId, filesToUpload);

      setFiles((prev) =>
        prev.map((f) => (f.status === 'uploading' ? { ...f, status: 'success' as const } : f))
      );

      setTimeout(() => {
        setFiles([]);
        onUploadSuccess?.();
      }, 1500);
    } catch (error: any) {
      console.error('Upload failed:', error);
      const errorMessage = error?.message || 'Failed to upload files';

      setFiles((prev) =>
        prev.map((f) =>
          f.status === 'uploading'
            ? { ...f, status: 'error' as const, error: errorMessage }
            : f
        )
      );

      alert(`Upload failed: ${errorMessage}`);
    } finally {
      setIsUploading(false);
    }
  }, [files, collectionId, isUploading, onUploadSuccess]);

  const formatFileSize = (bytes: number) => {
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  const pendingCount = files.filter((f) => f.status === 'pending').length;
  const hasFiles = files.length > 0;

  return (
    <div className="document-upload">
      <div className="upload-steps">
        <div className="step">
          <span className="step-number">①</span>
          <span className="step-text">Browse Files</span>
        </div>
        <div className="step-arrow">→</div>
        <div className="step">
          <span className="step-number">②</span>
          <span className="step-text">Upload</span>
        </div>
        <div className="step-arrow">→</div>
        <div className="step">
          <span className="step-number">③</span>
          <span className="step-text">Save to collection</span>
        </div>
      </div>

      <div
        className={`upload-area ${isDragging ? 'dragging' : ''} ${hasFiles ? 'has-files' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !hasFiles && fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={handleFileInputChange}
          className="file-input"
          style={{ display: 'none' }}
        />

        {!hasFiles ? (
          <>
            <div className="upload-icon">
              <Upload size={48} />
            </div>
            <p className="upload-text">Drag & drop files here</p>
            <p className="upload-hint">Or click to browse (max 100MB for each file)</p>
          </>
        ) : (
          <div className="files-list">
            {files.map((fileWithStatus, index) => (
              <div key={index} className={`file-item ${fileWithStatus.status}`}>
                <div className="file-item-content">
                  <FileIcon size={20} className="file-icon" />
                  <div className="file-info">
                    <span className="file-name">{fileWithStatus.file.name}</span>
                    <span className="file-size">{formatFileSize(fileWithStatus.file.size)}</span>
                  </div>
                  <div className="file-status">
                    {fileWithStatus.status === 'pending' && (
                      <span className="status-text">Ready</span>
                    )}
                    {fileWithStatus.status === 'uploading' && (
                      <span className="status-text uploading">Uploading...</span>
                    )}
                    {fileWithStatus.status === 'success' && (
                      <CheckCircle2 size={20} className="status-icon success" />
                    )}
                    {fileWithStatus.status === 'error' && (
                      <AlertCircle size={20} className="status-icon error" />
                    )}
                  </div>
                  {fileWithStatus.status !== 'uploading' && (
                    <button
                      className="remove-file-button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRemoveFile(index);
                      }}
                    >
                      <X size={16} />
                    </button>
                  )}
                </div>
                {fileWithStatus.error && (
                  <div className="file-error">{fileWithStatus.error}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {hasFiles && (
        <div className="upload-actions">
          <button
            className="upload-button"
            onClick={handleUpload}
            disabled={isUploading || pendingCount === 0}
          >
            {isUploading ? 'Uploading...' : `Upload ${pendingCount} file${pendingCount !== 1 ? 's' : ''}`}
          </button>
          <button
            className="clear-button"
            onClick={() => setFiles([])}
            disabled={isUploading}
          >
            Clear All
          </button>
        </div>
      )}
    </div>
  );
}
