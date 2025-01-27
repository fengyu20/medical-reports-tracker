// frontend/src/screens/Review/ReviewForm.js
import React, { useState } from 'react';
import './ReviewForm.css'; // Correctly import the ReviewForm.css

export default function ReviewForm({ data, onSubmit }) {
  const [formData, setFormData] = useState({
    PatientName: data.PatientName || '',
    CollectedDate: data.CollectedDate || '',
    Result: data.Result || '',
    Units: data.Units || '',
    LowerRange: data.LowerRange || '',
    UpperRange: data.UpperRange || '',
    Indicator: data.Indicator || '',
  });

  const [formError, setFormError] = useState('');

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    // Basic validation
    for (const field in formData) {
      if (formData[field] === '') {
        setFormError(`Please fill out the ${field} field.`);
        return;
      }
    }

    // Clear any previous errors
    setFormError('');

    // Call the onSubmit prop with the updated data
    onSubmit(formData);
  };

  return (
    <div className="formContainer"> {/* Updated className */}
      <h2 className="formHeader">Review Your Data</h2> {/* Updated className */}
      {formError && <div className="errorMessage">{formError}</div>} {/* Updated className */}

      <form onSubmit={handleSubmit}>
        <div className="formField">
            <label htmlFor="Indicator">Indicator Name:</label>
            <input
              type="text"
              id="indicator"
              name="indicator"
              value={formData.Indicator}
              onChange={handleChange}
              required
            />
        </div>

        <div className="formField">
          <label htmlFor="PatientName">Patient Name:</label>
          <input
            type="text"
            id="PatientName"
            name="PatientName"
            value={formData.PatientName}
            onChange={handleChange}
            required
          />
        </div>


        <div className="formField">
          <label htmlFor="CollectedDate">Collected Date:</label>
          <input
            type="date"
            id="CollectedDate"
            name="CollectedDate"
            value={formData.CollectedDate}
            onChange={handleChange}
            required
          />
        </div>

        <div className="formField">
          <label htmlFor="Result">Result:</label>
          <input
            type="number"
            id="Result"
            name="Result"
            value={formData.Result}
            onChange={handleChange}
            required
          />
        </div>

        <div className="formField">
          <label htmlFor="Units">Units:</label>
          <input
            type="text"
            id="Units"
            name="Units"
            value={formData.Units}
            onChange={handleChange}
            required
          />
        </div>

        <div className="formField">
          <label htmlFor="LowerRange">Lower Range:</label>
          <input
            type="number"
            id="LowerRange"
            name="LowerRange"
            value={formData.LowerRange}
            onChange={handleChange}
            required
          />
        </div>

        <div className="formField">
          <label htmlFor="UpperRange">Upper Range:</label>
          <input
            type="number"
            id="UpperRange"
            name="UpperRange"
            value={formData.UpperRange}
            onChange={handleChange}
            required
          />
        </div>

        <button type="submit" className="submitButton"> {/* Updated className */}
          Submit Review
        </button>
      </form>
    </div>
  );
}