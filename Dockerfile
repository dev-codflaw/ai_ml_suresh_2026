FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501

WORKDIR /app

# Install only lightweight runtime dependencies before copying application code
# so this layer remains cached across source-only changes.
RUN python -m pip install --no-cache-dir \
    "streamlit>=1.40,<2" \
    "PyMuPDF>=1.24,<2" \
    "pymongo>=4.8,<5" \
    "python-dotenv>=1.0,<2" \
    "requests>=2.32,<3"

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py"]
