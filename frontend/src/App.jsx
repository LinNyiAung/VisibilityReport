import React, { useState, useEffect } from 'react';

const API_BASE = 'http://logcalculator.pahtama.com:4000';

const PROGRAM_MAP = {
  "51": "Hair Care-Bottle",
  "52": "Oral Care",
  "53": "Fabric Care",
  "54": "Blade & razor",
  "55": "Home Care",
  "57": "Medical Nutrition",
  "58": "Pediatric Nutrition",
  "59": "Nutrition Supplement",
  "60": "Beverage",
  "62": "Cake & Pie",
  "63": "Instant Noodle Any",
  "64": "Cereal",
  "65": "Potato Chip",
  "66": "Biscuit & Cookies",
  "67": "Sugar Supplement",
  "68": "Cooking Oil",
  "69": "Snack",
  "70": "Cake Rusk",
  "71": "Ready to Eat (Balachaung)",
  "72": "Coffee",
  "74": "Condiment",
  "75": "Process Food",
  "77": "Pickled Tea and Related Item",
  "86": "Preserve Fruit",
  "87": "Butter & Spreads",
  "88": "Ice Cream",
  "89": "May Yee Mon Visibility Program",
  "90": "Ovaltine Visibility Program",
  "91": "MYM Congee visibility program"
};

function App() {
  const [periods, setPeriods] = useState({ daily: [], weekly: [], monthly: [] });
  const [periodsLoading, setPeriodsLoading] = useState(true);
  const [periodsError, setPeriodsError] = useState(null);

  const [activeTab, setActiveTab] = useState('daily'); // 'daily' | 'weekly' | 'monthly'
  const [selectedPeriod, setSelectedPeriod] = useState(null); // { type, ...params, label }

  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [selectedProgram, setSelectedProgram] = useState('All');
  
  // State to toggle between Detail and Summary report types
  const [reportType, setReportType] = useState('Detail'); // 'Detail' | 'Summary'

  // 1. Load the available Daily / Weekly / Monthly lists on mount
  useEffect(() => {
    setPeriodsLoading(true);
    fetch(`${API_BASE}/api/periods`)
      .then((response) => {
        if (!response.ok) throw new Error('Failed to load available report periods.');
        return response.json();
      })
      .then((data) => {
        const loadedPeriods = {
          daily: data.daily || [],
          weekly: data.weekly || [],
          monthly: data.monthly || [],
        };
        setPeriods(loadedPeriods);
        setPeriodsLoading(false);

        // Default to the latest available daily period
        if (loadedPeriods.daily.length > 0) {
          const mostRecent = loadedPeriods.daily[0];
          setSelectedPeriod({ type: 'daily', date: mostRecent.date, label: mostRecent.label });
        }
      })
      .catch((err) => {
        setPeriodsError(err.message);
        setPeriodsLoading(false);
      });
  }, []);

  // 2. Whenever the selected period changes, fetch its report
  useEffect(() => {
    if (!selectedPeriod) return;

    setLoading(true);
    setError(null);
    setSelectedProgram('All'); // Reset filter when changing periods

    const params = new URLSearchParams();
    params.set('period_type', selectedPeriod.type);
    if (selectedPeriod.type === 'daily') {
      params.set('date', selectedPeriod.date);
    } else if (selectedPeriod.type === 'weekly') {
      params.set('end_date', selectedPeriod.end_date);
    } else if (selectedPeriod.type === 'monthly') {
      params.set('year', selectedPeriod.year);
      params.set('month', selectedPeriod.month);
    }

    fetch(`${API_BASE}/api/reports?${params.toString()}`)
      .then((response) => {
        if (!response.ok) throw new Error('Failed to retrieve reports for this period.');
        return response.json();
      })
      .then((data) => {
        if (data.error) throw new Error(data.error);
        setReports(data.reports || []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [selectedPeriod]);

  const handleSelectPeriod = (type, item) => {
    if (type === 'daily') {
      setSelectedPeriod({ type, date: item.date, label: item.label });
    } else if (type === 'weekly') {
      setSelectedPeriod({ type, end_date: item.end_date, label: item.label });
    } else if (type === 'monthly') {
      setSelectedPeriod({ type, year: item.year, month: item.month, label: item.label });
    }
  };

  const isSelected = (type, item) => {
    if (!selectedPeriod || selectedPeriod.type !== type) return false;
    if (type === 'daily') return selectedPeriod.date === item.date;
    if (type === 'weekly') return selectedPeriod.end_date === item.end_date;
    if (type === 'monthly') return selectedPeriod.year === item.year && selectedPeriod.month === item.month;
    return false;
  };

  const tabs = [
    { key: 'daily', label: 'Daily' },
    { key: 'weekly', label: 'Weekly' },
    { key: 'monthly', label: 'Monthly' },
  ];

  const activeList = periods[activeTab] || [];

  const filteredReports = reports.filter((report) => {
    if (selectedProgram === 'All') return true;
    return report.ProgramCode === selectedProgram;
  });

  return (
    <div style={{ padding: '20px', fontFamily: 'sans-serif', display: 'flex', gap: '16px' }}>

      {/* Sidebar: Daily / Weekly / Monthly period browser */}
      <div style={styles.sidebar}>
        <div style={styles.tabRow}>
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              style={activeTab === tab.key ? styles.tabButtonActive : styles.tabButton}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {periodsLoading && <p style={{ color: '#666', padding: '10px' }}>Loading periods...</p>}
        {periodsError && <p style={{ color: 'red', padding: '10px' }}>Error: {periodsError}</p>}

        {!periodsLoading && !periodsError && activeList.length === 0 && (
          <p style={{ color: '#666', padding: '10px' }}>No {activeTab} periods available.</p>
        )}

        {!periodsLoading && !periodsError && (
          <ul style={styles.periodList}>
            {activeList.map((item, idx) => (
              <li key={idx}>
                <button
                  onClick={() => handleSelectPeriod(activeTab, item)}
                  style={isSelected(activeTab, item) ? styles.periodItemActive : styles.periodItem}
                >
                  {item.label}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Main content: selected report */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {!selectedPeriod && (
          <h2 style={{ color: '#666' }}>Select a Daily, Weekly, or Monthly period from the list to view its report.</h2>
        )}

        {selectedPeriod && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h3 style={{ color: '#444', margin: 0 }}>
              Showing {activeTabLabel(selectedPeriod.type)} report: {selectedPeriod.label}
            </h3>
            
            {!loading && !error && reports.length > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                
                {/* Report Type Toggle */}
                <div style={styles.toggleGroup}>
                  <button 
                    style={reportType === 'Detail' ? styles.toggleActive : styles.toggleInactive}
                    onClick={() => setReportType('Detail')}
                  >
                    Detail
                  </button>
                  <button 
                    style={reportType === 'Summary' ? styles.toggleActive : styles.toggleInactive}
                    onClick={() => setReportType('Summary')}
                  >
                    Summary
                  </button>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <label style={{ fontWeight: 'bold', color: '#444' }}>Filter by Program:</label>
                  <select
                    value={selectedProgram}
                    onChange={(e) => setSelectedProgram(e.target.value)}
                    style={styles.selectInput}
                  >
                    <option value="All">All Programs</option>
                    {Object.entries(PROGRAM_MAP).map(([code, name]) => (
                      <option key={code} value={code}>
                        {name} ({code})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}
          </div>
        )}

        {loading && <h2 style={{ color: '#666' }}>Generating Reports... Processing image paths and database queries...</h2>}
        {error && <h2 style={{ color: 'red' }}>Error: {error}</h2>}

        {!loading && !error && selectedPeriod && reports.length === 0 && (
          <h2>No image folder matches found for {selectedPeriod.label}.</h2>
        )}
        
        {!loading && reports.length > 0 && filteredReports.length === 0 && (
          <h3 style={{ color: '#666' }}>No data found for the selected program in this period.</h3>
        )}

        {/* Report Render Section */}
        {!loading && filteredReports.map((report) => (
          <div key={report.ProgramCode} style={{ marginBottom: '50px' }}>
            <h1 style={styles.title}>
              {report.ProgramName} Visibility Program {reportType} - {report.TimeFrame}
            </h1>

            <div style={styles.tableWrapper}>
              <table style={styles.table}>
                <colgroup>
                  <col style={{ width: '8%' }} />
                  <col style={{ width: '8%' }} />
                  <col style={{ width: '10%' }} />
                  <col style={{ width: '8%' }} />
                  <col style={{ width: '10%' }} />
                  <col style={{ width: '8%' }} />
                  <col style={{ width: '10%' }} />
                  <col style={{ width: reportType === 'Detail' ? '38%' : '15%' }} />
                </colgroup>
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
                      
                      {/* CONDITIONAL RENDER: Images (Detail) vs Text Status (Summary) */}
                      <td style={styles.thtd}>
                        {reportType === 'Detail' ? (
                          <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                            {row.DisplayImages.map((imgUrl, imgIndex) => (
                              <img
                                key={imgIndex}
                                src={imgUrl}
                                alt="Merchandise"
                                height="130"
                                width="130"
                                style={{ border: '1px solid #ddd', borderRadius: '4px' }}
                              />
                            ))}
                          </div>
                        ) : (
                          <div style={{ textAlign: 'center' }}>
                            <div>{report.ProgramName} visibility</div>
                            <hr style={{ borderTop: '1px solid #ddd', margin: '8px 0' }}/>
                            <div style={{ fontWeight: 'bold' }}>{row.Active}</div>
                          </div>
                        )}
                      </td>

                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function activeTabLabel(type) {
  if (type === 'daily') return 'Daily';
  if (type === 'weekly') return 'Weekly';
  if (type === 'monthly') return 'Monthly';
  return '';
}

const styles = {
  sidebar: {
    width: '160px',
    flexShrink: 0,
    backgroundColor: '#f8f9fa',
    border: '1px solid #e9ecef',
    borderRadius: '6px',
    padding: '10px',
    alignSelf: 'flex-start',
  },
  tabRow: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    marginBottom: '12px',
  },
  tabButton: {
    width: '100%',
    padding: '8px 6px',
    fontSize: '13px',
    border: '1px solid #ced4da',
    borderRadius: '4px',
    backgroundColor: '#fff',
    cursor: 'pointer',
  },
  tabButtonActive: {
    width: '100%',
    padding: '8px 6px',
    fontSize: '13px',
    border: '1px solid #495057',
    borderRadius: '4px',
    backgroundColor: '#495057',
    color: '#fff',
    cursor: 'pointer',
    fontWeight: 'bold',
  },
  periodList: {
    listStyle: 'none',
    margin: 0,
    padding: 0,
    maxHeight: '70vh',
    overflowY: 'auto',
  },
  periodItem: {
    display: 'block',
    width: '100%',
    textAlign: 'left',
    padding: '8px 8px',
    marginBottom: '4px',
    fontSize: '13px',
    border: '1px solid transparent',
    borderRadius: '4px',
    backgroundColor: 'transparent',
    cursor: 'pointer',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  periodItemActive: {
    display: 'block',
    width: '100%',
    textAlign: 'left',
    padding: '8px 8px',
    marginBottom: '4px',
    fontSize: '13px',
    border: '1px solid #0d6efd',
    borderRadius: '4px',
    backgroundColor: '#e7f1ff',
    color: '#0d6efd',
    cursor: 'pointer',
    fontWeight: 'bold',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  title: {
    fontSize: '22px',
    color: '#212529',
    borderBottom: '2px solid #dee2e6',
    paddingBottom: '8px',
    marginBottom: '15px'
  },
  tableWrapper: {
    width: '100%',
  },
  table: {
    width: '100%',
    tableLayout: 'fixed',
    borderCollapse: 'collapse',
    marginBottom: '20px'
  },
  thtd: {
    border: '1px solid #111',
    padding: '10px 8px',
    textAlign: 'left',
    fontSize: '13px',
    wordWrap: 'break-word',
    overflowWrap: 'break-word',
  },
  selectInput: {
    padding: '6px 12px',
    fontSize: '14px',
    borderRadius: '4px',
    border: '1px solid #ced4da',
    backgroundColor: '#fff',
    cursor: 'pointer',
    minWidth: '200px'
  },
  toggleGroup: {
    display: 'flex',
    borderRadius: '4px',
    overflow: 'hidden',
    border: '1px solid #ced4da'
  },
  toggleActive: {
    backgroundColor: '#0d6efd',
    color: '#fff',
    border: 'none',
    padding: '6px 12px',
    cursor: 'pointer',
    fontWeight: 'bold'
  },
  toggleInactive: {
    backgroundColor: '#f8f9fa',
    color: '#495057',
    border: 'none',
    padding: '6px 12px',
    cursor: 'pointer'
  }
};

export default App;