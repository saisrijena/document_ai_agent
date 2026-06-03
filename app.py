import streamlit as st
import fitz
from docx import Document
from google import genai
import pandas as pd
import io
import json

api_key = st.secrets["GEMINI_API_KEY"]
