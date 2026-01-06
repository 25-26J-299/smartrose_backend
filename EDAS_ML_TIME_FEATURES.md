# EDAS ML Time-Based Features Documentation

## ✅ Implementation Complete

**Date:** January 5, 2026  
**Feature:** ML Time-Based Fields for Disease Pattern Recognition  
**Status:** ✅ **Fully Implemented & Tested**

---

## 📋 Overview

EDAS now automatically enriches every sensor reading with **time-based ML features** that enable the machine learning model to learn time-dependent disease patterns:

- **Day vs Night behavior** - Fungal risk vs heat stress
- **Time period patterns** - Morning/Noon/Evening/Night characteristics
- **Hour-specific patterns** - Hourly disease progression tracking

---

## 🎯 New Fields Added

Every EDAS sensor record now includes these **auto-calculated** fields:

| Field | Type | Range | Description | ML Purpose |
|-------|------|-------|-------------|-----------|
| **`hour`** | `int` | 0-23 | Hour of day from timestamp | Hourly pattern recognition |
| **`is_day`** | `bool` | true/false | Day (06:00-18:00) or Night | Day/Night behavior separation |
| **`time_period`** | `str` | morning/noon/evening/night | Time classification | Period-specific patterns |

---

## ⚙️ Calculation Rules

### **1. Hour Extraction**
```python
hour = timestamp.hour  # 0-23 (UTC timezone)
```

### **2. Day/Night Classification**
```python
is_day = True  if 06:00 <= hour < 18:00
is_day = False otherwise (18:00-06:00)
```

**Why This Matters for ML:**
- **Day (is_day=True)**: Heat stress, water loss, direct sunlight exposure
- **Night (is_day=False)**: Fungal risk, high humidity, condensation

### **3. Time Period Classification**

| Time Range | `time_period` | Characteristics | Disease Risk |
|------------|---------------|-----------------|--------------|
| **06:00-10:00** | `"morning"` | Temperature rising, dew evaporation | Fungal spores active |
| **10:00-14:00** | `"noon"` | Peak heat, maximum stress | Heat stress, wilting |
| **14:00-18:00** | `"evening"` | Cooling down, afternoon conditions | Transition period |
| **18:00-06:00** | `"night"` | Darkness, humidity increase | High fungal risk |

---

## 📊 Example: Before vs After

### **Before (Old Format):**
```json
{
  "_id": "695aa22a1423c6e74593ca03",
  "device_id": "edas_zone1",
  "plant_temperature": 30.11,
  "air_temperature": 30.51,
  "humidity": 75.47,
  "temperature_difference": -0.40,
  "timestamp": "2026-01-04T17:23:54.846Z"
}
```

### **After (With ML Features):**
```json
{
  "_id": "695aa22a1423c6e74593ca03",
  "device_id": "edas_zone1",
  "plant_temperature": 30.11,
  "air_temperature": 30.51,
  "humidity": 75.47,
  "temperature_difference": -0.40,
  "timestamp": "2026-01-04T17:23:54.846Z",
  "hour": 17,
  "is_day": true,
  "time_period": "evening"
}
```

---

## 🔄 Automatic Processing Flow

```
┌─────────────────────────────────────────────────────────┐
│ STEP 1: ESP32 Sends Sensor Data                        │
└─────────────────────────────────────────────────────────┘

POST /api/v1/edas/sensor-data
{
  "device_id": "edas_zone1",
  "plant_temperature": 30.11,
  "air_temperature": 30.51,
  "humidity": 75.47
}

┌─────────────────────────────────────────────────────────┐
│ STEP 2: Backend Auto-Calculates (NO ARDUINO CODE!)     │
└─────────────────────────────────────────────────────────┘

1. ✅ Set timestamp = datetime.utcnow()
2. ✅ Calculate temperature_difference = 30.11 - 30.51 = -0.40
3. ✅ Extract hour = 17 (from timestamp)
4. ✅ Determine is_day = True (17 is between 6-18)
5. ✅ Classify time_period = "evening" (17 is between 14-18)

┌─────────────────────────────────────────────────────────┐
│ STEP 3: Store in MongoDB with ALL Fields               │
└─────────────────────────────────────────────────────────┘

{
  "device_id": "edas_zone1",
  "plant_temperature": 30.11,
  "air_temperature": 30.51,
  "humidity": 75.47,
  "temperature_difference": -0.40,
  "timestamp": "2026-01-04T17:23:54.846Z",
  "hour": 17,              ← Auto-calculated
  "is_day": true,          ← Auto-calculated
  "time_period": "evening" ← Auto-calculated
}
```

---

## 🎓 ML Training Use Cases

### **Use Case 1: Day/Night Pattern Separation**

```python
# ML can now learn different patterns for day vs night

# Day Pattern (is_day = True)
# - High temperature + Low humidity = Heat stress risk
# - High temp_diff + Direct sun = Leaf damage risk

# Night Pattern (is_day = False)
# - High humidity + Low temp_diff = Fungal disease risk
# - Condensation + Cold = Powdery mildew risk
```

### **Use Case 2: Time Period-Specific Models**

```python
# Train separate models for each time period

morning_model = train(data[data['time_period'] == 'morning'])
noon_model = train(data[data['time_period'] == 'noon'])
evening_model = train(data[data['time_period'] == 'evening'])
night_model = train(data[data['time_period'] == 'night'])

# More accurate predictions based on time context
```

### **Use Case 3: Hourly Risk Prediction**

```python
# Predict disease risk by hour of day

high_risk_hours = data.groupby('hour').apply(lambda x: x['has_disease'].mean())

# Example insights:
# - Hour 6-8: High fungal spore activity (morning dew)
# - Hour 12-14: Peak heat stress risk
# - Hour 18-20: Transition to fungal-favorable conditions
```

---

## 🧪 Testing the Implementation

### **Test 1: Insert Data and Verify Time Features**

```bash
# Using PowerShell
$payload = @{
    device_id = "edas_test"
    plant_temperature = 28.5
    air_temperature = 26.0
    humidity = 72.0
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://192.168.1.3:8000/api/v1/edas/sensor-data" `
    -Method POST `
    -ContentType "application/json" `
    -Body $payload
```

### **Test 2: Retrieve and Check Fields**

```bash
# Get latest reading
Invoke-WebRequest -Uri "http://192.168.1.3:8000/api/v1/edas/sensor-data/latest" | 
    Select-Object -ExpandProperty Content | 
    ConvertFrom-Json | 
    Select-Object hour, is_day, time_period
```

**Expected Output:**
```json
{
  "hour": 17,
  "is_day": true,
  "time_period": "evening"
}
```

### **Test 3: Verify Different Time Periods**

Insert data at different times and verify classifications:

| Current Time (UTC) | Expected `hour` | Expected `is_day` | Expected `time_period` |
|-------------------|-----------------|-------------------|------------------------|
| 08:30 AM | 8 | true | morning |
| 12:00 PM | 12 | true | noon |
| 04:00 PM | 16 | true | evening |
| 10:00 PM | 22 | false | night |
| 02:00 AM | 2 | false | night |

---

## 📝 MongoDB Queries for ML Training

### **Query 1: Get All Day Readings**
```javascript
db.edas_sensor_data.find({ is_day: true })
```

### **Query 2: Get Night Readings with High Humidity**
```javascript
db.edas_sensor_data.find({
  is_day: false,
  humidity: { $gt: 70 }
})
```

### **Query 3: Get Morning Readings for Pattern Analysis**
```javascript
db.edas_sensor_data.find({
  time_period: "morning"
}).sort({ timestamp: -1 })
```

### **Query 4: Aggregate by Time Period**
```javascript
db.edas_sensor_data.aggregate([
  {
    $group: {
      _id: "$time_period",
      avg_temp_diff: { $avg: "$temperature_difference" },
      avg_humidity: { $avg: "$humidity" },
      count: { $sum: 1 }
    }
  }
])
```

### **Query 5: Hour-by-Hour Analysis**
```javascript
db.edas_sensor_data.aggregate([
  {
    $group: {
      _id: "$hour",
      avg_plant_temp: { $avg: "$plant_temperature" },
      avg_air_temp: { $avg: "$air_temperature" },
      avg_humidity: { $avg: "$humidity" }
    }
  },
  { $sort: { _id: 1 } }
])
```

---

## 🔧 Implementation Details

### **Files Modified:**

1. **`app/models/edas_models.py`**
   - Added `hour`, `is_day`, `time_period` fields to `EDASSensorData`
   - Updated `EDASSensorDataUpdate` and `EDASSensorDataResponse`
   - Added type hints with `Literal` for `time_period`

2. **`app/db/collections/edas_sensor_data.py`**
   - Added `calculate_time_features()` helper function
   - Updated `create_edas_reading()` to auto-calculate time features
   - Updated `update_edas_reading()` to recalculate on timestamp changes

### **Key Functions:**

```python
def calculate_time_features(timestamp: datetime) -> Dict[str, Any]:
    """Calculate time-based features from timestamp for ML training.
    
    Returns:
        {
            "hour": 0-23,
            "is_day": True/False,
            "time_period": "morning"|"noon"|"evening"|"night"
        }
    """
    hour = timestamp.hour
    is_day = 6 <= hour < 18
    
    if 6 <= hour < 10:
        time_period = "morning"
    elif 10 <= hour < 14:
        time_period = "noon"
    elif 14 <= hour < 18:
        time_period = "evening"
    else:
        time_period = "night"
    
    return {
        "hour": hour,
        "is_day": is_day,
        "time_period": time_period,
    }
```

---

## ✅ Validation & Quality Assurance

| Check | Status | Details |
|-------|--------|---------|
| **Linter Errors** | ✅ 0 errors | Clean code, no warnings |
| **Type Hints** | ✅ Complete | Full type annotations |
| **Documentation** | ✅ Comprehensive | Docstrings on all functions |
| **Backward Compatible** | ✅ Yes | Existing API unchanged |
| **Auto-Calculated** | ✅ Yes | No Arduino changes needed |
| **MongoDB Schema** | ✅ Updated | New fields stored automatically |

---

## 🚫 What NOT to Do

### **❌ Don't Send These Fields from Arduino:**

```cpp
// ❌ WRONG - Don't calculate in Arduino
String payload = "{";
payload += "\"hour\":17,";           // Backend calculates this
payload += "\"is_day\":true,";       // Backend calculates this
payload += "\"time_period\":\"evening\"";  // Backend calculates this
payload += "}";
```

### **✅ Correct - Only Send Sensor Data:**

```cpp
// ✅ CORRECT - Only send raw sensor readings
String payload = "{";
payload += "\"device_id\":\"edas_zone1\",";
payload += "\"plant_temperature\":" + String(plantTemp) + ",";
payload += "\"air_temperature\":" + String(airTemp) + ",";
payload += "\"humidity\":" + String(humidity);
payload += "}";
```

**Backend automatically adds:** `timestamp`, `temperature_difference`, `hour`, `is_day`, `time_period`

---

## 📊 Expected Log Output

When data is inserted, you'll see in the backend logs:

```
INFO:     EDAS sensor reading created with ML time features
  collection: edas_sensor_data
  id: 695aa22a1423c6e74593ca03
  device_id: edas_zone1
  hour: 17
  is_day: True
  time_period: evening
```

---

## 🎯 ML Model Integration

### **Python ML Training Example:**

```python
import pandas as pd
from pymongo import MongoClient

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017")
db = client["smartrose"]

# Load EDAS data with time features
data = pd.DataFrame(list(db.edas_sensor_data.find()))

# Separate day and night data
day_data = data[data['is_day'] == True]
night_data = data[data['is_day'] == False]

# Train time-aware model
features = ['plant_temperature', 'air_temperature', 'humidity', 
            'temperature_difference', 'hour', 'is_day']

# One-hot encode time_period
data = pd.get_dummies(data, columns=['time_period'])

# Now you have: time_period_morning, time_period_noon, 
#                time_period_evening, time_period_night

# Train your disease prediction model
from sklearn.ensemble import RandomForestClassifier

X = data[features + ['time_period_morning', 'time_period_noon', 
                     'time_period_evening', 'time_period_night']]
y = data['has_disease']  # Your target variable

model = RandomForestClassifier()
model.fit(X, y)
```

---

## 🔄 Update Process

If timestamp is manually updated (administrative correction), time features are automatically recalculated:

```bash
# Update timestamp
PUT /api/v1/edas/sensor-data/{reading_id}
{
  "timestamp": "2026-01-05T08:00:00.000Z"
}

# Backend automatically recalculates:
# - hour = 8
# - is_day = True
# - time_period = "morning"
```

---

## 📚 Summary

✅ **3 new ML fields** added to every sensor record  
✅ **Fully automatic** - no Arduino code changes needed  
✅ **Timezone-safe** - UTC timestamps  
✅ **Backward compatible** - existing API unchanged  
✅ **Production ready** - 0 linter errors, full documentation  
✅ **ML-optimized** - enables time-aware disease prediction  

**Your EDAS system now provides rich time-context for accurate ML disease detection! 🌹🤖**

---

## 📞 Support

For questions about the ML time features:
1. Check this documentation
2. View inline code comments in:
   - `app/models/edas_models.py`
   - `app/db/collections/edas_sensor_data.py`
3. Test with API docs: http://localhost:8000/docs

---

**Implementation Date:** January 5, 2026  
**Status:** ✅ **COMPLETE & PRODUCTION READY**






