import React, { useState } from 'react'
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

function App() {
  const [step, setStep] = useState('upload') // upload, select, review, export
  const [sessionId, setSessionId] = useState(null)
  const [fileInfo, setFileInfo] = useState(null)
  const [selectedColumns, setSelectedColumns] = useState([])
  const [threshold, setThreshold] = useState(0.85)
  const [duplicateGroups, setDuplicateGroups] = useState([])
  const [reviewedDuplicates, setReviewedDuplicates] = useState({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleFileUpload = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    setLoading(true)
    setError(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setFileInfo(response.data)
      setSessionId(response.data.session_id)
      setStep('select')
    } catch (err) {
      setError(err.response?.data?.detail || 'Error uploading file')
    } finally {
      setLoading(false)
    }
  }

  const handleColumnToggle = (column) => {
    setSelectedColumns(prev =>
      prev.includes(column)
        ? prev.filter(c => c !== column)
        : [...prev, column]
    )
  }

  const handleAnalyze = async () => {
    if (selectedColumns.length === 0) {
      setError('Please select at least one column')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await axios.post(`${API_BASE_URL}/analyze`, {
        session_id: sessionId,
        columns: selectedColumns,
        similarity_threshold: threshold
      })
      setDuplicateGroups(response.data.groups)
      setStep('review')
    } catch (err) {
      setError(err.response?.data?.detail || 'Error analyzing duplicates')
    } finally {
      setLoading(false)
    }
  }

  const handleReview = async (duplicateId, isDuplicate) => {
    try {
      await axios.post(`${API_BASE_URL}/review`, {
        session_id: sessionId,
        duplicate_id: duplicateId,
        is_duplicate: isDuplicate
      })
      setReviewedDuplicates(prev => ({
        ...prev,
        [duplicateId]: isDuplicate
      }))
    } catch (err) {
      setError(err.response?.data?.detail || 'Error reviewing duplicate')
    }
  }

  const handleExport = async () => {
    setLoading(true)
    try {
      const response = await axios.get(`${API_BASE_URL}/export/${sessionId}`, {
        responseType: 'blob'
      })

      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `duplicate_report_${Date.now()}.xlsx`)
      document.body.appendChild(link)
      link.click()
      link.remove()

      setStep('export')
    } catch (err) {
      setError(err.response?.data?.detail || 'Error exporting report')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setStep('upload')
    setSessionId(null)
    setFileInfo(null)
    setSelectedColumns([])
    setThreshold(0.85)
    setDuplicateGroups([])
    setReviewedDuplicates({})
    setError(null)
  }

  const reviewedCount = Object.keys(reviewedDuplicates).length
  const totalGroups = duplicateGroups.length
  const progressPercentage = totalGroups > 0 ? (reviewedCount / totalGroups) * 100 : 0

  return (
    <div className="app-container">
      <header className="header">
        <h1>DSS-TRACK: AI/NLP-powered Semantic Duplicate Detection</h1>
        <p>Upload your data, generate semantic embeddings via transformer encoding, identify duplicates using cosine similarity, and export a clean report</p>
      </header>

      {error && (
        <div className="card">
          <div className="error">
            <strong>Error:</strong> {error}
          </div>
        </div>
      )}

      {/* Upload Step */}
      {step === 'upload' && (
        <div className="card upload-section">
          <h2>Step 1: Upload Your File</h2>
          <p>Upload a CSV or Excel file to begin duplicate detection</p>

          <div className="file-input-wrapper">
            <input
              type="file"
              id="file-input"
              accept=".csv,.xlsx,.xls"
              onChange={handleFileUpload}
              disabled={loading}
            />
            <label htmlFor="file-input" className="file-input-label">
              {loading ? 'Uploading...' : 'Choose File'}
            </label>
          </div>

          {loading && (
            <div className="loading">
              <div className="loading-spinner"></div>
              <p>Processing your file...</p>
            </div>
          )}
        </div>
      )}

      {/* Column Selection Step */}
      {step === 'select' && fileInfo && (
        <div className="card">
          <h2>Step 2: Select Columns for Analysis</h2>
          <p>Choose which columns should be compared for semantic similarity</p>

          <div className="stats-summary">
            <div className="stat-card">
              <div className="stat-value">{fileInfo.rows}</div>
              <div className="stat-label">Total Rows</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{fileInfo.columns.length}</div>
              <div className="stat-label">Total Columns</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{selectedColumns.length}</div>
              <div className="stat-label">Selected Columns</div>
            </div>
          </div>

          <div className="column-selection">
            <h3>Available Columns:</h3>
            <div className="column-list">
              {fileInfo.columns.map(column => (
                <div key={column} className="column-item" onClick={() => handleColumnToggle(column)}>
                  <input
                    type="checkbox"
                    checked={selectedColumns.includes(column)}
                    onChange={() => {}}
                  />
                  <span>{column}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="threshold-input">
            <label>
              Similarity Threshold:
              <span className="threshold-value">{(threshold * 100).toFixed(0)}%</span>
            </label>
            <input
              type="range"
              min="0.5"
              max="0.99"
              step="0.01"
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
            />
            <p style={{ fontSize: '0.9rem', color: '#6b7280', marginTop: '10px' }}>
              Higher threshold = stricter matching.
            </p>
          </div>

          <h3>Data Preview:</h3>
          <div style={{ overflowX: 'auto' }}>
            <table className="preview-table">
              <thead>
                <tr>
                  {fileInfo.columns.map(col => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {fileInfo.preview.map((row, idx) => (
                  <tr key={idx}>
                    {fileInfo.columns.map(col => (
                      <td key={col}>{String(row[col] || '')}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ textAlign: 'center', marginTop: '20px' }}>
            <button
              className="btn btn-primary"
              onClick={handleAnalyze}
              disabled={selectedColumns.length === 0 || loading}
            >
              {loading ? 'Analyzing...' : 'Analyze for Duplicates'}
            </button>
          </div>

          {loading && (
            <div className="loading">
              <div className="loading-spinner"></div>
              <p>Analyzing semantic similarity... This may take a moment.</p>
            </div>
          )}
        </div>
      )}

      {/* Review Step */}
      {step === 'review' && (
        <div className="card">
          <h2>Step 3: Review Potential Duplicates</h2>
          <p>Mark each group as true duplicates or false positives</p>

          <div className="stats-summary">
            <div className="stat-card">
              <div className="stat-value">{totalGroups}</div>
              <div className="stat-label">Duplicate Groups</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{reviewedCount}</div>
              <div className="stat-label">Reviewed</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{totalGroups - reviewedCount}</div>
              <div className="stat-label">Pending</div>
            </div>
          </div>

          {totalGroups > 0 && (
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${progressPercentage}%` }}>
                {progressPercentage.toFixed(0)}%
              </div>
            </div>
          )}

          {duplicateGroups.length === 0 ? (
            <div className="success">
              <strong>No duplicates found!</strong> Your data appears to be clean.
            </div>
          ) : (
            <div className="duplicate-groups">
              {duplicateGroups.map((group, groupIdx) => (
                <div
                  key={group.duplicate_id}
                  className={`duplicate-group ${
                    reviewedDuplicates[group.duplicate_id] === true
                      ? 'reviewed-true'
                      : reviewedDuplicates[group.duplicate_id] === false
                      ? 'reviewed-false'
                      : ''
                  }`}
                >
                  <div className="duplicate-group-header">
                    <div className="duplicate-group-title">
                      Group {groupIdx + 1} ({group.rows.length} rows)
                    </div>
                    <div>
                      <button
                        className="btn btn-success"
                        onClick={() => handleReview(group.duplicate_id, true)}
                        disabled={reviewedDuplicates[group.duplicate_id] === true}
                      >
                        ✓ True Duplicate
                      </button>
                      <button
                        className="btn btn-danger"
                        onClick={() => handleReview(group.duplicate_id, false)}
                        disabled={reviewedDuplicates[group.duplicate_id] === false}
                      >
                        ✗ False Positive
                      </button>
                    </div>
                  </div>

                  {group.rows.map((row, rowIdx) => (
                    <div key={rowIdx} className="duplicate-row">
                      <div className="duplicate-row-header">
                        Row {row.original_index + 1}
                      </div>
                      <div className="duplicate-row-content">
                        {selectedColumns.map(col => (
                          <div key={col}>
                            <strong>{col}:</strong> {String(row[col] || '')}
                          </div>
                        ))}
                      </div>
                      {Object.keys(row.similarity_scores).length > 0 && (
                        <div className="similarity-scores">
                          <strong>Similarity scores:</strong>{' '}
                          {Object.entries(row.similarity_scores).map(([idx, score]) => (
                            <span key={idx} className="similarity-score">
                              Row {parseInt(idx) + 1}: {(score * 100).toFixed(1)}%
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}

          <div style={{ textAlign: 'center', marginTop: '30px' }}>
            <button
              className="btn btn-secondary"
              onClick={() => setStep('select')}
            >
              ← Back to Column Selection
            </button>
            <button
              className="btn btn-primary"
              onClick={handleExport}
              disabled={loading}
            >
              {loading ? 'Generating Report...' : 'Export Report →'}
            </button>
          </div>
        </div>
      )}

      {/* Export Step */}
      {step === 'export' && (
        <div className="card export-section">
          <h2>✓ Report Generated Successfully!</h2>
          <p style={{ marginBottom: '20px' }}>
            Your multi-sheet Excel report has been downloaded and includes:
          </p>
          <ul style={{ textAlign: 'left', maxWidth: '600px', margin: '0 auto 30px' }}>
            <li>Original data</li>
            <li>De-duplicated data</li>
            <li>Duplicate records with group mappings</li>
            <li>Statistical analysis and summary</li>
          </ul>

          <button className="btn btn-primary" onClick={handleReset}>
            Analyze Another File
          </button>
        </div>
      )}
    </div>
  )
}

export default App
