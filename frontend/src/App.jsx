import React, { useState, useEffect } from 'react';

function App() {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Default to empty string so the backend auto-calculates the current Friday on initial load
  const [selectedFriday, setSelectedFriday] = useState('');

  useEffect(() => {
    setLoading(true);
    // Append the end_date query parameter to the API request
    const url = selectedFriday 
      ? `http://localhost:8000/api/reports?end_date=${selectedFriday}`
      : 'http://localhost:8000/api/reports';

    fetch(url)
      .then(response => {
        if (!response.ok) throw new Error('Failed to retrieve reports for this timeframe.');
        return response.json();
      })
      .then(data => {
        setReports(data.reports || []);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [selectedFriday]); // Re-run effect whenever selectedFriday changes

  const handleDateChange = (e) => {
    const dateStr = e.target.value; // Format: YYYY-MM-DD
    if (!dateStr) return;

    const dateObj = new Date(dateStr);
    // day index: 0 = Sunday, 5 = Friday
    if (dateObj.getDay() !== 5) {
      alert("Please select a Friday. Reports run on a weekly timeframe ending on Fridays.");
      return;
    }
    
    setSelectedFriday(dateStr);
  };

  return (
    <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
      
      {/* Control Panel Section */}
      <div style={styles.controlPanel}>
        <label htmlFor="friday-picker" style={{ marginRight: '10px', fontWeight: 'bold' }}>
          Select History Week (Ends on Friday): 
        </label>
        <input 
          type="date" 
          id="friday-picker" 
          value={selectedFriday} 
          onChange={handleDateChange}
          style={styles.dateInput}
        />
        {selectedFriday && (
          <button 
            onClick={() => setSelectedFriday('')} 
            style={styles.resetButton}
          >
            Clear Filter (Show Current Week)
          </button>
        )}
      </div>

      {loading && <h2 style={{ color: '#666' }}>Generating Reports... Processing image paths and database queries...</h2>}
      {error && <h2 style={{ color: 'red' }}>Error: {error}</h2>}
      
      {!loading && reports.length === 0 && (
        <h2>No image folder matches found for the week ending {selectedFriday || 'this Friday'}.</h2>
      )}

      {/* Report Render Section */}
      {!loading && reports.map((report) => (
        <div key={report.ProgramCode} style={{ marginBottom: '50px' }}>
          <h1 style={styles.title}>
            {report.ProgramName} Visibility Program Detail - {report.TimeFrame}
          </h1>
          
          <table style={styles.table}>
            <thead>
              <tr style={{ backgroundColor: '#f2f2f2' }}>
                <th style={styles.thtd}>SaleMan</th>
                <th style={styles.thtd}>RouteCode</th>
                <th style={styles.thtd}>SM_Name</th>
                <th style={styles.thtd}>SuperEcode</th>
                <th style={styles.thtd}>SuperName</th>
                <th style={styles.thtd}>CusCode</th>
                <th style={styles.thtd}>CusName</th>
                <th style={styles.thtd}>Display Images</th>
              </tr>
            </thead>
            <tbody>
              {report.Details.map((row, index) => (
                <tr key={index}>
                  <td style={styles.thtd}>{row.SaleMan}</td>
                  <td style={styles.thtd}>{row.RouteCode}</td>
                  <td style={styles.thtd}>{row.SM_Name}</td>
                  <td style={styles.thtd}>{row.SuperEcode}</td>
                  <td style={styles.thtd}>{row.SuperName}</td>
                  <td style={styles.thtd}>{row.CusCode}</td>
                  <td style={styles.thtd}>{row.CusName}</td>
                  <td style={styles.thtd}>
                    <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                      {row.DisplayImages.map((imgUrl, imgIndex) => (
                        <img 
                          key={imgIndex} 
                          src={imgUrl} 
                          alt="Merchandise" 
                          height="120" 
                          width="120"
                          style={{ border: '1px solid #ddd', borderRadius: '4px' }}
                        />
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

const styles = {
  controlPanel: {
    backgroundColor: '#f8f9fa',
    padding: '15px',
    borderRadius: '6px',
    marginBottom: '25px',
    border: '1px solid #e9ecef',
    display: 'flex',
    alignItems: 'center'
  },
  dateInput: {
    padding: '8px',
    borderRadius: '4px',
    border: '1px solid #ced4da',
    fontSize: '14px'
  },
  resetButton: {
    marginLeft: '15px',
    padding: '8px 12px',
    backgroundColor: '#6c757d',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer'
  },
  title: {
    fontSize: '22px',
    color: '#212529',
    borderBottom: '2px solid #dee2e6',
    paddingBottom: '8px',
    marginBottom: '15px'
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    marginBottom: '20px'
  },
  thtd: {
    border: '1px solid #111',
    padding: '10px',
    textAlign: 'left',
    fontSize: '14px'
  }
};

export default App;