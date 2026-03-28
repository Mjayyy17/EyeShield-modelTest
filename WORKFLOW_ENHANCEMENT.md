# Screening Workflow Enhancement - Save/Back Behavior

## ✅ Changes Complete

Updated the screening workflow to improve user experience and prevent accidental data loss.

---

## 🔄 Behavior Changes

### **1. Save Button - Now Keeps Window Open**

#### **Before:**
```
User clicks "Save" → Results window closes → Back to empty form
```

#### **After:**
```
User clicks "Save" → Results window stays open → Can view results
                                              → Can export PDF
                                              → Can review before next patient
```

**Why:** Clinicians often need to review the saved result, export a PDF, or show the patient the results before moving to the next screening.

---

### **2. Back Button - Now Clears All Data with Warnings**

#### **Before:**
```
User clicks "Back" → Returns to form (data still there)
                  → Warning only if unsaved
```

#### **After:**
```
User clicks "Back" → Warning dialog appears (ALWAYS)
                  → "Clear and Go Back" or "Stay on Results"
                  → If confirmed: ALL data cleared, fresh start
                  → If cancelled: Stays on results page
```

**Why:** Prevents confusion about whether form data persists. Explicit clearing ensures clean slate for next patient.

---

## 📋 Warning Dialog Details

### **Scenario 1: Unsaved Results**
```
┌────────────────────────────────────────────┐
│ ⚠️  Back to Screening                     │
├────────────────────────────────────────────┤
│ Unsaved screening results will be lost.   │
│                                            │
│ Going back will clear all patient data    │
│ and start a new screening.                │
│                                            │
│ Are you sure you want to go back?         │
├────────────────────────────────────────────┤
│  [Stay on Results]  [Clear and Go Back]   │
│        (Default)         (Destructive)     │
└────────────────────────────────────────────┘
```

### **Scenario 2: Saved Results**
```
┌────────────────────────────────────────────┐
│ ⚠️  Back to Screening                     │
├────────────────────────────────────────────┤
│ Going back will clear all patient data    │
│ and start a new screening.                │
│                                            │
│ Are you sure you want to go back?         │
├────────────────────────────────────────────┤
│  [Stay on Results]  [Clear and Go Back]   │
│        (Default)         (Destructive)     │
└────────────────────────────────────────────┘
```

---

## 🔧 Technical Changes

### **File 1: `screening_results.py`**

#### **Change 1 - Save Button (Line ~1013):**
```python
# BEFORE:
result = self.parent_page.save_screening(reset_after=True)

# AFTER:
result = self.parent_page.save_screening(reset_after=False)  # Keep window open
```

#### **Change 2 - Back Button (Line ~987):**
```python
def go_back(self):
    """Go back to screening form - clears all fields with confirmation."""
    if not self.parent_page:
        return
    page = self.parent_page
    
    # Always show warning before going back (data will be cleared)
    box = QMessageBox(self)
    box.setWindowTitle("Back to Screening")
    box.setIcon(QMessageBox.Icon.Warning)
    
    if not getattr(page, "_current_eye_saved", True):
        # Unsaved results - stronger warning
        box.setText(
            "<b>Unsaved screening results will be lost.</b><br><br>"
            "Going back will clear all patient data and start a new screening.<br><br>"
            "Are you sure you want to go back?"
        )
    else:
        # Saved results - still warns about clearing
        box.setText(
            "Going back will clear all patient data and start a new screening.<br><br>"
            "Are you sure you want to go back?"
        )
    
    stay_btn = box.addButton("Stay on Results", QMessageBox.ButtonRole.RejectRole)
    clear_btn = box.addButton("Clear and Go Back", QMessageBox.ButtonRole.DestructiveRole)
    box.setDefaultButton(stay_btn)
    box.exec()
    
    if box.clickedButton() != clear_btn:
        write_activity("INFO", "DIALOG_BACK_TO_SCREENING", "User chose to stay")
        return
    
    write_activity("WARNING", "DIALOG_BACK_TO_SCREENING", "User confirmed clear and go back")
    
    # Clear all fields and reset
    page.reset_screening()
    
    # Switch back to intake form
    if hasattr(page, "stacked_widget"):
        page.stacked_widget.setCurrentIndex(0)
```

---

### **File 2: `screening_form.py`**

#### **Change - Reset Method (Line ~1647):**
Added clearing for Phase 1 fields:
```python
if hasattr(self, "rbs"):
    self.rbs.setValue(0)
if hasattr(self, "height"):
    self.height.setValue(0)
if hasattr(self, "weight"):
    self.weight.setValue(0)
if hasattr(self, "bmi"):
    self.bmi.setValue(0)
if hasattr(self, "treatment_regimen"):
    self.treatment_regimen.setCurrentIndex(0)
if hasattr(self, "prev_dr_stage"):
    self.prev_dr_stage.setCurrentIndex(0)
self.symptom_blurred.setChecked(False)
```

---

## 🎯 User Workflow Examples

### **Typical Single-Eye Screening:**
```
1. Enter patient data
2. Upload fundus image
3. Click "Analyze"
4. View results
5. Click "Save Result"           ← Results window stays open
6. Review result on screen
7. Click "Export PDF" (optional)
8. Click "Back"                  ← Warning appears
9. Click "Clear and Go Back"     ← All data cleared
10. Ready for next patient
```

### **Bilateral Screening (Both Eyes):**
```
1. Enter patient data
2. Screen RIGHT eye
3. Click "Save Result"           ← Window stays open
4. Prompted: "Screen other eye?"
5. Click "Continue"
6. Form keeps patient data       ← Demographics preserved
7. Upload LEFT eye image
8. Analyze and save
9. Click "Back"                  ← Warning appears
10. Confirm to clear all
```

### **Review Without Clearing:**
```
1. Complete screening
2. Click "Save Result"           ← Window stays open
3. Review results
4. Decide to stay longer
5. Click "Export PDF"
6. Eventually click "Back"       ← Warning appears
7. Can cancel to stay on results
```

---

## 🛡️ Safety Features

### **Multiple Confirmation Points:**
1. ✅ **Unsaved warning** - Bold text if results not saved
2. ✅ **Default to safe action** - "Stay on Results" is default button
3. ✅ **Destructive button styling** - "Clear and Go Back" has red styling
4. ✅ **Clear messaging** - Explains that ALL data will be cleared
5. ✅ **Activity logging** - All user choices logged for audit

### **What Gets Cleared:**
When "Clear and Go Back" is clicked:
- ✅ Patient demographics (name, DOB, age, sex, contact)
- ✅ Clinical history (diabetes type, duration, HbA1c, treatment)
- ✅ Vital signs (BP, blood glucose, height, weight, BMI)
- ✅ Visual acuity values
- ✅ Symptoms
- ✅ Clinical notes
- ✅ Uploaded image
- ✅ Analysis results
- ✅ Previous DR stage, treatment regimen
- ✅ New patient ID generated

**Result:** Fresh, empty form ready for next patient.

---

## ✅ Benefits

### **For Clinicians:**
- ✨ **Review before next patient** - Can view saved results longer
- ✨ **Export after save** - Natural workflow: Save → Review → Export → Next
- ✨ **Prevents mixing patients** - Clear warning before clearing data
- ✨ **Explicit clearing** - No confusion about whether data persists

### **For Workflow:**
- ✨ **Reduced errors** - Less chance of mixing patient data
- ✨ **Better UX** - Results stay visible after save
- ✨ **Predictable behavior** - Clear data when starting fresh
- ✨ **Audit trail** - Logs all user decisions

---

## 🔄 Comparison Table

| Action | Before | After |
|--------|--------|-------|
| **Click Save** | Window closes, form cleared | Window stays open, data preserved |
| **Click Back (unsaved)** | Warning, then back to form | Warning, then CLEAR ALL if confirmed |
| **Click Back (saved)** | Back to form (data there) | Warning, then CLEAR ALL if confirmed |
| **Start new patient** | Manually clear fields | Auto-cleared after Back button |
| **Review after save** | Window closed (can't review) | Window open (can review) |

---

## 📝 Notes

1. **Save behavior** - Changed `reset_after=True` to `reset_after=False`
2. **Back behavior** - Now ALWAYS clears all fields after confirmation
3. **Warning dialog** - Appears every time Back is clicked
4. **Button styling** - "Clear and Go Back" uses destructive role (red)
5. **Default button** - "Stay on Results" is default (safer)
6. **Phase 1 fields** - All new fields properly cleared in reset

---

## 🧪 Testing Recommendations

### **Test 1 - Save and Stay:**
1. Complete screening
2. Click "Save Result"
3. ✓ Verify window stays open
4. ✓ Verify can still export PDF
5. ✓ Verify all buttons still work

### **Test 2 - Back with Warning (Unsaved):**
1. Complete screening (don't save)
2. Click "Back"
3. ✓ Verify warning appears with bold text
4. ✓ Click "Stay on Results"
5. ✓ Verify stays on results page

### **Test 3 - Back and Clear (Saved):**
1. Complete screening
2. Click "Save Result"
3. Click "Back"
4. ✓ Verify warning appears
5. ✓ Click "Clear and Go Back"
6. ✓ Verify ALL fields cleared
7. ✓ Verify new patient ID generated
8. ✓ Verify on intake form (index 0)

### **Test 4 - Cancel Clearing:**
1. Complete screening and save
2. Click "Back"
3. ✓ Verify warning appears
4. ✓ Click "Stay on Results"
5. ✓ Verify remains on results page
6. ✓ Verify can still interact

---

**Implementation Date**: 2026-03-27  
**Status**: ✅ Ready for Testing  
**Files Modified**: `screening_results.py`, `screening_form.py`  
**Validation**: ✅ Syntax Checked (Both files)
