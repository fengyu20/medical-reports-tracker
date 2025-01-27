// src/screens/Upload/UploadForm.js
import React, { useState } from 'react';
import './UploadScreen.css'; // Ensure this line is present

export default function UploadForm({ onSubmit }) {
  const [file, setFile] = useState(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (file) {
      onSubmit({ file });
    }
  };

  return (
    <form onSubmit={handleSubmit} className="upload-form">
      <input
        type="file"
        onChange={(e) => setFile(e.target.files[0])}
        className="file-input"
      />
      <button type="submit" className="submit-button">
        Upload File
      </button>
    </form>
  );
}