import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'diploma-secret-key-2024'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///platform.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
