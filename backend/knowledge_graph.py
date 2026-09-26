"""
knowledge_graph.py — VideoGPT Pro Multi-Video Knowledge Graph Engine
Builds concept maps and connects topics across all indexed videos.
"""

import json
from collections import defaultdict
from embeddings import list_all_videos, get_video_chunks
from ocr import get_visual_context

def build_knowledge_graph() -> dict:
    """
    Scans all indexed videos and visual contexts to build a simple keyword-based
    knowledge graph connecting common terms to the videos they appear in.
    """
    videos = list_all_videos()
    graph = defaultdict(lambda: {"videos": set(), "occurrences": 0})
    
    # We will build a basic keyword index. For a real production app, 
    # we would use an LLM or NLP library (like spaCy) to extract named entities.
    # Here, we'll do a simplified concept extraction based on frequent capitalized phrases.
    
    for v in videos:
        vid = v.get("video_id")
        if not vid:
            continue
            
        try:
            chunks = get_video_chunks(vid)
        except Exception:
            continue
            
        # Add visual chunks if available
        visual_chunks = get_visual_context(vid)
        
        all_text = " ".join([c.get("text", "") for c in chunks])
        all_text += " ".join([c.get("analysis", "") for c in visual_chunks])
        
        # Simple extraction: look for words > 5 chars that appear frequently
        words = [w.strip(".,!?:;\"'()[]{}") for w in all_text.split()]
        word_counts = defaultdict(int)
        for w in words:
            if len(w) > 5 and not w.lower() in _STOP_WORDS:
                # Capitalize to normalize
                word_counts[w.capitalize()] += 1
                
        # Top 15 concepts for this video
        top_concepts = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:15]
        
        for concept, count in top_concepts:
            graph[concept]["videos"].add(vid)
            graph[concept]["occurrences"] += count
            
    # Filter graph: only keep concepts that appear in > 1 video, or are very prominent
    filtered_graph = []
    for concept, data in graph.items():
        if len(data["videos"]) > 1 or data["occurrences"] > 5:
            filtered_graph.append({
                "concept": concept,
                "video_ids": list(data["videos"]),
                "weight": data["occurrences"]
            })
            
    # Sort by weight
    filtered_graph.sort(key=lambda x: x["weight"], reverse=True)
    
    return {
        "nodes": filtered_graph[:50], # Top 50 cross-video concepts
        "total_videos_analyzed": len(videos)
    }

_STOP_WORDS = {
    "about", "above", "across", "after", "again", "against", "because", "before", 
    "below", "between", "could", "during", "either", "enough", "especially", 
    "everything", "everywhere", "further", "having", "herself", "himself", 
    "however", "inside", "instead", "itself", "little", "meaning", "mostly", 
    "myself", "neither", "nobody", "nothing", "nowhere", "others", "ourselves", 
    "outside", "perhaps", "please", "probably", "rather", "really", "should", 
    "someone", "something", "sometimes", "somewhere", "themselves", "there", 
    "therefore", "things", "though", "through", "together", "toward", "towards", 
    "under", "unless", "until", "whatever", "whenever", "wherever", "whether", 
    "which", "while", "within", "without", "would", "yourself", "yourselves",
    "really", "people", "actually", "probably", "something", "everything", "because",
    "going", "think", "getting", "better", "always", "around", "another"
}
