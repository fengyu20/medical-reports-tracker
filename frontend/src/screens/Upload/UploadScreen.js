// src/screens/Upload/UploadScreen.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { checkSession } from '../../utils/auth';
import './UploadScreen.css';
import Header from '../../components/Header/Header';


const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';

const UploadScreen = () => {
  const [file, setFile] = useState(null);
  const [indicatorInput, setIndicatorInput] = useState('');
  const [indicators, setIndicators] = useState([]);
  const [error, setError] = useState(null);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [step, setStep] = useState(1);
  const navigate = useNavigate();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [authError, setAuthError] = useState(null);

  useEffect(() => {
    let mounted = true;

    const verifyAuth = async () => {
      try {
        const { authenticated, user } = await checkSession();
        
        if (!mounted) return;

        if (!authenticated) {
          navigate('/signin');
          return;
        }
        
        setIsAuthenticated(true);
        setIsLoading(false);
      } catch (error) {
        if (!mounted) return;
        console.error('Auth verification failed:', error);
        setAuthError(error.message);
        navigate('/signin');
      }
    };

    verifyAuth();

    return () => {
      mounted = false;
    };
  }, [navigate]);

  if (isLoading) {
    return <div className="loading-container">
      <div className="loading-spinner"></div>
      <p>Verifying authentication...</p>
    </div>;
  }

  if (authError) {
    return <div className="error-container">
      <p>Authentication error: {authError}</p>
      <button onClick={() => navigate('/signin')}>Return to Sign In</button>
    </div>;
  }

  // Only render content when authenticated
  if (!isAuthenticated) {
    return <div>Checking authentication...</div>;
  }

  const handleFileChange = (event) => {
    setFile(event.target.files[0]);
    setStep(2);
  };

  const handleIndicatorAdd = () => {
    if (indicatorInput.trim()) {
      setIndicators([...indicators, indicatorInput.trim()]);
      setIndicatorInput('');
    }
  };

  const handleIndicatorRemove = (index) => {
    setIndicators(indicators.filter((_, i) => i !== index));
  };

  const handleUpload = async (file) => {
    try {
      // First, get the presigned URL
      const presignedUrlResponse = await fetch(`${API_URL}/clinical-data/get-upload-url`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          filename: file.name,
          contentType: file.type,
          indicators: indicators
        })
      });

      if (!presignedUrlResponse.ok) {
        throw new Error('Failed to get upload URL');
      }

      const { uploadUrl, fileKey } = await presignedUrlResponse.json();

      // Validate the URL before using it
      if (!uploadUrl || typeof uploadUrl !== 'string') {
        throw new Error('Invalid upload URL received from server');
      }

      // Now upload the file to S3 using the presigned URL
      const uploadResponse = await fetch(uploadUrl, {
        method: 'PUT',
        body: file,
        headers: {
          'Content-Type': file.type,
        },
      });

      if (!uploadResponse.ok) {
        throw new Error('Failed to upload file to S3');
      }

      // Notify the backend that the upload is complete
      const confirmResponse = await fetch(`${API_URL}/clinical-data/confirm-upload`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          fileKey: fileKey,
          filename: file.name,
          contentType: file.type
        })
      });

      if (!confirmResponse.ok) {
        throw new Error('Failed to confirm upload');
      }

      return await confirmResponse.json();

    } catch (error) {
      console.error('Upload error:', error);
      throw error;
    }
  };

  const renderStep1 = () => (
    <div className="file-upload-section">
      <h2>Upload Clinical Report</h2>
      <p className="instruction-text">
        Please select a PDF or image file of your clinical report
      </p>
      <input
        type="file"
        onChange={handleFileChange}
        accept=".pdf,.png,.jpg,.jpeg"
        className="file-input"
      />
    </div>
  );

  const renderStep2 = () => (
    <div className="indicator-input-section">
      <h2>Specify Indicators to Track</h2>
      <p className="instruction-text">
        Enter the names of health indicators you want to track from this report
        (e.g., "blood sugar", "cholesterol", etc.)
      </p>
      <div className="input-container">
        <input
          type="text"
          value={indicatorInput}
          onChange={(e) => setIndicatorInput(e.target.value)}
          placeholder="Enter indicator name"
          className="indicator-input"
        />
        <button 
          onClick={handleIndicatorAdd}
          className="add-indicator-btn"
          disabled={!indicatorInput.trim()}
        >
          Add
        </button>
      </div>
      {indicators.length > 0 && (
        <div className="indicators-list">
          {indicators.map((indicator, index) => (
            <div key={index} className="indicator-tag">
              {indicator}
              <button 
                onClick={() => handleIndicatorRemove(index)}
                className="remove-indicator-btn"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
      <button
        onClick={() => {
          setProcessing(true);
          setError(null);
          handleUpload(file)
            .then(() => {
              setUploadStatus('success');
              console.log('Upload successful. Preparing to redirect.');
              setTimeout(() => {
                navigate('/review');
                console.log('Redirected to Review Screen.');
              }, 3000);
            })
            .catch((err) => {
              setError(err.message || 'Upload failed');
            })
            .finally(() => {
              setProcessing(false);
            });
        }}
        disabled={processing || !indicators.length || !file}
        className="upload-button"
      >
        {processing ? 'Processing...' : 'Upload Report'}
      </button>
    </div>
  );

  return (
    <div className="upload-container">
      {error && <div className="error-message">{error}</div>}
      {uploadStatus === 'success' && (
        <div className="success-message">
          Upload successful! Redirecting to Review Page...
        </div>
      )}
      {step === 1 ? renderStep1() : renderStep2()}
    </div>
  );
};

export default UploadScreen;