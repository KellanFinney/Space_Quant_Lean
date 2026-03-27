FROM quantconnect/lean:latest

# Install NLTK and download required data
RUN pip install nltk && \
    python -c "import nltk; nltk.download('vader_lexicon')"

# TensorFlow for neural-net strategies (lesson16)
RUN pip install --no-cache-dir tensorflow
