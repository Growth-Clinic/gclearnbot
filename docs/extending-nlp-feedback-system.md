🔹 Step 1: Implement Fast Browser-Based NLP (Word Similarity Matching)
For this, we'll:
✅ Use wink-nlp (lightweight, fast, and optimized for mobile).
✅ Apply word similarity matching instead of strict keyword matching.
✅ Lazy-load NLP so the site still loads fast.

🔹 Step 2: Later, Add a Server-Side NLP Fallback
If the user's device is slow, we’ll send the request to the backend for better processing.
This will use Python NLP (e.g., spaCy or DistilBERT) for more advanced word understanding.
