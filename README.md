# Overview:
DSS-Track allows users to compare rows within Excel/CSV spreadsheets to identify items with significant semantic similarity (i.e. similar "meaning"). It tracks deep semantic similarity between uploaded rows, using a lightweight sentence-transformer model for encoding, to generate semantic embeddings. These semantic embeddings are then compared within the vector space via cosine similarity to identify possible duplicates.

# Demo Video:
https://github.com/user-attachments/assets/47de53f0-022b-45a9-a052-e5ae223813fc

_Note: Video quality downscaled due to Github limitations_

# Get Started:
1. Ensure Docker installed locally
2. Run `./build.sh`
3. Profit

# Ports:
 - 3100: Frontend/UI
 - 8000: API/Backend
 - 8000/docs: Swagger UI via Browser
