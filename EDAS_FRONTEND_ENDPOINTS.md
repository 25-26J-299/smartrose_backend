# EDAS Frontend Endpoints Documentation

## ✅ **New Endpoints for Disease Detection Card**

**Status:** ✅ **IMPLEMENTED**  
**Date:** January 6, 2026  
**Purpose:** Provide EDAS data endpoints matching frontend expectations

---

## 📋 **Available Endpoints**

### **Base URL:** `/api/v1/edas-data/`

All endpoints follow the same pattern as other components (eosm-data, inm, fm) for consistency.

---

## 🎯 **Main Endpoints**

### **1. GET `/api/v1/edas-data/latest-with-prediction`**

**Purpose:** Get latest sensor data with disease risk analysis for the disease detection card

**Query Parameters:**
- `device_id` (optional): Filter by specific device/zone

**Response:**
```json
{
  "status": "success",
  "message": "Latest EDAS data with disease prediction retrieved successfully",
  "data": {
    "sensor_data": {
      "_id": "695c053ce6b12ddca7cf4b35",
      "device_id": "edas_zone1",
      "plant_temperature": 29.63,
      "air_temperature": 29.83,
      "humidity": 81.71,
      "temperature_difference": -0.20,
      "timestamp": "2026-01-06T23:45:00+05:30",  // Sri Lankan local time
      "hour": 23,
      "is_day": false,
      "time_period": "night"
    },
    "prediction": {
      "disease_risk_level": "high",  // "low", "medium", "high"
      "risk_score": 85,  // 0-100
      "confidence": 0.85,
      "alerts": [
        "High fungal disease risk detected (nighttime + high humidity)"
      ],
      "recommendations": [
        "Consider improving ventilation overnight",
        "Monitor for early signs of powdery mildew or botrytis"
      ],
      "analysis_time": "2026-01-06T23:45:00+05:30",
      "time_context": {
        "is_day": false,
        "time_period": "night",
        "hour": 23
      }
    },
    "key_metrics": {
      "plant_temperature": 29.63,
      "air_temperature": 29.83,
      "humidity": 81.71,
      "temperature_difference": -0.20
    }
  }
}
```

**Disease Risk Levels:**
- **`low`** (score 0-40): Normal conditions, continue monitoring
- **`medium`** (score 41-70): Potential stress detected, increased attention needed
- **`high`** (score 71-100): High disease risk, immediate action recommended

---

### **2. GET `/api/v1/edas-data/?limit=120`**

**Purpose:** Get list of EDAS sensor data for history/charts

**Query Parameters:**
- `limit` (default: 120, max: 2000): Number of records to return
- `skip` (default: 0): Pagination offset
- `device_id` (optional): Filter by device

**Response:**
```json
{
  "status": "success",
  "message": "EDAS sensor data retrieved successfully",
  "data": {
    "count": 120,
    "items": [
      {
        "_id": "695c053ce6b12ddca7cf4b35",
        "device_id": "edas_zone1",
        "plant_temperature": 29.63,
        "air_temperature": 29.83,
        "humidity": 81.71,
        "temperature_difference": -0.20,
        "timestamp": "2026-01-06T23:45:00+05:30",
        "hour": 23,
        "is_day": false,
        "time_period": "night"
      },
      // ... more records (most recent first)
    ]
  }
}
```

---

### **3. POST `/api/v1/edas-data/`**

**Purpose:** Ingest sensor data from IoT device (same as existing endpoint)

**Request Body:**
```json
{
  "device_id": "edas_zone1",
  "plant_temperature": 29.63,
  "air_temperature": 29.83,
  "humidity": 81.71
}
```

**Response:**
```json
{
  "status": "success",
  "message": "EDAS sensor data ingested successfully",
  "data": {
    "id": "695c053ce6b12ddca7cf4b35",
    "temperature_difference": -0.20
  }
}
```

---

## 🎨 **Disease Detection Card UI Implementation**

### **React Example:**

```jsx
import React, { useEffect, useState } from 'react';

const DiseaseDetectionCard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch('/api/v1/edas-data/latest-with-prediction');
        const result = await response.json();
        setData(result.data);
      } catch (error) {
        console.error('Error fetching EDAS data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    // Refresh every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div>Loading...</div>;
  if (!data) return <div>No data available</div>;

  const { sensor_data, prediction, key_metrics } = data;

  // Risk level colors
  const riskColors = {
    low: 'green',
    medium: 'orange',
    high: 'red'
  };

  return (
    <div className="disease-detection-card">
      <h3>Disease Risk Assessment</h3>
      
      {/* Risk Level Indicator */}
      <div className={`risk-badge ${prediction.disease_risk_level}`}
           style={{ backgroundColor: riskColors[prediction.disease_risk_level] }}>
        Risk Level: {prediction.disease_risk_level.toUpperCase()}
        <div className="risk-score">Score: {prediction.risk_score}/100</div>
      </div>

      {/* Key Metrics */}
      <div className="metrics">
        <div className="metric">
          <span>Plant Temp:</span>
          <strong>{key_metrics.plant_temperature}°C</strong>
        </div>
        <div className="metric">
          <span>Air Temp:</span>
          <strong>{key_metrics.air_temperature}°C</strong>
        </div>
        <div className="metric">
          <span>Humidity:</span>
          <strong>{key_metrics.humidity}%</strong>
        </div>
        <div className="metric">
          <span>Temp Diff:</span>
          <strong>{key_metrics.temperature_difference}°C</strong>
        </div>
      </div>

      {/* Time Context */}
      <div className="time-info">
        <span>Time: {new Date(sensor_data.timestamp).toLocaleString()}</span>
        <span>Period: {sensor_data.time_period}</span>
        <span>{sensor_data.is_day ? '☀️ Day' : '🌙 Night'}</span>
      </div>

      {/* Alerts */}
      {prediction.alerts.length > 0 && (
        <div className="alerts">
          <h4>⚠️ Alerts:</h4>
          <ul>
            {prediction.alerts.map((alert, index) => (
              <li key={index}>{alert}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Recommendations */}
      {prediction.recommendations.length > 0 && (
        <div className="recommendations">
          <h4>💡 Recommendations:</h4>
          <ul>
            {prediction.recommendations.map((rec, index) => (
              <li key={index}>{rec}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default DiseaseDetectionCard;
```

---

## 📊 **Disease Risk Rules (Current Implementation)**

### **High Risk (Score 71-100):**
1. **Night + High Humidity (>75%)**
   - Fungal disease risk
   - Recommendations: Improve ventilation, monitor for mildew

### **Medium Risk (Score 41-70):**
1. **Large Temperature Difference (>3°C)**
   - Heat stress or plant health issue
   - Recommendations: Check irrigation, inspect plants

2. **Day + High Temp (>30°C) + High Humidity (>70%)**
   - Stress conditions
   - Recommendations: Increase ventilation, ensure shading

### **Low Risk (Score 0-40):**
- Normal environmental conditions
- Continue regular monitoring

---

## 🧪 **Testing the Endpoints**

### **Test 1: Get Latest with Prediction**

```bash
# PowerShell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/edas-data/latest-with-prediction" | 
    Select-Object -ExpandProperty Content | 
    ConvertFrom-Json | 
    ConvertTo-Json -Depth 10
```

### **Test 2: Get Data List**

```bash
# PowerShell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/edas-data/?limit=10" | 
    Select-Object -ExpandProperty Content
```

### **Test 3: Check Specific Device**

```bash
# PowerShell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/edas-data/latest-with-prediction?device_id=edas_zone1" | 
    Select-Object -ExpandProperty Content
```

---

## 🔄 **Auto-refresh Pattern**

For real-time disease detection card updates:

```javascript
// Fetch data every 30 seconds
const REFRESH_INTERVAL = 30000; // 30 seconds

const useDiseaseDetection = () => {
  const [data, setData] = useState(null);
  
  useEffect(() => {
    const fetchData = async () => {
      const response = await fetch('/api/v1/edas-data/latest-with-prediction');
      const result = await response.json();
      setData(result.data);
    };
    
    fetchData(); // Initial fetch
    const interval = setInterval(fetchData, REFRESH_INTERVAL);
    
    return () => clearInterval(interval);
  }, []);
  
  return data;
};
```

---

## 📝 **Response Format Consistency**

All responses follow the standard format:

```json
{
  "status": "success",
  "message": "Descriptive message",
  "data": {
    // Actual data here
  }
}
```

**Error Response:**
```json
{
  "detail": "Error message"
}
```

---

## 🎯 **Key Features**

✅ **Real-time disease risk assessment**  
✅ **Rule-based analysis** (ready for ML model upgrade)  
✅ **Time-aware predictions** (uses hour, is_day, time_period)  
✅ **Actionable recommendations**  
✅ **Alert system**  
✅ **Sri Lankan local time display**  
✅ **Consistent with other components**  

---

## 🔮 **Future ML Integration**

When the ML model is trained, replace the rule-based logic in `get_latest_with_prediction()`:

```python
# Current: Rule-based
risk_level = "high" if (not is_day and humidity > 75) else "low"

# Future: ML Model
from app.ml.edas.edas_inference import predict_disease_risk
prediction = predict_disease_risk({
    "plant_temperature": plant_temp,
    "air_temperature": air_temp,
    "humidity": humidity,
    "temperature_difference": temp_diff,
    "hour": hour,
    "is_day": is_day,
    "time_period": time_period
})
risk_level = prediction["risk_level"]
risk_score = prediction["risk_score"]
```

---

## ✅ **Summary**

| Endpoint | Purpose | Frontend Use |
|----------|---------|--------------|
| `GET /latest-with-prediction` | Disease detection card | Main dashboard card |
| `GET /?limit=120` | Historical data | Charts, history view |
| `POST /` | IoT data ingestion | ESP32 devices |

**All endpoints are now live and ready for your disease detection card! 🌹🔍**

---

**Implementation Status:** ✅ **COMPLETE & TESTED**  
**Frontend Integration:** ✅ **READY**  
**Documentation:** ✅ **COMPLETE**



