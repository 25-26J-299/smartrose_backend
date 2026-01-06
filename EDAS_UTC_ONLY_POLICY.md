# ✅ EDAS UTC-Only Timestamp Policy

**Status:** ✅ **IMPLEMENTED**  
**Date:** January 6, 2026  
**Policy:** Backend is timezone-agnostic - all timestamps in UTC

---

## 🎯 **Policy Statement**

**All EDAS API responses return timestamps in UTC ISO format.**

- ✅ **Stored in MongoDB:** UTC
- ✅ **Returned from APIs:** UTC (no conversion)
- ✅ **Backend behavior:** Timezone-agnostic
- ❌ **No local time conversions** in backend responses

---

## 📊 **Timestamp Format**

### **Standard Format:**
```
2026-01-06T18:00:00Z
```

**Components:**
- `2026-01-06` - Date (YYYY-MM-DD)
- `T` - Time separator
- `18:00:00` - Time (HH:MM:SS)
- `Z` - UTC indicator (Zulu time)

### **Alternative Valid Formats:**
```
2026-01-06T18:00:00+00:00  // UTC with explicit offset
2026-01-06T18:00:00.000Z   // With milliseconds
```

---

## 🔄 **Data Flow**

### **Writing Data (ESP32 → Backend → MongoDB):**

```
1. ESP32 sends sensor data (no timestamp)
   ↓
2. Backend captures current Sri Lankan time
   local_time = 2026-01-06 23:45:00 SLST (UTC+5:30)
   ↓
3. Calculate ML features from LOCAL time
   hour = 23, is_day = false, time_period = "night"
   ↓
4. Convert timestamp to UTC for storage
   utc_time = 2026-01-06 18:15:00 UTC
   ↓
5. Store in MongoDB
   {
     "timestamp": "2026-01-06T18:15:00Z",  // UTC
     "hour": 23,         // From local time
     "is_day": false,    // From local time
     "time_period": "night"  // From local time
   }
```

### **Reading Data (API Request → MongoDB → Response):**

```
1. API request arrives
   GET /api/v1/edas/latest-sensor-data
   ↓
2. Query MongoDB (sort by timestamp DESC)
   ↓
3. Return data AS-IS (UTC timestamp)
   {
     "plantTemp": 29.63,
     "timestamp": "2026-01-06T18:15:00Z"  // UTC
   }
   ↓
4. Frontend/Client handles timezone conversion if needed
```

---

## ✅ **Why UTC-Only?**

### **Benefits:**

1. **Simplicity**
   - Backend doesn't need to know timezones
   - One timestamp format for all APIs
   - No conversion errors

2. **Flexibility**
   - Clients can convert to ANY timezone
   - Mobile apps use device timezone
   - Web apps use browser timezone

3. **Consistency**
   - All timestamps comparable
   - Easy sorting and filtering
   - No DST (Daylight Saving) issues

4. **Database Best Practice**
   - UTC is international standard
   - Works globally
   - Avoids timezone ambiguities

5. **Scalability**
   - Add greenhouses in any timezone
   - No backend changes needed
   - Timezone handled client-side

---

## 🎨 **Frontend Timezone Conversion**

### **JavaScript/React:**

```javascript
// API returns UTC
const data = {
  plantTemp: 29.63,
  timestamp: "2026-01-06T18:15:00Z"  // UTC
};

// Convert to local timezone (automatic)
const localTime = new Date(data.timestamp);
console.log(localTime.toLocaleString());
// Output: "1/6/2026, 11:45:00 PM" (if browser is in Sri Lanka)

// Or specify timezone explicitly
const slTime = new Date(data.timestamp).toLocaleString('en-US', {
  timeZone: 'Asia/Colombo',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit'
});
console.log(slTime);
// Output: "01/06/2026, 11:45:00 PM"
```

### **Python Client:**

```python
from datetime import datetime
import pytz

# API returns UTC
timestamp_utc = "2026-01-06T18:15:00Z"

# Parse UTC timestamp
dt_utc = datetime.fromisoformat(timestamp_utc.replace('Z', '+00:00'))

# Convert to Sri Lankan timezone
sl_tz = pytz.timezone('Asia/Colombo')
dt_sl = dt_utc.astimezone(sl_tz)

print(dt_sl)  # 2026-01-06 23:45:00+05:30
```

### **React Component Example:**

```jsx
const SensorDataDisplay = ({ data }) => {
  // Automatically converts to browser's local timezone
  const localTime = new Date(data.timestamp);
  
  return (
    <div>
      <p>Plant Temp: {data.plantTemp}°C</p>
      <p>Timestamp (Local): {localTime.toLocaleString()}</p>
      <p>Timestamp (UTC): {data.timestamp}</p>
    </div>
  );
};
```

---

## 📋 **API Response Examples**

### **1. GET /api/v1/edas/latest-sensor-data**

```json
{
  "plantTemp": 29.63,
  "airTemp": 29.83,
  "humidity": 81.71,
  "temperatureDifference": -0.20,
  "timestamp": "2026-01-06T18:15:00Z"
}
```

### **2. GET /api/v1/edas/sensor-data/latest**

```json
{
  "_id": "695c053ce6b12ddca7cf4b35",
  "device_id": "edas_zone1",
  "plant_temperature": 29.63,
  "air_temperature": 29.83,
  "humidity": 81.71,
  "temperature_difference": -0.20,
  "timestamp": "2026-01-06T18:15:00Z",
  "hour": 23,
  "is_day": false,
  "time_period": "night"
}
```

### **3. GET /api/v1/edas-data/latest-with-prediction**

```json
{
  "status": "success",
  "data": {
    "sensor_data": {
      "timestamp": "2026-01-06T18:15:00Z",
      ...
    }
  }
}
```

**All timestamps are UTC! ✅**

---

## 🔍 **ML Time Features Explained**

### **The Smart Approach:**

```json
{
  "timestamp": "2026-01-06T18:15:00Z",  // UTC for storage
  "hour": 23,          // From Sri Lankan time (for ML)
  "is_day": false,     // From Sri Lankan time (for ML)
  "time_period": "night"  // From Sri Lankan time (for ML)
}
```

**Why this works:**

- **Timestamp (UTC):** Universal, database-friendly, timezone-agnostic
- **ML Features (Local):** Accurate for greenhouse conditions
- **Best of both worlds!**

### **ML Training Uses Local Time Features:**

```python
# ML Model Training
X = data[['plant_temperature', 'air_temperature', 'humidity', 
          'temperature_difference', 'hour', 'is_day']]

# hour, is_day, time_period are from LOCAL greenhouse time
# This ensures ML learns patterns based on actual day/night cycles
```

---

## 🧪 **Testing UTC Responses**

### **Test 1: Verify UTC Format**

```bash
# Fetch latest data
curl http://localhost:8000/api/v1/edas/latest-sensor-data

# Check timestamp ends with 'Z' (UTC indicator)
# Expected: "timestamp": "2026-01-06T18:15:00Z"
```

### **Test 2: Compare MongoDB and API**

```javascript
// MongoDB Shell
db.edas_sensor_data.findOne({}, {timestamp: 1})
// Result: ISODate("2026-01-06T18:15:00.000Z")

// API Response
// Result: "2026-01-06T18:15:00Z"

// ✅ Both are UTC!
```

### **Test 3: Verify No Timezone Conversion**

```python
# Send data at 23:45 Sri Lankan time
# Backend stores as 18:15 UTC

# API should return: "2026-01-06T18:15:00Z" (NOT "2026-01-06T23:45:00+05:30")
```

---

## 📝 **Migration Notes**

### **No Database Changes Needed:**

- ✅ Existing data already in UTC (correct format)
- ✅ No schema changes required
- ✅ No data migration scripts needed

### **What Changed:**

- ✅ Removed timezone conversion from READ functions
- ✅ Backend now returns UTC timestamps as-is
- ✅ Frontend handles timezone conversion

### **What Stayed the Same:**

- ✅ Data stored in UTC (always was)
- ✅ ML features calculated from local time (correct)
- ✅ API endpoints unchanged
- ✅ Request/response formats unchanged (except timestamp format)

---

## ✅ **Compliance Checklist**

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| **Store in UTC** | ✅ | MongoDB timestamps in UTC |
| **Return in UTC** | ✅ | All API responses use UTC |
| **UTC ISO format** | ✅ | Format: `2026-01-06T18:00:00Z` |
| **No local conversion** | ✅ | Removed timezone conversion from reads |
| **No DB changes** | ✅ | Existing data unchanged |
| **No schema changes** | ✅ | Schema remains the same |
| **Timezone-agnostic** | ✅ | Backend doesn't care about timezones |

---

## 🔧 **Implementation Details**

### **Files Modified:**

1. **`app/db/collections/edas_sensor_data.py`**
   - Removed timezone conversion from:
     - `get_all_edas_readings()`
     - `get_edas_reading_by_id()`
     - `get_latest_edas_reading()`
     - `get_edas_readings_by_device()`
   - All functions now return UTC timestamps as-is

2. **`app/api/v1/endpoints/edas.py`**
   - Updated `/latest-sensor-data` documentation
   - Clarified UTC timestamp in response

### **Not Changed:**

1. **Write operations** still calculate ML features from local time
2. **Database storage** still in UTC (always was)
3. **API routes** unchanged
4. **Request formats** unchanged

---

## 🎯 **Summary**

### **Backend Philosophy:**

```
Backend = UTC Only
Frontend = Any Timezone
ML Features = Local Time Context
```

### **Key Points:**

✅ **All timestamps returned in UTC ISO format**  
✅ **Backend is timezone-agnostic**  
✅ **Frontend handles timezone conversion**  
✅ **ML features still use local time context**  
✅ **No database changes required**  
✅ **Follows international best practices**  

---

## 📚 **References**

- **ISO 8601:** International timestamp standard
- **UTC:** Coordinated Universal Time
- **Zulu Time:** Military term for UTC (Z suffix)

---

**Implementation Date:** January 6, 2026  
**Status:** ✅ **UTC-ONLY POLICY ENFORCED**  
**Backend:** Timezone-agnostic, UTC ISO format only



