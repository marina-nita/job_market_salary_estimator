from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import joblib
import pandas as pd

app = FastAPI(title="Job Salary Estimator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500", "http://localhost:5500",
        "http://127.0.0.1:5501", "http://localhost:5501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# load model
MODEL_PATH = "salary_model_rf.joblib"
model = joblib.load(MODEL_PATH)

# load dataset
DATA_PATH = "jobs_clean_for_model_v2.csv"
df_ui = pd.read_csv(DATA_PATH)

# basic cleanup
for c in ["company", "location_restrictions", "employment_type", "seniority"]:
    if c in df_ui.columns:
        df_ui[c] = df_ui[c].fillna("").astype(str).str.strip()

def split_locations(s: str):
    s = (s or "").strip()
    if not s:
        return []
    return [x.strip() for x in s.split("|") if x.strip()]

# one row per job, country
df_loc = df_ui[["company", "location_restrictions"]].copy()
df_loc["location"] = df_loc["location_restrictions"].apply(split_locations)
df_loc = df_loc.explode("location")
df_loc["location"] = df_loc["location"].fillna("").astype(str).str.strip()
df_loc = df_loc[df_loc["location"] != ""]

_locations = sorted(df_loc["location"].unique().tolist())

# employment lists
def split_pipe_values(s: str):
    s = (s or "").strip()
    if not s:
        return []
    return [x.strip() for x in s.split("|") if x.strip()]

# normalize employment types
emp_vals = set()
for v in df_ui["employment_type"].dropna().astype(str):
    for x in split_pipe_values(v):
        emp_vals.add(x)
_employment_types = sorted(emp_vals)

sen_vals = set()
for v in df_ui["seniority"].dropna().astype(str):
    for x in split_pipe_values(v):
        sen_vals.add(x)
_seniorities = sorted(sen_vals)

TOP_COMPANIES_PER_LOCATION = 500
location_to_companies = {}
for loc, group in df_loc[df_loc["company"] != ""].groupby("location"):
    companies_sorted = group["company"].value_counts().index.tolist()
    location_to_companies[loc] = companies_sorted[:TOP_COMPANIES_PER_LOCATION]

class PredictRequest(BaseModel):
    title: str
    company: str
    location_restrictions: str
    employment_type: str
    seniority: str

# endpoint 
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/meta")
def meta():
    return {
        "employment_types": _employment_types,
        "seniorities": _seniorities,
    }

@app.get("/locations")
def locations():
    return {"locations": _locations}


@app.get("/companies")
def companies(location: str = Query(default="")):
    location = (location or "").strip()
    comps = location_to_companies.get(location, [])
    if "other" not in comps:
        comps = comps + ["other"]
    return {"location": location, "companies": comps}

# model serving endpoint
@app.post("/predict")
def predict(req: PredictRequest):
    title = (req.title or "").strip()
    company = (req.company or "").strip()
    location = (req.location_restrictions or "").strip()
    employment_type = (req.employment_type or "").strip()
    seniority = (req.seniority or "").strip()

    # IMPORTANT: text_all must match what the model was trained on
    # If training used "title | company | parent_categories | location_restrictions",
    # keep the same structure. Here we only have title/company/location.
    text_all = f"{title} | {company} | {location}"

    X = pd.DataFrame([{
        "text_all": text_all,
        "company": company,
        "location_restrictions": location,
        "employment_type": employment_type,
        "seniority": seniority,
    }])

    pred = float(model.predict(X)[0])
    return {"predicted_salary": pred}
