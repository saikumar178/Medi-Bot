# Medi-Bot

1.clone the repo
2.create a venv
    >python -m venv venv
3.activate the venv 
    >venv/Scripts/Activate
4.install requirements
    >pip install -r requirements.txt
5.run the main app
    >uvicorn main:app --reload --port 8000

->make sure to keep GROQ_API_KEY in .env file
->to deactivate venv
    >Deactivate