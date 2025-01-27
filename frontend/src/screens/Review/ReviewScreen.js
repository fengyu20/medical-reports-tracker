// frontend/src/screens/Review/ReviewScreen.js
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ReviewForm from './ReviewForm';
import axios from 'axios';
import './ReviewScreen.css'; 

export default function ReviewScreen() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [dataId, setDataId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    const fetchLatestUpload = async () => {
      try {
        const response = await axios.get(
          'http://localhost:5001/clinical-data/latest-upload',
          { withCredentials: true }
        );

        if (response.data && Object.keys(response.data).length > 0) {
          setData(response.data);
          setDataId(response.data['PatientId#TestDateTime#Indicator']);
        } else {
          setError('No clinical data entries found.');
        }
      } catch (err) {
        console.error('Error fetching latest upload:', err);
        setError('Failed to fetch clinical data. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    fetchLatestUpload();
  }, []);

  const handleSubmit = async (updatedData) => {
    if (!dataId) {
      setError('Invalid data identifier. Please try again.');
      return;
    }

    try {
      const response = await axios.put(
        `http://localhost:5001/clinical-data/${dataId}`,
        updatedData,
        { withCredentials: true }
      );

      console.log('Review submitted successfully:', response.data);
      setSuccess('Data updated successfully! Redirecting to Home Page...');

      // Redirect after a short delay to allow users to read the message
      setTimeout(() => {
        navigate('/home');
      }, 3000); // 3-second delay
    } catch (err) {
      console.error('Error submitting review:', err);
      setError('Failed to submit review. Please try again.');
    }
  };

  if (loading) {
    return (
      <div className="loadingContainer">
        <div className="spinner"></div>
        <h2>Processing Your Data...</h2>
        <p>Please wait while we prepare your data for review.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="errorContainer">
        <div className="errorBox">{error}</div>
      </div>
    );
  }

  return (
    <div className="reviewContainer">
      {success && <div className="successBox">{success}</div>}
      <ReviewForm data={data} onSubmit={handleSubmit} />
    </div>
  );
}