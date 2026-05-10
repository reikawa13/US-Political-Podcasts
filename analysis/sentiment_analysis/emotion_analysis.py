"""
GPU-accelerated emotion scoring for sentences using
`j-hartmann/emotion-english-distilroberta-base`.

Designed for NVIDIA RTX A2000 12GB (default `BATCH_SIZE=64`).
Input:  analysis/mapped_sentences_with_meta.csv (expects `sentence` column)
Output: analysis/final_emotion_scored.csv
Run:    python emotion_analysis.py
Deps:   pandas, torch (CUDA), transformers, tqdm
"""

import pandas as pd
from transformers import pipeline
from tqdm.auto import tqdm
import torch

# ==========================================
# 1. CONFIGURATION
# ==========================================
INPUT_FILE = "analysis/mapped_sentences_with_meta.csv"
OUTPUT_FILE = "analysis/final_emotion_scored.csv"
BATCH_SIZE = 64  # Optimal for 12GB VRAM

# ==========================================
# 2. SETUP GPU
# ==========================================
print(f"Checking for GPU...")
device = -1
if torch.cuda.is_available():
    print(f"Success! Detected NVIDIA GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM Available: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    device = 0
else:
    print("WARNING: No GPU detected. This will be slow.")

print("Loading Emotion Model...")
emotion_pipe = pipeline(
    "text-classification",
    model="j-hartmann/emotion-english-distilroberta-base",
    tokenizer="j-hartmann/emotion-english-distilroberta-base",
    top_k=None, # Return scores for ALL emotions
    truncation=True,
    max_length=512,
    device=device
)

# ==========================================
# 3. FAST PROCESSING (BATCH MODE)
# ==========================================
if __name__ == "__main__":
    print(f"Loading data from {INPUT_FILE}...")
    df = pd.read_csv(INPUT_FILE)
    
    # Filter junk to speed it up further (Optional)
    # df = df[~df['Thesis_Label'].isin(["Others", "Unmapped"])]
    
    # Extract sentences as a list (Critical for GPU batching)
    sentences = df['sentence'].astype(str).tolist()
    
    print(f"Processing {len(sentences)} sentences on GPU (Batch Size: {BATCH_SIZE})...")
    
    # Run the pipeline on the LIST, not the DataFrame row-by-row
    # This activates the GPU speedup
    results = []
    for out in tqdm(emotion_pipe(sentences, batch_size=BATCH_SIZE), total=len(sentences)):
        # 'out' is a list of dicts like [{'label': 'fear', 'score': 0.9}, ...]
        # We need to flatten it
        scores = {res['label']: res['score'] for res in out}
        top_emotion = max(scores, key=scores.get)
        
        results.append({
            "Top_Emotion": top_emotion,
            "Fear_Score": scores.get("fear", 0),
            "Anger_Score": scores.get("anger", 0),
            "Joy_Score": scores.get("joy", 0),
            "Sadness_Score": scores.get("sadness", 0),
            "Disgust_Score": scores.get("disgust", 0),
            "Surprise_Score": scores.get("surprise", 0),  # Added
            "Neutral_Score": scores.get("neutral", 0)   # Added (Crucial!)
        })

    # ==========================================
    # 4. MERGE & SAVE
    # ==========================================
    print("Merging results...")
    emotion_df = pd.DataFrame(results)
    
    # Reset index to ensure alignment
    df = df.reset_index(drop=True)
    final_df = pd.concat([df, emotion_df], axis=1)
    
    print(f"Saving to {OUTPUT_FILE}...")
    final_df.to_csv(OUTPUT_FILE, index=False)
    
    print("Done! Here is a sample:")
    print(final_df[['Thesis_Label', 'Top_Emotion', 'Fear_Score']].head())
