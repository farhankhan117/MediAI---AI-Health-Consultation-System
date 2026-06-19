import pandas as pd
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "Data")

df_dataset     = pd.read_csv(os.path.join(DATA_DIR, "dataset.csv"))
df_description = pd.read_csv(os.path.join(DATA_DIR, "symptom_Description.csv"))
df_precaution  = pd.read_csv(os.path.join(DATA_DIR, "symptom_precaution.csv"))
df_severity    = pd.read_csv(os.path.join(DATA_DIR, "Symptom-severity.csv"))

df_dataset.columns     = df_dataset.columns.str.strip()
df_description.columns = df_description.columns.str.strip()
df_precaution.columns  = df_precaution.columns.str.strip()
df_severity.columns    = df_severity.columns.str.strip()

disease_symptom_text = {}
for _, row in df_dataset.iterrows():
    disease = row["Disease"].strip()
    symptoms = [
        str(row[col]).strip().lower().replace("_", " ")
        for col in df_dataset.columns[1:]
        if pd.notna(row[col]) and str(row[col]).strip() != ""
    ]
    text = " ".join(symptoms)
    if disease not in disease_symptom_text:
        disease_symptom_text[disease] = text
    else:
        disease_symptom_text[disease] += " " + text

diseases      = list(disease_symptom_text.keys())
symptom_texts = list(disease_symptom_text.values())
vectorizer    = TfidfVectorizer()
tfidf_matrix  = vectorizer.fit_transform(symptom_texts)

def predict_diseases(user_input):
    user_input  = user_input.lower().replace("_", " ")
    user_vec    = vectorizer.transform([user_input])
    scores      = cosine_similarity(user_vec, tfidf_matrix).flatten()
    top_indices = scores.argsort()[::-1][:5]
    results = []
    for i in top_indices:
        if scores[i] > 0:
            results.append((diseases[i], round(float(scores[i]) * 100, 1)))
    return results

def get_description(disease):
    row = df_description[df_description["Disease"].str.strip() == disease]
    if not row.empty:
        return row.iloc[0]["Description"]
    return "No description available."

def get_precautions(disease):
    row = df_precaution[df_precaution["Disease"].str.strip() == disease]
    if not row.empty:
        return [
            str(row.iloc[0][col])
            for col in df_precaution.columns[1:]
            if pd.notna(row.iloc[0][col])
        ]
    return ["Please consult a doctor."]

def get_severity_score(user_input):
    user_input = user_input.lower()
    total = 0
    for _, row in df_severity.iterrows():
        symptom = str(row["Symptom"]).strip().lower().replace("_", " ")
        if symptom in user_input:
            total += int(row["weight"])
    return total

def get_severity_level(score):
    if score <= 12:
        return "Mild", "#2ecc71"
    elif score <= 18:
        return "Moderate", "#f39c12"
    else:
        return "Severe — Please see a doctor immediately", "#e74c3c"