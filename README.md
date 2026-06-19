# 🩺 AI Health Consultation System

## 📖 Introduction

Healthcare accessibility remains a challenge for many people, especially when they are uncertain about the seriousness of their symptoms. Delays in seeking medical advice can lead to worsening health conditions, while unnecessary hospital visits may increase costs and burden healthcare systems.

The AI Health Consultation System is designed to address this problem by providing users with an intelligent platform for preliminary health assessment. The system combines Artificial Intelligence, Machine Learning, Natural Language Processing, and structured medical datasets to generate organized health reports and recommendations.

The application allows users to:

* Enter symptoms in natural language.
* Interact with an AI-powered consultation chatbot.
* Upload medical images for analysis.
* Upload PDF laboratory reports for interpretation.
* Receive disease predictions, severity assessment, precautions, and recommendations.

This project demonstrates the practical application of Large Language Models (LLMs) in healthcare support systems while maintaining a structured consultation workflow.

---

# 🎯 Objectives

The primary objectives of this project are:

* Develop an intelligent health consultation assistant.
* Collect patient symptoms through interactive conversations.
* Predict possible diseases using symptom matching techniques.
* Generate structured health reports.
* Analyze medical images using multimodal AI models.
* Interpret laboratory reports from uploaded PDFs.
* Provide severity assessment and precautionary guidance.
* Maintain consultation history for future reference.
* Improve healthcare awareness and early symptom assessment.

---

# ✨ Key Features

## 👤 Patient Profile Management

The system maintains a patient profile that stores:

* Name
* Age
* Gender
* Blood Pressure
* Existing Medical Conditions

This information helps personalize consultations and recommendations.

---

## 💬 Conversational AI Consultation

Instead of using traditional forms, the system conducts a natural conversation with the user.

Features include:

* Multi-turn question-answer sessions
* Context-aware questioning
* Follow-up symptom analysis
* Dynamic response generation
* Medical guidance in simple language

The chatbot uses the Groq API with LLaMA models for intelligent interaction.

---

## 🩺 Disease Prediction Engine

The disease prediction module uses a structured dataset containing:

* 413 diseases
* 982 symptoms
* Severity weights
* Disease descriptions
* Precaution information

The system compares user symptoms against the dataset and predicts the most relevant diseases.

### Prediction Process

1. User enters symptoms.
2. Symptoms are cleaned and normalized.
3. TF-IDF vectorization is applied.
4. Cosine similarity is calculated.
5. Top matching diseases are identified.
6. Severity score is computed.
7. Results are passed to the AI model for explanation.

---

## 📊 Severity Assessment

The system calculates symptom severity using predefined weights.

Severity Categories:

### 🟢 Mild

Minor symptoms that usually require monitoring and self-care.

### 🟡 Moderate

Conditions requiring medical consultation if symptoms persist.

### 🔴 Severe

Potentially serious conditions that require immediate medical attention.

This feature helps users understand the urgency of their condition.

---

## 📄 PDF Medical Report Analysis

Users can upload:

* Blood test reports
* Diagnostic reports
* Medical laboratory reports

The system:

* Extracts text from PDFs
* Identifies important findings
* Generates simplified explanations
* Provides health-related observations

---

## 🖼️ Medical Image Analysis

The application supports medical image uploads such as:

* Skin condition images
* X-rays
* Medical photographs

The AI model analyzes the image and generates a preliminary interpretation.

---

## 💾 Chat History Management

The system stores consultation history locally using JSON files.

Features include:

* Save conversations
* Load previous sessions
* Delete unwanted records
* Continue past consultations

---

# 🏗️ System Architecture

The system follows a three-layer architecture.

## 1️⃣ Presentation Layer

Responsible for user interaction.

Technologies:

* Python
* CustomTkinter

Functions:

* Display user interface
* Handle user inputs
* Show reports and results

---

## 2️⃣ Logic Layer

Responsible for processing.

Modules:

* chatbot_engine.py
* symptom_matcher.py

Functions:

* AI communication
* Disease prediction
* Severity calculation
* Prompt generation

---

## 3️⃣ Data Layer

Responsible for data storage and retrieval.

Components:

* CSV datasets
* JSON profile storage
* Chat history files
* Groq API

---

# 🛠️ Technologies Used

| Category             | Technology        |
| -------------------- | ----------------- |
| Programming Language | Python            |
| GUI Framework        | CustomTkinter     |
| AI Platform          | Groq API          |
| Text Model           | LLaMA 3.3 70B     |
| Vision Model         | LLaMA 4 Scout 17B |
| Machine Learning     | Scikit-Learn      |
| Data Processing      | Pandas, NumPy     |
| PDF Processing       | PyPDF2            |
| Image Processing     | Pillow            |
| Data Storage         | JSON              |
| Dataset Format       | CSV               |

---

# 📂 Project Structure

```bash
AI-Health-Consultation-System/
│
├── main.py
├── chatbot_engine.py
├── symptom_matcher.py
├── medicines.py
├── patient_profile.py
├── pdf_reader.py
├── config.py
│
├── Data/
│   ├── dataset.csv
│   ├── symptom_Description.csv
│   ├── symptom_precaution.csv
│   └── Symptom-severity.csv
│
├── chat_history/
├── README.md
├── requirements.txt
└── LICENSE
```

---

# 📊 Dataset Description

The system uses four major datasets:

### dataset.csv

Contains disease-to-symptom mappings.

### symptom_Description.csv

Contains disease descriptions.

### symptom_precaution.csv

Contains precautionary measures.

### Symptom-severity.csv

Contains severity weights for symptoms.

Dataset Coverage:

* 413 Diseases
* 982 Symptoms
* Severity Scale: 1–7

---

# 📈 Performance Results

Testing results showed:

* Average Text Response Time: 2–4 seconds
* Average Report Generation Time: 3–5 seconds
* Average Image Analysis Time: 3–6 seconds
* Disease Prediction Accuracy: Over 85% for common conditions
* AI Response Format Compliance: About 90%
* GUI Freeze Incidents: Zero

---

# 🚀 Future Enhancements

Planned improvements include:

* Voice-based consultation
* Mobile application
* Cloud database integration
* Appointment booking system
* Multilingual support
* Doctor recommendation engine
* Wearable health device integration

---

# ⚠️ Disclaimer

This project is intended solely for educational and research purposes. It is not a substitute for professional medical advice, diagnosis, or treatment. Always consult qualified healthcare professionals regarding medical conditions.

---

# 👨‍💻 Author

**Farhan Khan**

M.Sc. Artificial Intelligence & Machine Learning
Department of Computer Science
Jamia Millia Islamia, New Delhi

Major Project – 2026
