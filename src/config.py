"""Board and column identifiers for the Resources for Growing board.

These IDs were extracted from the live Monday.com board during the audit.
Run `python intake.py --refresh-config` to re-fetch them if the board changes.
"""

BOARD_ID = 3541315134
SUBITEMS_BOARD_ID = 3541315228

GROUP_TITLE_ISRAEL = "מקורות מישראל"
GROUP_TITLE_ABROAD = "מקורות מחו\"ל"

COL_REQUEST_TYPE = "color_mkphtbwm"
COL_SOURCE = "color_mkq4wcmv"
COL_OUR_STAGE = "color0"
COL_THEIR_STAGE = "status__1"
COL_DEADLINE = "date"
COL_DATE_SENT = "date2__1"
COL_DATE_FIT_CHECK = "date20__1"
COL_DATE_CONTENT_PREP = "date_1__1"
COL_DATE_REVISIONS = "date_2__1"
COL_BUDGET_REQUESTED = "numeric"
COL_AMOUNT_RECEIVED = "numeric_mm2wvg5y"
COL_SUBMISSION_ANALYSIS = "long_text_mkqgjve6"

SUB_COL_TASK_TYPE = "dropdown_mkmbrh3j"
SUB_COL_EXECUTOR = "dropdown_mkxrnxep"
SUB_COL_STATUS = "status"
SUB_COL_HOURS = "numbers"
SUB_COL_DUE_DATE = "date"

# Forbidden columns — never write to these.
FORBIDDEN_COLUMNS = frozenset({
    "color_mkxrf6kb",  # duplicate "מבצע בפועל" (status flavor)
    "color_mkxra7wc",  # "מסגרת הפעולה" — always empty in real data
})

REQUEST_TYPE_VALUE = "הגשה למענק/קול קורא"
INITIAL_OUR_STAGE = "בדיקת התאמה"
DEFAULT_TASK_STATUS = "Working on it"

SOURCE_CATEGORIES = [
    "קרנות פילנתרופיות",
    "משרדי ממשלה",
    "רשויות מקומיות",
    "תאגידים",
    "שגרירויות",
    "פדרציות",
    "תורמים פרטיים גדולים",
    "תורמים פרטיים קטנים",
    "שותפויות עם המגזר השלישי",
    "אנשי מקצוע פרטיים",
    "קרנות בינלאומיות",
    "מאגרי מידע על מענקים",
    "פלטפורמות לגיוס משאבים",
    "ארגוני המגזר השלישי",
    "קמפיין מימון המונים",
    "חברות מסחריות",
    "כללי",
]

TASK_TYPES = [
    "הכנסה למאגר",
    "יצירת קשר",
    "בדיקת התאמה",
    "הכנת תוכן",
    "הגשה",
    "תיקונים של ההגשה",
    "פולואפ",
    "פולואפ לבדיקת קבלת הגשה",
    "פגישה",
    "אדמניסטרציה",
    "הכנת חומרים שיווקיים",
]

CLAUDE_MODEL = "claude-opus-4-7"
MONDAY_API_URL = "https://api.monday.com/v2"
MONDAY_API_VERSION = "2024-10"
