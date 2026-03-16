# Job Market Salary Estimator

End-to-end ML project built for the **Data Science course (Master’s degree, Year 1)**.  
The project scrapes salary-listed job postings (Himalayas), cleans the dataset, trains a regression model, and serves predictions through a simple web app.

---

## What it does

- **Scraping:** collects job postings that include salary ranges  
- **Cleaning:** removes duplicates, handles missing values, keeps USD only, filters extreme outliers  
- **Modeling:** trains a **RandomForestRegressor** and tunes it with **GridSearchCV**  
- **Serving:** exposes predictions via a **FastAPI** backend + simple **HTML/JS** frontend  

---

## Tech Stack

- Python, Pandas, NumPy  
- Scrapy  
- scikit-learn (TF-IDF, pipelines, Random Forest, GridSearchCV)  
- FastAPI + Uvicorn  
- HTML + JavaScript  

