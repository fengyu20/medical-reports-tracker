// src/screens/Home/HomeScreen.js
import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { FaUpload } from 'react-icons/fa';
import './HomeScreen.css';
import { checkSession } from '../../utils/auth';
import Header from '../../components/Header/Header';
import { AuthProvider } from '../../contexts/AuthContext'; 

const HomeScreen = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [chartsData, setChartsData] = useState([]);
  const navigate = useNavigate();

  // (Optional) JWT retrieval logic
  const getToken = () => {
    return localStorage.getItem('token');
  };

  useEffect(() => {
    fetchAllData();
  }, []);

  const fetchAllData = async () => {
    try {
      // 1. Call the all trending endpoint
      const response = await axios.get(
        'http://localhost:5001/clinical-data/trending/all',
        { 
          withCredentials: true,
          headers: { Authorization: `Bearer ${getToken()}` }
        }
      );
      
      // 2. Extract items from response
      const { items } = response.data;
      if (!items || items.length === 0) {
        setError('No clinical data found for your account. Redirecting you to upload a new report...');
        setTimeout(() => {
          navigate('/upload');
        }, 2000);
        return;
      }

      // 3. Group by Indicator
      const grouped = groupDataByIndicator(items);

      // 4. Process each group's ranges
      const finalCharts = grouped.map(group => {
        // Sort the group by UploadDate descending to prioritize latest entries
        group.sort((a, b) => new Date(a.CollectedDate) - new Date(b.CollectedDate));
        // Attempt to find the latest available LowerRange and UpperRange
        let lowerRange = null;
        let upperRange = null;

        for (let entry of group) {
          if (lowerRange === null && entry.LowerRange != null) {
            lowerRange = parseFloat(entry.LowerRange);
          }
          if (upperRange === null && entry.UpperRange != null) {
            upperRange = parseFloat(entry.UpperRange);
          }
          if (lowerRange !== null && upperRange !== null) {
            break; // Stop if both ranges are found
          }
        }

        // If ranges are still null, they will be omitted from the chart
        const firstItem = group[0];
        const dataArray = group.map(d => ({
          date: d.CollectedDate,
          result: parseFloat(d.Result),
          laboratory: d.LaboratoryName
        }));

        return {
          indicator: firstItem.Indicator,
          lowerRange: lowerRange, 
          upperRange: upperRange, 
          units: firstItem.Units || '',
          data: dataArray
        };
      });

      // 5. Update state with the processed charts data
      setChartsData(finalCharts);
    } catch (err) {
      if (err.response && err.response.status === 401) {
        setError('Unauthorized. Please log in again.');
      } else {
        setError('Failed to load trending data.');
      }
      console.error('Error fetching data:', err);
    } finally {
      setLoading(false);
    }
  };

  // Helper function to group data by Indicator
  const groupDataByIndicator = (data) => {
    const grouped = {};

    data.forEach(item => {
      const indicator = item.Indicator;
      if (!grouped[indicator]) {
        grouped[indicator] = [];
      }
      grouped[indicator].push(item);
    });

    return Object.values(grouped);
  };

  const renderChart = (chartData) => {
    const uniqueKey = `${chartData.indicator}-${chartData.CollectedDate}`;
    if (!chartData || !chartData.data || chartData.data.length === 0) {
      return (
        <div key={chartData?.indicator || 'no-data'} className="chart-container">
          <p>No data available for {chartData?.indicator || 'this chart'}.</p>
        </div>
      );
    }
  
    const dates = chartData.data.map(item => item.date);
    const results = chartData.data.map(item => item.result);
    const laboratories = chartData.data.map(item => item.laboratory);
    const units = chartData.units || '';

    // Prepare the main results trace
    const traceResults = {
      x: dates,
      y: results,
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Results',
      line: { color: '#2196F3' },
      hovertemplate: `
        <b>Result:</b> %{y:.1f} ${units}<br>
        <b>Date:</b> %{x}<br>
        <b>Lab:</b> %{customdata}<extra></extra>
      `,
      customdata: laboratories,
    };

    const dataTraces = [traceResults];

    // Add Lower Range line if available
    if (chartData.lowerRange !== null && chartData.upperRange !== null) {
      const traceLowerRange = {
        x: dates,
        y: Array(dates.length).fill(chartData.lowerRange),
        type: 'scatter',
        mode: 'lines',
        name: 'Lower Range',
        line: { color: 'rgba(255, 0, 0, 0.7)', dash: 'dash' },
        hovertemplate: `<b>Lower Range:</b> ${chartData.lowerRange} ${units}<extra></extra>`,
      };
    
      const traceUpperRange = {
        x: dates,
        y: Array(dates.length).fill(chartData.upperRange),
        type: 'scatter',
        mode: 'lines',
        name: 'Upper Range',
        line: { color: 'rgba(255, 0, 0, 0.7)', dash: 'dash' },
        hovertemplate: `<b>Upper Range:</b> ${chartData.upperRange} ${units}<extra></extra>`,
      };

      dataTraces.push(traceLowerRange, traceUpperRange);
    }

    const layout = {
      title: {
        text: `Trending: ${chartData.indicator}`,
        font: { size: 24, family: 'Arial, sans-serif', color: '#333' },
        x: 0.05,
        xanchor: 'left',
      },
      xaxis: {
        title: { text: 'Collection Date', font: { size: 14 } },
        tickformat: '%Y-%m-%d',
        type: 'date',
      },
      yaxis: {
        title: { text: `Result (${units})`, font: { size: 14 } },
        zeroline: false,
      },
      hovermode: 'closest',
      showlegend: false,
      //showlegend: chartData.lowerRange !== null && chartData.upperRange !== null, // Show legend only if ranges are displayed
      margin: { t: 60, r: 50, b: 50, l: 60 },
      responsive: true,
      hoverlabel: { bgcolor: 'white', font: { size: 14 } },
    };
  
    const config = {
      responsive: true,
      displayModeBar: false,
      staticPlot: false,
      scrollZoom: false,
    };
  
    return (
      <div key={uniqueKey} className="chart-container">
        <Plot
          data={dataTraces}
          layout={layout}
          useResizeHandler={true}
          className="trending-chart"
          config={config}
        />
      </div>
    );
  };
  
  const handleUploadClick = () => {
    navigate('/upload');
  };

  return (
    <div className="home-container">
      <div className="chart-section">
        {loading && <div className="loading">Loading trending data...</div>}
        {error && <div className="error">{error}</div>}
        {!loading && !error && chartsData.length > 0 && chartsData.map(chart => renderChart(chart))}
        {!loading && !error && chartsData.length === 0 && <div>No trending data available.</div>}
      </div>
      
      <button className="upload-button" onClick={handleUploadClick}>
        <FaUpload className="upload-icon" />
        Upload New Report
      </button>
    </div>
  );
};

export default HomeScreen;