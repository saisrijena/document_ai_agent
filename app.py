import streamlit as st
import fitz
from docx import Document
from google import genai
import pandas as pd
import io
import json

api_key = st.secrets["AQ.Ab8RN6KMwmej5CJPC8cpm68_qaXzF6X8GpLXkBv7M1J_J1xXHw"]
